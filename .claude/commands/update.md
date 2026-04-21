# /update — Actualiser les fichiers sensibles aux changements (MONV)

Tu es un assistant de **maintenance documentaire et structurelle** pour le dépôt **MONV** (API FastAPI + frontend Next.js App Router).

## Objectif

Parcourir les fichiers du projet qui doivent rester **alignés** sur le code réel (`backend/`, `frontend/`, migrations Supabase, règles IA, commandes), puis les corriger s’ils sont obsolètes.

## Étape 1 — Audit (source de vérité)

Établir l’état réel du dépôt :

1. **Routers FastAPI** : `backend/main.py` — `app.include_router(...)` et fichiers dans `backend/routers/`.
2. **Services** : fichiers `*.py` dans `backend/services/`.
3. **Migrations Supabase** : `backend/supabase/migrations/` (ordre d’exécution `001` → `002` → `003`…).
4. **Frontend App Router** : `frontend/src/app/` (`layout.tsx`, `page.tsx`).
5. **Composants & libs** : `frontend/src/components/`, `frontend/src/lib/` (notamment `api.ts`, `landingTemplates.ts`, `modes.ts`, `agents.ts`).
6. **Tests backend** : `backend/tests/` (`test_*.py`, `conftest.py`) et cohérence avec `.github/workflows/ci.yml`.
7. **Variables d’environnement** : `backend/.env.example` vs champs utilisés dans `backend/config.py`.
8. **Scripts optionnels** : `backend/benchmark_*.py`, `prospection_pme.py` à la racine si toujours présents.
9. **Commandes Claude Code** : `.claude/commands/` (liste des fichiers `.md`).
10. **Skills Cursor** : `.cursor/skills/*/SKILL.md`.
11. **Règles IA** : `.claude/rules/backend.mdc`, `.claude/rules/frontend.mdc`, `.cursor/rules/backend.mdc`, `.cursor/rules/frontend.mdc` — le contenu **backend** et **frontend** doit être **identique en paire** (`.claude` ↔ `.cursor`).

> **Note** : ce dépôt ne contient pas les chemins d’un autre produit (pas de `backend/app/modules/`, pas de `frontend/src/App.tsx` React Router, pas de pages RH / super-admin / support tickets). Si une consigne slash ou un README y fait référence, c’est une **erreur de modèle** : adapter la vérification à MONV.

## Étape 2 — Fichiers à vérifier et mettre à jour

Pour chaque fichier ci-dessous, comparer au résultat de l’étape 1. **Modifier** seulement en cas d’écart.

### A. Documentation racine

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 1 | `README.md` (racine) | Arborescence : tous les **routers**, **services** et **migrations** réels ; section Supabase (ordre des migrations) ; mention des parcours **modes**, **agent Atelier**, **projets** si présents dans le code ; **Dernière mise à jour** (date du jour). |

### B. Règles IA (Claude Code & Cursor)

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 2 | `.claude/rules/backend.mdc` | Point d’entrée, liste des dossiers, routers (y compris `agent`), services (y compris `modes`, `relevance`, `atelier_*`), logging, tests/CI — conformes au backend actuel. |
| 3 | `.claude/rules/frontend.mdc` | Stack réelle Next.js 15 App Router, React 19, Tailwind, shadcn/ui (Radix) si présent dans `package.json`, next-themes, Sonner, etc. ; pas de Vite ; qualité via `npm run build`. |
| 4 | `.cursor/rules/backend.mdc` | **Identique** à `.claude/rules/backend.mdc`. |
| 5 | `.cursor/rules/frontend.mdc` | **Identique** à `.claude/rules/frontend.mdc`. |

### C. Documentation de configuration IA

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 6 | `.claude/README.md` | Arborescence `.claude/commands/` et `.claude/rules/` ; résumés des `.mdc` cohérents avec les fichiers réels. |
| 7 | `.cursor/README.md` | Arborescence `.cursor/skills/` (un dossier par skill) et `rules/` ; résumés cohérents. |

### D. Cette commande elle-même

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 8 | `.claude/commands/update.md` | Le workflow décrit bien **MONV** (chemins et stacks réels), pas un autre projet. |

### E. Fichiers absents dans MONV (ne pas créer sans demande explicite)

Les fichiers suivants **n’existent pas** dans ce dépôt : `backend/README.md`, `backend/app/README.md`, `frontend/README.md`, `backend/tests/README.md`, `GUIDE-DEV.md`. Ne pas les inventer lors d’un `/update` sauf demande produit.

## Étape 3 — Rapport

Après vérifications, afficher un **rapport concis** :

```
## Rapport /update

### Fichiers modifiés
- `chemin/fichier.ext` — description courte

### Fichiers déjà à jour
- (liste groupée)

### Alertes
- Incohérences non corrigées automatiquement
```

## Règles

- Ne modifier **que** ce qui remet la doc ou les règles en phase avec le code ; pas de refactor ni nouvelle fonctionnalité.
- Préserver style et formatage existants.
- Pour les dates « Dernière mise à jour », utiliser la **date du jour** (jour/mois/année si le fichier le précise déjà ainsi).
