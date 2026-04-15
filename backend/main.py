from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import settings
from models.db import get_supabase, verify_connection


def _cors_allow_origins() -> list[str]:
    raw = (settings.CORS_ORIGINS or "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    site = (settings.SITE_URL or "").strip().rstrip("/")
    if site and site not in origins:
        origins.append(site)
    return origins
from routers import auth, chat, search, credits
from utils.pipeline_log import configure_pipeline_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_pipeline_logging()
    Path(settings.EXPORTS_DIR).mkdir(parents=True, exist_ok=True)
    if not settings.SKIP_DB_VERIFY_ON_STARTUP:
        await verify_connection(get_supabase())
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Trouvez n'importe quelle entreprise en France : clients, prestataires, fournisseurs, partenaires.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(credits.router)

exports_path = Path(settings.EXPORTS_DIR)
exports_path.mkdir(exist_ok=True)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "pipeline_debug": settings.PIPELINE_DEBUG,
    }


@app.get("/api/templates")
async def get_templates():
    return [
        {
            "id": "startup-saas-paris",
            "title": "Startups SaaS à Paris",
            "description": "Startups SaaS de 10 à 50 salariés basées à Paris, créées depuis 2020",
            "query": "Je cherche des startups SaaS à Paris, entre 10 et 50 salariés, créées depuis 2020",
            "icon": "rocket",
        },
        {
            "id": "prestataire-informatique",
            "title": "Prestataire informatique",
            "description": "ESN et agences de développement en Île-de-France",
            "query": "Je cherche un prestataire informatique en Île-de-France, ESN ou agence de développement",
            "icon": "monitor",
        },
        {
            "id": "fournisseur-btp",
            "title": "Fournisseurs BTP",
            "description": "Fournisseurs de matériaux de construction en France",
            "query": "Trouve-moi des fournisseurs de matériaux de construction, PME avec plus de 10 salariés",
            "icon": "truck",
        },
        {
            "id": "cabinet-comptable",
            "title": "Cabinets comptables à Lyon",
            "description": "Experts-comptables et cabinets d'audit à Lyon et alentours",
            "query": "Je cherche un cabinet comptable ou expert-comptable à Lyon",
            "icon": "calculator",
        },
        {
            "id": "pme-industrielles-rhone-alpes",
            "title": "PME industrielles Rhône-Alpes",
            "description": "PME industrielles en Auvergne-Rhône-Alpes avec CA > 1M\u202f€",
            "query": "Trouve-moi des PME industrielles en Rhône-Alpes avec un chiffre d'affaires supérieur à 1 million d'euros",
            "icon": "factory",
        },
        {
            "id": "agence-communication",
            "title": "Agences de communication",
            "description": "Agences de pub, marketing et communication à Bordeaux",
            "query": "Je cherche des agences de communication et marketing à Bordeaux",
            "icon": "megaphone",
        },
        {
            "id": "btp-marseille",
            "title": "Entreprises BTP à Marseille",
            "description": "Entreprises du BTP à Marseille, 20 à 200 salariés",
            "query": "Je cherche des entreprises du BTP à Marseille entre 20 et 200 salariés",
            "icon": "building",
        },
        {
            "id": "cabinet-avocats",
            "title": "Cabinets d'avocats à Paris",
            "description": "Cabinets d'avocats spécialisés en droit des affaires à Paris",
            "query": "Trouve-moi des cabinets d'avocats en droit des affaires à Paris",
            "icon": "scale",
        },
    ]
