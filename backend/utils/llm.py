from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI
from config import settings

client: AsyncOpenAI | None = None


def _strip_markdown_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    text = text.strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def extract_first_json_object(text: str) -> str | None:
    """Extrait le premier objet JSON équilibré `{ ... }` (hors chaînes)."""
    i = text.find("{")
    if i < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    j = i
    while j < len(text):
        c = text[j]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            j += 1
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
        j += 1
    return None


def parse_llm_json_text(raw: str) -> dict[str, Any]:
    """Parse la sortie d'un LLM : JSON pur, bloc isolé, ou extraction `{`…`}`."""
    text = _strip_markdown_fences(raw)
    if not text:
        raise json.JSONDecodeError("Réponse vide", "", 0)

    for candidate in (text, extract_first_json_object(text) or ""):
        if not candidate:
            continue
        try:
            out = json.loads(candidate)
            if isinstance(out, dict):
                return out
        except json.JSONDecodeError:
            continue

    # Dernier recours : premier `{` … `}` même avec bruit après (raw_decode)
    i = text.find("{")
    if i >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("JSON non parseable", text, 0)


def get_client() -> AsyncOpenAI:
    global client
    if client is None:
        client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": settings.SITE_URL,
                "X-Title": settings.APP_NAME,
            },
        )
    return client


async def llm_call(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = 0.0,
    *,
    json_mode: bool = False,
) -> str:
    c = get_client()
    full_messages = [{"role": "system", "content": system}] + messages
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": full_messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        response = await c.chat.completions.create(**kwargs)
    except Exception:
        if json_mode:
            kwargs.pop("response_format", None)
            response = await c.chat.completions.create(**kwargs)
        else:
            raise
    content = response.choices[0].message.content
    if content is None:
        return ""
    return content


_JSON_REPAIR_SYSTEM = """\
Tu reçois du texte qui devait être un seul objet JSON mais est invalide ou tronqué.
Reconstruis UN objet JSON **valide** UTF-8 en conservant le maximum d'informations
utiles. Pas de markdown, pas de commentaires, pas de texte avant ou après le JSON.
Si une chaîne est coupée, ferme-la proprement et supprime le fragment incomplet.
"""


async def llm_json_call(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = 0.0,
    *,
    json_mode: bool = False,
    allow_json_repair: bool = False,
    repair_model: str | None = None,
) -> dict[str, Any]:
    """Appelle le LLM et parse le JSON (résilient + réparation optionnelle)."""
    raw = await llm_call(
        model, system, messages, max_tokens, temperature, json_mode=json_mode
    )
    try:
        return parse_llm_json_text(raw or "")
    except json.JSONDecodeError:
        if not allow_json_repair or not (repair_model or "").strip():
            raise
        fix = await llm_call(
            repair_model or model,
            _JSON_REPAIR_SYSTEM,
            [{"role": "user", "content": (raw or "")[:14000]}],
            max_tokens=min(max_tokens, 8192),
            temperature=0.0,
            json_mode=False,
        )
        return parse_llm_json_text(fix or "")
