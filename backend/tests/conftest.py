"""Variables d'environnement avant tout import applicatif (ordre de collection pytest)."""

from __future__ import annotations

import os

# test_modes importe orchestrator → config avant test_relevance : il faut une clé
# non vide pour les tests qui mockent llm_json_call, même si la CI exporte OPENROUTER_API_KEY="".
os.environ.setdefault("SKIP_DB_VERIFY_ON_STARTUP", "true")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")
if not (os.environ.get("OPENROUTER_API_KEY") or "").strip():
    os.environ["OPENROUTER_API_KEY"] = "test-placeholder-openrouter-key"
