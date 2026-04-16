# Guide du dossier `.cursor/`

Ce dossier contient la **configuration Cursor** propre au dépôt : règles que l’agent et l’IA utilisent pour rester alignés avec la stack et les conventions du projet.

Il complète (sans les remplacer) le [`README.md`](../README.md) à la racine ; d’autres guides (`AGENTS.md`, `CONTRIBUTING.md`, README par app) peuvent être ajoutés par l’équipe s’ils existent.

---

## Vue d’ensemble

| Objectif | Détail |
|----------|--------|
| Contexte persistant | Les règles `.mdc` sont prises en compte par Cursor selon leur portée (`globs`, `alwaysApply`). |
| Cohérence | Même stack, mêmes interdits que la doc du repo. |
| Moins de répétition | Pas besoin de recoller les conventions à chaque conversation si les bons fichiers sont dans le contexte. |

**Ce que ce dossier ne remplace pas** : paramètres globaux de l’éditeur, hooks Git (commitlint, pre-commit), CI.

---

## Structure du dépôt

```
.cursor/
├── README.md              ← ce guide (documentation humaine)
├── rules/
│   ├── backend.mdc        ← règle IA : backend/
│   └── frontend.mdc       ← règle IA : frontend/
└── skills/                 ← skills Agent (fichiers SKILL.md par dossier)
    ├── begin/
    ├── check-feature/
    ├── commit/
    ├── debug/
    ├── enhance/
    ├── enhance-fonctionnality/
    ├── etat/
    ├── frontend-design/
    ├── merge-dev-to-main/
    ├── propose-fonctionnality/
    ├── push/
    ├── smartphone-adapting/
    └── test/
```

---

## Fichier par fichier : comment l’utiliser

### 1. `README.md` (ce fichier)

| | |
|--|--|
| **Nature** | Documentation **Markdown** pour les humains. Ce n’est **pas** une règle `.mdc` : Cursor ne l’applique pas automatiquement comme une *rule* avec frontmatter. |
| **À qui ça sert** | Contributeurs, revue de config, onboarding sur « comment marche `.cursor/` dans ce repo ». |
| **Quand le lire** | Avant d’ajouter une règle, quand on ne comprend pas pourquoi l’IA se comporte d’une certaine façon sur `backend/` vs `frontend/`, ou pour maintenir les `.mdc`. |
| **Ce que vous faites** | Ouvrir ce fichier dans l’IDE ou sur GitHub ; le mettre à jour quand vous changez la structure de `.cursor/` ou les conventions décrites. |
| **Ce que vous ne faites pas** | Ne pas s’attendre à ce qu’il soit injecté comme une règle projet au même titre qu’un `.mdc` (sauf si vous l’ajoutez vous-même au contexte du chat, par ex. avec `@README.md`). |
| **Maintenance** | Si vous créez un nouveau `.mdc` ou renommez des fichiers, ajoutez une entrée dans la section « Fichier par fichier » ci-dessous. |

---

### 2. `rules/backend.mdc`

| | |
|--|--|
| **Nature** | Règle projet au format **`.mdc`** (YAML + Markdown). Contient les conventions Python / FastAPI pour tout ce qui est sous `backend/`. |
| **Contenu actuel (résumé)** | Point d’entrée `main:app`, dossiers `routers/` / `services/` / `models/` / `utils/` (services incl. conversationalist, signaux, géocodage), logging pipeline (`pipeline_log`), tests pytest + CI sans Supabase réel, français pour les messages utilisateur, migrations sous `supabase/migrations/`. |
| **Frontmatter actuel** | `globs: backend/**`, `alwaysApply: false`. |

**Comment Cursor l’utilise**

- Avec **`alwaysApply: false`**, la règle est associée aux chemins qui matchent `backend/**` (racine du workspace = racine du dépôt).
- Elle est typiquement **prise en compte** quand vous travaillez sur des fichiers dans `backend/` (fichiers ouverts, fichiers modifiés, ou contexte Agent centré sur ce dossier). Le comportement exact peut varier selon la version de Cursor ; en cas de doute, inclure un fichier sous `backend/` dans le contexte ou mentionner `@backend.mdc` dans le chat.

**Ce que vous faites en pratique**

- Développer ou faire réviser du code Python/FastAPI dans `backend/` : vous n’avez **rien d’obligatoire** à faire de plus — la règle aide l’agent à suivre les conventions.
- Pour **forcer** le contexte : dans le chat, vous pouvez référencer explicitement la règle ou un fichier du backend (ex. `@.cursor/rules/backend.mdc` ou un fichier `.py` sous `backend/`).

**Ce que vous ne faites pas**

- Ne pas dupliquer tout le README racine dans ce fichier : la règle reste un **rappel ciblé** ; le détail d’architecture est dans le [`README.md`](../README.md) du dépôt.

**Quand modifier ce fichier**

- Changement de conventions backend (imports, logging, langue des messages, politique DB) qui doit être rappelé à chaque session sur `backend/`.
- Lors de l’édition : vérifier que le frontmatter reste valide (`description`, `globs`, `alwaysApply`).

---

### 3. `rules/frontend.mdc`

| | |
|--|--|
| **Nature** | Règle projet **`.mdc`** pour tout ce qui est sous `frontend/`. |
| **Contenu actuel (résumé)** | Next.js 15 App Router, React 19, TypeScript, Tailwind, imports, pas de gros refactors hors demande, textes UI en français ; qualité via `npm run build` (pas de script `lint` npm actuellement). |
| **Frontmatter actuel** | `globs: frontend/**`, `alwaysApply: false`. |

**Comment Cursor l’utilise**

- Même logique que `backend.mdc` : `globs: frontend/**` et `alwaysApply: false` → la règle s’applique au contexte des fichiers sous `frontend/`.

**Ce que vous faites en pratique**

- Travailler sur l’app React dans `frontend/` : l’agent s’appuie sur cette règle quand le contexte inclut des fichiers concernés.
- Pour **forcer** : `@.cursor/rules/frontend.mdc` ou un fichier sous `frontend/` dans le message.

**Ce que vous ne faites pas**

- Ne pas y mettre la doc exhaustive de chaque composant : lien vers `frontend/README.md` si besoin.

**Quand modifier ce fichier**

- Nouvelles conventions UI, stack front, ou règles de copie / lint spécifiques au dossier `frontend/`.

---

### 4. Dossier `skills/` (Agent Skills)

| | |
|--|--|
| **Nature** | Un dossier par intention (`begin`, `push`, `debug`, `test`, etc.) contenant un fichier **`SKILL.md`** : consignes réutilisables pour l’agent (Git, CI, design, etc.). |
| **Quand l’utiliser** | Attacher le skill dans le chat ou invoquer la commande slash associée (ex. `/begin`, `/push`, `/debug`) si elle est configurée dans Cursor. |
| **Maintenance** | Ajouter un sous-dossier `nom-du-skill/SKILL.md` puis mettre à jour l’arborescence en tête de ce README. |

---

## Format technique des `.mdc` (rappel)

Chaque fichier dans `rules/` commence par un **frontmatter YAML**, puis du Markdown.

| Champ | Rôle |
|-------|------|
| `description` | Court résumé (souvent affiché dans l’UI des règles). |
| `globs` | Motif de chemins, ex. `backend/**` — limite la règle à cette zone si `alwaysApply` est `false`. |
| `alwaysApply` | `true` = chargé pour toutes les conversations ; `false` = dépend du contexte / des `globs`. Dans ce dépôt, les deux règles sont en `false`. |

Exemple minimal pour une **nouvelle** règle par zone :

```yaml
---
description: Ce que la règle impose ou rappelle
globs: chemin/vers/la-zone/**
alwaysApply: false
---

# Titre

Corps en Markdown.
```

---

## Ajouter une nouvelle règle (nouveau fichier `.mdc`)

1. Créer un fichier `.cursor/rules/nom-explicite.mdc`.
2. Renseigner `description`, `globs` (et `alwaysApply: true` seulement si vraiment transverse).
3. Rédiger le corps : rappels actionnables + liens vers la doc du dépôt.
4. **Mettre à jour ce `README.md`** : ajouter une sous-section « Fichier par fichier » pour le nouveau fichier.
5. Vérifier la cohérence avec le [`README.md`](../README.md) racine et les règles jumelles sous `.claude/rules/` si elles existent.

---

## Relation avec le reste du dépôt

| Fichier / zone | Rôle |
|----------------|------|
| [`README.md`](../README.md) | Vue d’ensemble du dépôt MONV ; les `.mdc` résument les conventions par dossier. |
| `.github/` | Workflows et prompts GitHub Actions ; indépendant des règles Cursor locales. |

---

## Dépannage

| Problème | Piste |
|----------|--------|
| La règle backend/frontend ne semble pas suivie | Vérifier que des fichiers sous `backend/` ou `frontend/` sont bien dans le contexte ; référencer explicitement `@.cursor/rules/<fichier>.mdc` ou un fichier du bon dossier. |
| `globs` incorrect | Les chemins sont relatifs à la **racine du workspace** (souvent la racine du repo). |
| Contradiction entre règles et doc | Mettre à jour le README canonique **et** le `.mdc` concerné (ainsi que `.claude/rules/` en miroir). |

---

## Résumé

| Fichier | Utilisation |
|---------|-------------|
| **`README.md`** | Lire pour comprendre et maintenir `.cursor/` ; mettre à jour quand la structure ou les fichiers changent. |
| **`rules/backend.mdc`** | S’applique au contexte `backend/**` ; rien d’obligatoire côté dev au quotidien ; modifier si les conventions backend évoluent. |
| **`rules/frontend.mdc`** | S’applique au contexte `frontend/**` ; idem pour le front. |
| **`skills/*/`** | Workflows Agent (Git, tests, debug, design…) : consulter ou attacher le `SKILL.md` du dossier concerné. |

Pour toute évolution majeure des conventions : mettre à jour le **README** (racine ou apps) et les **`.mdc`** correspondants (`.cursor` et `.claude` en parallèle).
