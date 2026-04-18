# Guide du dossier `.claude/`

Ce dossier contient la **configuration Claude Code** du dépôt : **commandes** (fichiers décrivant des workflows slash) et **règles** (conventions `.mdc` alignées sur celles de Cursor pour le même code).

Il complète le [`README.md`](../README.md) à la racine du dépôt. Les fichiers `AGENTS.md`, `CONTRIBUTING.md` ou `GUIDE-DEV.md` peuvent être ajoutés plus tard par l’équipe s’ils existent.

Pour l’équipe qui utilise **Cursor** en parallèle : règles équivalentes sous [`.cursor/rules/`](../.cursor/rules/) ; skills sous [`.cursor/skills/`](../.cursor/skills/) (voir [`.cursor/README.md`](../.cursor/README.md)).

---

## Structure du dépôt

```
.claude/
├── README.md              ← ce guide
├── rules/
│   ├── backend.mdc        ← conventions Python / FastAPI (`backend/`)
│   └── frontend.mdc       ← conventions Next.js / React / TS (`frontend/`)
└── commands/
    ├── commit.md
    ├── debug-local.md
    ├── debug-prod.md
    ├── merge-dev-to-main.md
    ├── security-check.md
    └── update.md
```

---

## Fichiers `rules/*.mdc`

Même contenu que **`.cursor/rules/`** pour `backend.mdc` et `frontend.mdc` : à modifier **en paire** si vous changez les conventions (voir tâche `/update` du projet).

| Fichier | Rôle |
|---------|------|
| `backend.mdc` | `main:app`, structure `routers/` (dont `agent`) / `services/` / `models/` (services : filtre, guard, conversationalist, modes, orchestrateur, APIs, signaux, géocodage, relevance, atelier, export), `pipeline_log`, tests pytest + CI sans Supabase réel. |
| `frontend.mdc` | Next.js 15 App Router, React 19, Tailwind, imports, textes UI en français, vérification via `npm run build`. |

---

## Fichiers `commands/*.md`

Procédures détaillées pour Claude Code (debug, merge, sécurité, synchronisation doc, etc.). Les noms correspondent aux **commandes slash** configurées côté Claude Code pointant vers ces fichiers.

| Commande (fichier) | Usage typique |
|-------------------|----------------|
| `commit.md` | Aide à la préparation de commits / messages. |
| `debug-local.md` / `debug-prod.md` | Diagnostic environnement local ou production. |
| `merge-dev-to-main.md` | Intégration branche perso → `main`. |
| `security-check.md` | Revue sécurité ciblée. |
| `update.md` | Actualiser doc, navigation, smoke tests et cohérence repo. |

---

**Maintenance** : après ajout ou suppression d’un fichier sous `.claude/commands/` ou `.claude/rules/`, mettre à jour la section **Structure** de ce README.
