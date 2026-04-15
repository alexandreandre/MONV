from openai import AsyncOpenAI
import json
from config import settings

client: AsyncOpenAI | None = None


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
) -> str:
    c = get_client()
    full_messages = [{"role": "system", "content": system}] + messages
    response = await c.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=full_messages,
    )
    return response.choices[0].message.content


async def llm_json_call(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> dict:
    """Call LLM and parse JSON from response."""
    raw = await llm_call(model, system, messages, max_tokens, temperature)

    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]

    return json.loads(raw.strip())
