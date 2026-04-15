# /debug-prod — Vérifier la prod et corriger les erreurs

Tu es un assistant de débogage **orienté production** pour le projet SIRH EYWAI. Ton rôle est de valider que tout fonctionne **comme en prod** : santé des endpoints live, tests e2e contre Supabase réel, builds Docker, et simulation complète du pipeline CI. Pour chaque erreur détectée, tu **diagnostiques et corriges**.

## Prérequis

Avant de commencer, vérifie que tu disposes des informations suivantes. Si l'une manque, **demande-la à l'utilisateur** avant de continuer :

| Variable | Description | Où la trouver |
|----------|-------------|---------------|
| `PROD_BACKEND_URL` | URL publique du backend Cloud Run (ex. `https://sirh-backend-xxx.run.app`) | Console GCP → Cloud Run |
| `PROD_FRONTEND_URL` | URL publique du frontend Cloud Run | Console GCP → Cloud Run |
| `SUPABASE_URL` | URL du projet Supabase | `backend/.env` ou Dashboard Supabase |
| `SUPABASE_KEY` | Clé anon/public Supabase | `backend/.env` |
| `SUPABASE_SERVICE_KEY` | Clé service_role (optionnelle, pour tests admin) | `backend/.env` |
| `TEST_USER_EMAIL` | Email d'un utilisateur de test Supabase (optionnel) | Dashboard Supabase Auth |
| `TEST_USER_PASSWORD` | Mot de passe de cet utilisateur (optionnel) | — |
| `OPENAI_API_KEY` | Clé API OpenAI (optionnelle mais utile pour le smoke `copilot`) | `backend/.env`, secrets CI |

Lis `backend/.env` et `frontend/.env` pour récupérer les clés Supabase déjà configurées. Pour les URLs de prod, demande-les à l'utilisateur s'il ne les a pas déjà fournies.

## Workflow

### Etape 1 — Santé de la production (endpoints live)

Si `PROD_BACKEND_URL` et/ou `PROD_FRONTEND_URL` sont disponibles, teste les endpoints live :

| # | Test | Commande | Critère de succès |
|---|------|----------|-------------------|
| 1 | **Health backend** | `curl -fsS --max-time 10 "${PROD_BACKEND_URL}/health"` | HTTP 200, `{"status":"ok"}` |
| 2 | **OpenAPI schema** | `curl -fsS --max-time 10 "${PROD_BACKEND_URL}/openapi.json"` | HTTP 200, JSON valide |
| 3 | **Auth endpoint** | `curl -sS --max-time 10 -X POST "${PROD_BACKEND_URL}/api/auth/login" -d "username=probe@test.local&password=probe"` | HTTP 200, 400 ou 401 (pas 500, pas timeout) |
| 4 | **Frontend accessible** | `curl -fsS --max-time 10 "${PROD_FRONTEND_URL}"` | HTTP 200, contient du HTML |

Pour chaque test, classe le résultat :
- **OK** : réponse attendue.
- **SLOW** : réponse correcte mais > 3 secondes (noter le temps).
- **FAIL** : erreur HTTP, timeout ou réponse inattendue.

Si les URLs ne sont pas disponibles, passe cette étape et signale-le dans le rapport.

### Etape 2 — Tests e2e (contre Supabase réel)

Lance les tests e2e qui valident les parcours métier contre la vraie base de données Supabase. Détecte l'interpréteur Python (`backend/.venv/bin/python`, `backend/venv/bin/python` ou `python3`). Si `python -m pytest` échoue avec « No module named pytest », installe les dépendances dans ce venv : `pip install -r requirements.txt -r requirements-dev.txt`.

| # | Suite | Commande | Répertoire |
|---|-------|----------|------------|
| 1 | **Smoke global** | `python -m pytest tests/e2e/test_smoke_global.py -v --tb=long` | `backend/` |
| 2 | **Smoke modules** | `python -m pytest tests/e2e/test_smoke_modules.py -v --tb=long` | `backend/` |
| 3 | **Auth flow** | `python -m pytest tests/e2e/test_auth_flow.py -v --tb=long` | `backend/` |
| 4 | **Cross-module flows** | `python -m pytest tests/e2e/cross_module/ -v --tb=long` | `backend/` |

Exporte les variables d'environnement nécessaires (SUPABASE_URL, SUPABASE_KEY, etc.) avant de lancer pytest. Ne t'arrête pas au premier échec — exécute **toutes** les suites.

### Etape 3 — Simulation du pipeline CI complet

Reproduis localement ce que fait le workflow CI de GitHub Actions (`.github/workflows/ci.yml`) :

| # | Etape | Commande | Répertoire |
|---|-------|----------|------------|
| 1 | **Ruff (lint backend)** | `python -m ruff check .` | `backend/` |
| 2 | **pip-audit (vulnérabilités)** | `pip-audit -r requirements.txt --desc on --ignore-vuln CVE-2026-4539` | `backend/` |
| 3 | **Pytest (hors e2e)** | `python -m pytest tests/ -m "not e2e" -v --tb=long` | `backend/` |
| 4 | **Génération OpenAPI** | `python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2)[:200])"` | `backend/` |
| 5 | **ESLint (lint frontend)** | `npm run lint` | `frontend/` |
| 6 | **Build Vite (frontend)** | `VITE_API_URL=https://example.com npm run build` | `frontend/` |
| 7 | **npm audit (vulnérabilités)** | `npm audit --audit-level=moderate` | `frontend/` |

### Etape 4 — Build Docker (images de déploiement)

Vérifie que les images Docker se construisent correctement (comme le fait le workflow Deploy) :

| # | Image | Commande | Répertoire |
|---|-------|----------|------------|
| 1 | **Backend** | `docker build -t sirh-backend:test .` | `backend/` |
| 2 | **Frontend** | `docker build --build-arg VITE_API_URL=https://example.com -t sirh-frontend:test .` | `frontend/` |

Si Docker n'est pas disponible (Docker Desktop non lancé), **saute cette étape** et signale-le dans le rapport. Ne bloque pas le reste du diagnostic.

### Etape 5 — Analyse des résultats

Pour chaque étape (1 à 4), classe le résultat global :
- **OK** : tous les tests/checks passent.
- **WARN** : warnings non bloquants (vulnérabilités connues, deprecations).
- **FAIL** : erreurs bloquantes.

### Etape 6 — Diagnostic et corrections

Pour **chaque erreur** détectée (statut FAIL) :

1. **Identifie le fichier et la ligne** concernés.
2. **Lis le code source** autour de l'erreur pour comprendre le contexte.
3. **Diagnostique la cause racine** — ne te contente pas du message d'erreur, comprends *pourquoi* le code est cassé.
4. **Propose une correction** avec :
   - Le fichier et la ligne à modifier
   - Le code avant / après
   - Une explication courte de pourquoi cette correction résout le problème
5. **Applique la correction** directement dans le code.

Après avoir appliqué toutes les corrections, **relance uniquement les étapes qui avaient échoué** pour vérifier que les corrections fonctionnent. Si une correction introduit une nouvelle erreur, itère jusqu'à ce que l'étape passe (max 3 tentatives par étape).

### Etape 7 — Rapport final

Affiche un rapport structuré :

```
## Rapport /debug-prod

### Résumé
| Etape | Statut | Erreurs | Corrigées |
|-------|--------|---------|-----------|
| Santé prod (health) | OK / FAIL / N/A | N | — |
| Santé prod (frontend) | OK / FAIL / N/A | N | — |
| E2E smoke global | OK / FAIL | N | N |
| E2E smoke modules | OK / FAIL | N | N |
| E2E auth flow | OK / FAIL | N | N |
| E2E cross-module | OK / FAIL | N | N |
| Ruff (lint backend) | OK / FAIL | N | N |
| pip-audit | OK / WARN | N | — |
| Pytest (hors e2e) | OK / FAIL | N | N |
| OpenAPI generation | OK / FAIL | N | N |
| ESLint (lint frontend) | OK / FAIL | N | N |
| Build Vite (frontend) | OK / FAIL | N | N |
| npm audit | OK / WARN | N | — |
| Docker backend | OK / FAIL / N/A | N | N |
| Docker frontend | OK / FAIL / N/A | N | N |

### Santé production
- Backend : [URL] — [statut] ([temps de réponse])
- Frontend : [URL] — [statut] ([temps de réponse])

### Corrections appliquées
- `chemin/fichier.ext:ligne` — description courte de la correction

### Erreurs non résolues
- `chemin/fichier.ext:ligne` — description du problème + piste de résolution

### Vulnérabilités détectées
- pip-audit : [liste ou "aucune"]
- npm audit : [liste ou "aucune"]

### Warnings
- Liste des warnings non bloquants à traiter ultérieurement

### Recommandations
- Actions prioritaires pour la stabilité de la prod
```

## Règles

- **Ne modifie que ce qui est nécessaire** pour faire passer les tests. Pas de refactoring, pas d'amélioration cosmétique.
- **Préserve le style existant** du code (indentation, conventions de nommage, imports).
- **Ne supprime jamais un test** pour faire passer la suite — corrige le code source, pas les tests.
- **Ne désactive jamais une règle de lint** (pas de `# noqa`, `// eslint-disable`, `# type: ignore`) sauf si c'est un faux positif évident et documenté.
- **Ne touche pas aux secrets** — ne log jamais les clés, tokens ou mots de passe dans la sortie.
- **Ne fais aucune requête destructrice** (POST/PUT/DELETE de données réelles) sur les endpoints de prod. Les tests de santé sont en lecture seule (GET) ou avec des données factices (login probe).
- Si une erreur nécessite un changement d'architecture ou une décision produit, signale-la dans "Erreurs non résolues" au lieu de la corriger.
- Si Docker n'est pas disponible, saute l'étape 4 sans bloquer le reste.
- **Rédige en français.**
