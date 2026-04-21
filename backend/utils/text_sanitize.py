"""Nettoyage de texte affiché à l'utilisateur."""

from __future__ import annotations

import re

# Plages usuelles d'émojis et pictogrammes (hors texte latin / ponctuation métier).
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # Symboles & pictos étendus
    "\U0001F600-\U0001F64F"  # Émoticons
    "\U0001F680-\U0001F6FF"  # Transport & cartes
    "\U0001F1E0-\U0001F1FF"  # Drapeaux régionaux
    "\U00002600-\U000027BF"  # Divers symboles dont ✏️ etc.
    "\U0000FE00-\U0000FE0F"  # Sélecteurs de variation
    "\u200d"  # ZWJ
    "]+",
    flags=re.UNICODE,
)


def strip_emojis(text: str) -> str:
    """Retire les émojis / pictogrammes ; compresse les espaces résiduels."""
    if not text:
        return text
    s = _EMOJI_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", s).strip()
