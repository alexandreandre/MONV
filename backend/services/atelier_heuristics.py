"""Heuristiques de titrage Atelier (sans LLM)."""

from __future__ import annotations

_PITCH_INTENT_PREFIXES: tuple[str, ...] = (
    "je veux créer ",
    "je veux lancer ",
    "je veux monter ",
    "je veux ouvrir ",
    "je souhaite créer ",
    "je souhaite lancer ",
    "je souhaite monter ",
    "je souhaite ouvrir ",
    "j'aimerais créer ",
    "j'aimerais lancer ",
    "j'aimerais monter ",
    "j'aimerais ouvrir ",
    "je compte créer ",
    "je compte lancer ",
    "je compte monter ",
    "je compte ouvrir ",
    "mon projet : ",
    "mon idée : ",
    "idée : ",
)


def _strip_french_pitch_intent(line: str) -> str:
    """Retire les préfixes du type « je veux créer » pour densifier le nom de projet."""
    s = " ".join(line.split())
    while True:
        low = s.lower()
        hit = False
        for p in _PITCH_INTENT_PREFIXES:
            if low.startswith(p):
                s = s[len(p) :].lstrip()
                hit = True
                break
        if not hit:
            break
    return s


def _strip_leading_article_phrase(line: str) -> str:
    """Retire un article en tête (« une boîte » → « boîte ») une seule fois."""
    s = line.strip()
    low = s.lower()
    for art in ("une ", "un ", "des ", "les ", "la ", "le ", "l'", "d'"):
        if low.startswith(art):
            return s[len(art) :].lstrip()
    return s


def _project_folder_display_fr(words: list[str]) -> str:
    """Casse lisible type « Boîte de nuit Marseille » : premier et dernier mot capitalisés."""
    if not words:
        return ""
    n = len(words)
    out: list[str] = []
    for i, raw in enumerate(words):
        core = raw.strip(".,;:!?").strip()
        if not core:
            continue
        low = core.lower()
        if i == 0 or i == n - 1:
            out.append(core[:1].upper() + core[1:].lower())
        else:
            out.append(low)
    return " ".join(out)


def heuristic_atelier_conversation_title(pitch: str, max_len: int = 72) -> str:
    """Titre de repli à partir du pitch : première phrase utile, découpe propre aux mots."""
    line = " ".join((pitch or "").split())
    if not line:
        return "Projet Atelier"
    lowered = line.lower()
    for prefix in (
        "bonjour ",
        "salut ",
        "bonsoir ",
        "hello ",
        "coucou ",
    ):
        if lowered.startswith(prefix):
            line = line[len(prefix) :].lstrip()
            lowered = line.lower()
            break
    for sep in (".", "!", "?", "…"):
        pos = line.find(sep)
        if 8 <= pos <= max_len + 24:
            line = line[:pos].strip()
            break
    if len(line) <= max_len:
        return line or "Projet Atelier"
    chunk = line[: max_len + 1]
    if " " in chunk:
        cut = chunk.rsplit(" ", 1)[0].strip()
        if len(cut) >= 8:
            return cut + "…"
    return line[:max_len].rstrip() + "…"


def heuristic_atelier_project_folder_name(pitch: str) -> str:
    """Nom de dossier projet de repli : pitch nettoyé, quelques mots, lieu conservé."""
    line = " ".join((pitch or "").split())
    if not line:
        return "Projet Atelier"
    lowered = line.lower()
    for prefix in (
        "bonjour ",
        "salut ",
        "bonsoir ",
        "hello ",
        "coucou ",
    ):
        if lowered.startswith(prefix):
            line = line[len(prefix) :].lstrip()
            lowered = line.lower()
            break
    line = _strip_french_pitch_intent(line)
    line = _strip_leading_article_phrase(line)
    if not line.strip():
        return "Projet Atelier"
    for sep in (".", "!", "?", "…"):
        pos = line.find(sep)
        if 8 <= pos <= 90:
            line = line[:pos].strip()
            break
    words = line.split()
    if len(words) > 7:
        words = words[:7]
    titled = _project_folder_display_fr(words)
    if not titled:
        return "Projet Atelier"
    out = titled[:80].strip()
    return out or "Projet Atelier"
