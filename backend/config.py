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
    # Erreur LLM / JSON sur le filtre : fail_open (dev), fail_closed (tout rejeter),
    # heuristic_then_closed (second seuil léger puis hors-scope si doute).
    FILTER_LLM_ERROR_POLICY: str = "fail_open"
    # Si True : court-circuit run_filter (pas d'appel LLM) quand l'heuristique locale est très confiante
    FILTER_HEURISTIC_SHORT_CIRCUIT: bool = True
    # Limite /api/chat/send par utilisateur (fenêtre glissante, mémoire process).
    CHAT_SEND_RATE_LIMIT_ENABLED: bool = True
    CHAT_SEND_RATE_LIMIT_MAX_REQUESTS: int = 40
    CHAT_SEND_RATE_LIMIT_WINDOW_S: int = 60
    # Limite ``POST /api/search/estimate`` (fenêtre glissante, mémoire process).
    SEARCH_ESTIMATE_RATE_LIMIT_ENABLED: bool = True
    SEARCH_ESTIMATE_RATE_LIMIT_MAX_REQUESTS: int = 80
    SEARCH_ESTIMATE_RATE_LIMIT_WINDOW_S: int = 60
    # Couche 1 / 1b — Guard extraction + Conversationalist (coût moyen)
    GUARD_MODEL: str = "anthropic/claude-3.5-haiku"
    # Guard : second passage « ambiguïté sectorielle » (prompt long) si détecteur lexical
    GUARD_SECTOR_AMBIGUITY_SECOND_PASS: bool = True
    # Couche 2 — Orchestrateur plan d'exécution (le meilleur, précis)
    ORCHESTRATOR_MODEL: str = "anthropic/claude-3.5-sonnet"
    # Post-filtrage des lignes de résultats (rapide, JSON fiable via OpenRouter)
    RELEVANCE_FILTER_MODEL: str = "openai/gpt-4o-mini"
    # Enrichissement « pitch digital » (prospection) ; si vide → RELEVANCE_FILTER_MODEL
    DIGITAL_PITCH_ENRICH_MODEL: str = ""
    # Atelier — planification + dossier business (2 appels LLM). Si vide → ORCHESTRATOR_MODEL.
    ATELIER_BUSINESS_MODEL: str = ""
    # Atelier fake (dev UI) : aucun appel LLM/API, réponses déterministes.
    ATELIER_FAKE_MODE: bool = False

    # ── APIs externes ─────────────────────────────────────────────
    PAPPERS_API_KEY: str = ""
    SIRENE_BASE_URL: str = "https://recherche-entreprises.api.gouv.fr/search"
    GOOGLE_PLACES_API_KEY: str = ""
    PAPPERS_BASE_URL: str = "https://api.pappers.in/v1"
    PAPPERS_COUNTRY_CODE: str = "FR"
    # Max fiches Pappers pour compléter téléphone/site (lignes déjà complètes sont ignorées)
    PAPPERS_CONTACT_ENRICH_MAX: int = 60

    # ── App ───────────────────────────────────────────────────────
    CACHE_TTL_HOURS: int = 48
    MAX_RESULTS_PER_QUERY: int = 150
    FREE_PREVIEW_ROWS: int = 10
    FREE_CREDITS: int = 5

    # Emails (séparés par des virgules) : pas de débit à l'export, solde API affiché comme illimité
    UNLIMITED_CREDITS_EMAILS: str = ""

    # Accès `/api/admin/*` et interface `/admin` (emails, séparés par des virgules, insensible à la casse)
    ADMIN_EMAILS: str = ""

    # Enregistrer chaque étape LLM dans agent_runs / agent_run_steps (impact perf — désactivé par défaut)
    RUN_RECORDING_ENABLED: bool = False
    # Journaliser usage tokens (OpenRouter / OpenAI) sur stderr via logging ``monv.llm``
    LLM_USAGE_LOG_ENABLED: bool = True

    # Cache lecture overrides actifs (secondes)
    AGENT_CONFIG_CACHE_SECONDS: float = 30.0

    # Métriques pipeline chat (anneau mémoire, voir ``utils/pipeline_timing.py``)
    PIPELINE_TIMING_MAX_SAMPLES: int = 500

    # Cache connecteurs SIRENE / Google Places (process-local, TTL court)
    CONNECTOR_CACHE_ENABLED: bool = True
    CONNECTOR_CACHE_TTL_S: float = 300.0
    CONNECTOR_CACHE_MAX_KEYS: int = 256

    # Jobs chat async (spike : anneau mémoire, voir ``services/chat_async_jobs.py``)
    CHAT_ASYNC_JOBS_MAX: int = 200
    CHAT_ASYNC_JOB_RESULT_TTL_S: float = 3600.0

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
