# MONV — Prospection B2B conversationnelle

> Décris ton prospect idéal, obtiens une liste exploitable.  
> Assistant de prospection B2B ciblant les entreprises françaises (données publiques et enrichissement optionnel).

MONV est une application **full stack** : un chat guide la recherche, des modèles de langage structurent l’intention et planifient les appels aux APIs, puis les résultats s’affichent dans l’interface et peuvent être **exportés** (Excel ou CSV) selon un système de **crédits**.

---

## Sommaire 

- [Architecture du dépôt](#architecture-du-dépôt)
- [Prérequis](#prérequis)
- [Configuration Supabase](#configuration-supabase)
- [Variables d’environnement](#variables-denvironnement)
- [Démarrage en local](#démarrage-en-local)
- [Utilisation](#utilisation)
- [Pipeline côté backend](#pipeline-côté-backend)
- [Données et APIs externes](#données-et-apis-externes)
- [Crédits et export](#crédits-et-export)
- [Script autonome `prospection_pme.py`](#script-autonome-prospection_pmepy)
- [Stack technique](#stack-technique)


---

## Architecture du dépôt

```
MONV/
├── backend/                 # API FastAPI (Python)
│   ├── main.py              # Application, CORS, routers, /api/health, /api/templates
│   ├── config.py            # Paramètres (Pydantic Settings) + .env
│   ├── requirements.txt
│   ├── supabase/migrations/
│   │   └── 001_schema.sql   # Schéma PostgreSQL à exécuter dans Supabase
│   ├── models/
│   │   ├── db.py            # Client Supabase (service_role), accès tables
│   │   ├── entities.py      # Entités domaine
│   │   └── schemas.py       # Schémas Pydantic (API + pipeline)
│   ├── routers/
│   │   ├── auth.py          # Inscription, connexion, JWT, profil
│   │   ├── chat.py          # Envoi de messages, pipeline prospection
│   │   ├── search.py        # Historique, export, téléchargement fichiers
│   │   └── credits.py       # Packs de crédits (ajout manuel en dev)
│   ├── services/
│   │   ├── filter.py        # Couche 0 — filtre « in scope » (rapide)
│   │   ├── guard.py         # Couche 1 — intent + entités
│   │   ├── conversationalist.py  # QCM de clarification
│   │   ├── orchestrator.py  # Couche 2 — plan d’exécution API + coût crédits
│   │   ├── api_engine.py    # Couche 3 — SIRENE / Pappers / Google Places, fusion résultats
│   │   ├── sirene.py        # Recherche Entreprises (data.gouv.fr)
│   │   ├── pappers.py       # Enrichissement (clé optionnelle)
│   │   ├── google_places.py # Commerces de niche + recoupement SIRENE (clé optionnelle)
│   │   └── export.py        # Génération Excel / CSV
│   └── utils/
│       ├── llm.py           # Client OpenAI-compatible → OpenRouter
│       ├── pipeline_log.py  # Traces optionnelles [MONV.pipeline]
│       ├── cache.py         # Cache clé/valeur via table Supabase `cache`
│       └── credits_policy.py  # Comptes « crédits illimités » (liste e-mails config)
├── frontend/                # Next.js 15 (App Router)
│   ├── next.config.js         # Rewrite /api/* → backend :8000
│   └── src/
│       ├── app/               # layout, page principale
│       ├── components/        # Chat, tableau, auth, crédits, etc.
│       └── lib/api.ts         # Client HTTP + types
├── prospection_pme.py         # Script CLI hors MONV (dataset Excel via API gouv)
└── README.md
```

---

## Prérequis

- **Python** 3.11 ou supérieur (venv recommandé)
- **Node.js** 18 ou supérieur
- Un projet **[Supabase](https://supabase.com)** (gratuit suffisant pour le développement)
- Une clé **[OpenRouter](https://openrouter.ai)** pour les appels LLM (compatible client OpenAI)
- *(Optionnel)* une clé **[Pappers](https://www.pappers.fr/api)** pour dirigeants, CA, contacts enrichis

---

## Configuration Supabase

1. Crée un projet Supabase.
2. Dans **Settings → API**, récupère l’URL du projet, la clé **anon** (peu utilisée côté backend actuel) et surtout la clé **service_role** (réservée au serveur, jamais dans le frontend).
3. Ouvre **SQL Editor** et exécute une fois le fichier  
   `backend/supabase/migrations/001_schema.sql`  
   pour créer les tables : `users`, `conversations`, `messages`, `search_history`, `cache`.

Le backend parle à la base **uniquement via le client Supabase (PostgREST)** ; il n’y a pas de `DATABASE_URL` classique.

---

## Variables d’environnement

Fichier modèle : `backend/.env.example`. Copie-le en `backend/.env` et complète les valeurs.

| Variable | Obligatoire | Rôle |
|----------|-------------|------|
| `SUPABASE_URL` | Oui | URL du projet (`https://xxx.supabase.co`) |
| `SUPABASE_SERVICE_KEY` | Oui | Clé **service_role** (backend uniquement) |
| `SUPABASE_KEY` | Non | Clé anon (référence / usages futurs) |
| `OPENROUTER_API_KEY` | Oui | Appels LLM via OpenRouter |
| `FILTER_MODEL` | Non | Modèle couche 0 (défaut : `google/gemini-flash-1.5`) |
| `GUARD_MODEL` | Non | Modèle guard / clarification (défaut : `anthropic/claude-3.5-haiku`) |
| `ORCHESTRATOR_MODEL` | Non | Modèle orchestrateur (défaut : `anthropic/claude-3.5-sonnet`) |
| `PAPPERS_API_KEY` | Non | Enrichissement Pappers |
| `GOOGLE_PLACES_API_KEY` | Non | Découverte commerces (Places API) + lien SIRENE |
| `SITE_URL` | Non | Référent OpenRouter (défaut : `http://localhost:3000`) |
| `JWT_SECRET` | Fortement conseillé en prod | Secret de signature des JWT |
| `PIPELINE_DEBUG` | Non | `true` → logs détaillés `[MONV.pipeline]` sur stderr |
| `DEBUG` | Non | Mode debug FastAPI / comportements dev |

Les exports sont écrits dans le répertoire configuré par `EXPORTS_DIR` (défaut : `./exports` sous `backend/`).

---

## Démarrage en local

Lance **deux terminaux** : backend puis frontend. Le frontend proxifie les requêtes `/api/*` vers le port **8000** (`frontend/next.config.js`).

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Édite .env : Supabase + OpenRouter (+ Pappers si besoin)

uvicorn main:app --reload --port 8000
```

- API : `http://127.0.0.1:8000`  
- Swagger : `http://127.0.0.1:8000/docs`  
- Santé : `GET /api/health`  

Lance `uvicorn` depuis le dossier `backend/` pour que le fichier `.env` soit résolu correctement par `config.py`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- Interface : `http://localhost:3000`

Si tu changes le port du backend, mets à jour `destination` dans `frontend/next.config.js`.

---

## Utilisation

1. Ouvre `http://localhost:3000`.
2. Crée un compte ou connecte-toi (JWT stocké côté navigateur).
3. Les nouveaux comptes reçoivent **5 crédits** gratuits (`FREE_CREDITS` dans `config.py`).
4. Décris ta cible en langage naturel ou choisis un **modèle** proposé par l’API `GET /api/templates`.
5. Si les critères manquent, MONV peut afficher un **QCM de clarification**.
6. Après exécution du plan, un **aperçu** (jusqu’à 10 lignes) apparaît dans le chat ; l’export complet consomme les crédits indiqués pour la recherche.
7. L’**historique** des recherches est disponible côté API (`/api/search/history`) et dans l’UI (tableau de bord selon l’implémentation actuelle).
8. La page **Crédits** permet d’**ajouter** des crédits via un pack (simulation sans Stripe en développement).

---

## Pipeline côté backend

Le flux principal est dans `routers/chat.py` :

1. **Couche 0 — Filtre** (`services/filter`) : la requête est-elle dans le périmètre prospection B2B / outil ?
2. **Couche 1 — Guard** (`services/guard`) : intention structurée, entités, besoin de clarification.
3. **Couche 1b — Conversationalist** : génération d’un **QCM** si clarification nécessaire.
4. **Couche 2 — Orchestrateur** (`services/orchestrator`) : plan d’appels (SIRENE / Pappers), colonnes, **crédits estimés** ; peut redemander une clarification.
5. **Couche 3 — API Engine** (`services/api_engine`) : exécution déterministe, déduplication par SIREN, appels SIRENE / Pappers / **Google Places** selon le plan, enrichissements ciblés (dirigeants, finances, liens Maps).
6. Persistance : conversation, messages, ligne dans `search_history` avec `results_json` pour l’export ultérieur.

Les appels LLM passent par `utils/llm.py` (client **OpenAI** pointant sur **OpenRouter**).

---

## Données et APIs externes

| Source | Rôle |
|--------|------|
| **Recherche Entreprises** (`recherche-entreprises.api.gouv.fr`, paramétrée via `SIRENE_BASE_URL`) | Recherche gratuite : SIREN, NAF, localisation, effectifs, etc. |
| **Google Places (New)** | Optionnel (`GOOGLE_PLACES_API_KEY`) : commerces / points d’intérêt, fusion avec SIRENE pour SIREN officiel |
| **Pappers** | Optionnel : recherche enrichie, dirigeants, finances, signaux « contacts » selon le plan |

Sans clé Pappers ni Google Places, une grande partie des cas reste couverte par la base SIRENE / Recherche Entreprises.

---

## Crédits et export

Les règles de **coût en crédits** sont définies dans le prompt de l’orchestrateur (ordre de grandeur) :

- Recherche surtout SIRENE, moins de 100 résultats : **1** crédit  
- SIRENE + Pappers, moins de 500 résultats : **3** crédits  
- Enrichi + contacts, moins de 500 : **5** crédits  
- Recherche massive (plus de 500 résultats côté logique produit) : **10** crédits  

L’**export** (`POST /api/search/export`, formats `xlsx` ou `csv`) débite les crédits une première fois par recherche (tant que `exported` restait faux). Les fichiers sont servis via `GET /api/search/download/{filename}`.

---

## Script autonome `prospection_pme.py`

Script **hors stack MONV** : génère un fichier Excel de PME à partir de l’API publique Recherche d’entreprises, avec critères éditables en tête de fichier (`CONFIG`). Utile pour constituer un dataset brut sans passer par le chat.

```bash
pip install requests pandas openpyxl
python prospection_pme.py
```

---

## Stack technique

| Couche | Technologies |
|--------|----------------|
| Backend | FastAPI, Supabase Python client, Pydantic, JWT (python-jose), passlib/bcrypt, httpx, pandas/openpyxl |
| LLM | OpenRouter (API OpenAI-compatible) |
| Données | PostgreSQL hébergé par Supabase ; cache clé/valeur en table `cache` |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS, Lucide, react-markdown |

---

## Notes production

- Change `JWT_SECRET` et désactive les comportements de debug inadaptés.
- Remplace l’endpoint `POST /api/credits/add/{pack_id}` par un flux de paiement (ex. Stripe + webhook) si tu commercialises les packs.
- Renforce les règles **RLS** Supabase si tu exposes un jour la clé anon côté client ; aujourd’hui l’app métier s’appuie sur le backend et la **service_role**.

### CI/CD (GitHub → Google Cloud Run)

- **CI** : `.github/workflows/ci.yml` — tests pytest backend (sans Supabase), build Next.js, construction d’images Docker locales (sans push).
- **Déploiement** : `.github/workflows/deploy-gcp.yml` — sur chaque push sur `main` (ou déclenchement manuel), build et push des images vers **Artifact Registry**, déploiement de deux services **Cloud Run** (`monv-backend`, `monv-frontend`), puis mise à jour de `CORS_ORIGINS` et `SITE_URL` sur le backend avec l’URL du frontend.
- Variables d’environnement du backend côté Cloud Run : voir la liste des **secrets GitHub** attendus dans le guide de configuration fourni avec le dépôt (même ensemble que `backend/.env.example` pour les clés obligatoires).

---

*MONV — prospection B2B conversationnelle sur données France.*

**Dernière mise à jour :** avril 2026.
