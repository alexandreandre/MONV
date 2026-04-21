from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    APP_NAME: str = "MONV"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    # Traces diagnostic sur stderr (voir ``utils/pipeline_log.py``)
    PIPELINE_DEBUG: bool = False

    # ── Supabase ──────────────────────────────────────────────────
    SUPABASE_URL: str = ""          # https://<project-ref>.supabase.co
    SUPABASE_KEY: str = ""          # anon / public key
    SUPABASE_SERVICE_KEY: str = ""  # service_role key (backend only)

    # ── OpenRouter ────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    SITE_URL: str = "http://localhost:3000"

    # Couche 0 — Filtre scope (le moins cher, rapide)
    FILTER_MODEL: str = "google/gemini-flash-1.5"
    # Couche 1 / 1b — Guard extraction + Conversationalist (coût moyen)
    GUARD_MODEL: str = "anthropic/claude-3.5-haiku"
    # Couche 2 — Orchestrateur plan d'exécution (le meilleur, précis)
    ORCHESTRATOR_MODEL: str = "anthropic/claude-3.5-sonnet"
    # Post-filtrage des lignes de résultats (rapide, JSON fiable via OpenRouter)
    RELEVANCE_FILTER_MODEL: str = "openai/gpt-4o-mini"
    # Enrichissement « pitch digital » (prospection) ; si vide → RELEVANCE_FILTER_MODEL
    DIGITAL_PITCH_ENRICH_MODEL: str = ""
    # Atelier — planification + dossier business (2 appels LLM). Si vide → ORCHESTRATOR_MODEL.
    ATELIER_BUSINESS_MODEL: str = ""

    # ── APIs externes ─────────────────────────────────────────────
    PAPPERS_API_KEY: str = ""
    SIRENE_BASE_URL: str = "https://recherche-entreprises.api.gouv.fr/search"
    GOOGLE_PLACES_API_KEY: str = ""
    PAPPERS_BASE_URL: str = "https://api.pappers.in/v1"
    PAPPERS_COUNTRY_CODE: str = "FR"

    # ── App ───────────────────────────────────────────────────────
    CACHE_TTL_HOURS: int = 48
    MAX_RESULTS_PER_QUERY: int = 150
    FREE_PREVIEW_ROWS: int = 10
    FREE_CREDITS: int = 5

    # Emails (séparés par des virgules) : pas de débit à l'export, solde API affiché comme illimité
    UNLIMITED_CREDITS_EMAILS: str = ""

    JWT_SECRET: str = "monv-local-dev-secret-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 72

    # Origines CORS (séparées par des virgules). Si vide : localhost + SITE_URL.
    CORS_ORIGINS: str = ""

    # CI / tests : évite l’appel Supabase au démarrage (défaut False en prod).
    SKIP_DB_VERIFY_ON_STARTUP: bool = False

    EXPORTS_DIR: str = "./exports"

    model_config = SettingsConfigDict(
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
Path(settings.EXPORTS_DIR).mkdir(exist_ok=True)
