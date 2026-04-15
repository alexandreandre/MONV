# /update — Actualiser tous les fichiers sensibles aux changements

Tu es un assistant de maintenance documentaire et structurelle pour le projet SIRH EYWAI.

## Objectif

Parcourir **tous les fichiers du projet qui doivent rester synchronisés** avec l'état réel du code, puis les mettre à jour si nécessaire. Chaque fichier est comparé à l'état actuel du code source (modules, routes, pages, composants, etc.) et corrigé s'il est obsolète.

## Workflow

### Etape 1 — Audit

Lis l'état actuel du projet pour établir la **source de vérité** :

1. **Modules backend** : `ls backend/app/modules/` — liste exhaustive des domaines.
2. **Routeur API** : `backend/app/api/router.py` — tous les routers inclus et leurs prefixes.
3. **Routes frontend** : `frontend/src/App.tsx` — toutes les routes (collaborateur, RH, super-admin).
4. **Sidebar RH** : `frontend/src/components/ui/app-sidebar.tsx` — items `RH_HOME`, `RH_TEAM_BASE`, `RH_PAIE_ITEMS`, `menuItems`.
5. **Sidebar collaborateur** : `frontend/src/components/ui/employee-sidebar.tsx` — `baseNavItems` et items conditionnels.
6. **Navigation super-admin** : `frontend/src/pages/super-admin/SuperAdminLayout.tsx` — tableau `navigation`.
7. **Pages super-admin** : `ls frontend/src/pages/super-admin/` — fichiers présents.
8. **Support — modules** : `frontend/src/pages/support/SupportPage.tsx` — tableaux `MODULES`, `COMMON_TYPES`, `EXTRA_TYPES`, `URGENCY_LEVELS`, `MODULES_HAUTE_PRIORITE`.
9. **Support — filtres tickets** : `frontend/src/pages/support/TicketsHistoryPage.tsx` — `MODULE_OPTIONS`, `URGENCY_OPTIONS`, `STATUS_OPTIONS`.
10. **Constantes frontend** : `frontend/src/constants/contracts.ts` — `CONTRACT_TYPES`, `EMPLOYEE_STATUSES`.
11. **Onglets CSE** : `frontend/src/pages/CSE.tsx` — tabs et imports des sous-composants.
12. **Tests backend** : `ls backend/tests/` (unit, integration, e2e) — vérifier la couverture par module.
13. **Skills Claude Code** : `ls .claude/commands/` — liste des skills disponibles.
14. **Skills Cursor** : `ls .cursor/skills/` — liste des skills Cursor disponibles.
15. **Règles IA** : `.claude/rules/backend.mdc`, `.claude/rules/frontend.mdc`, `.cursor/rules/backend.mdc`, `.cursor/rules/frontend.mdc` — conventions actuelles.

### Etape 2 — Vérification et mise à jour des fichiers

Pour **chaque fichier** ci-dessous, compare son contenu actuel à la source de vérité de l'étape 1. Si un écart existe (module manquant, route absente, section obsolète, etc.), **modifie le fichier** pour le remettre en phase. Si le fichier est déjà à jour, passe au suivant sans le modifier.

---

#### A. Documentation (README)

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 1 | `README.md` (racine) | Sections "Fonctionnalités principales", "Structure du projet", "Statut du projet", "Dernière mise à jour" (mettre la date du jour). Vérifier que chaque module backend et chaque feature front est mentionné. |
| 2 | `backend/README.md` | Sections "Fonctionnalités principales" (un § par module), "Arborescence du projet" (liste des modules), endpoints principaux. Vérifier que chaque module sous `backend/app/modules/` a sa section. "Dernière mise à jour" → date du jour. |
| 3 | `backend/app/README.md` | Section "Structure des répertoires > modules/" — la liste doit correspondre à `ls backend/app/modules/`. |
| 4 | `frontend/README.md` | Sections "Fonctionnalités", "Arborescence", "Routing". Vérifier cohérence avec `App.tsx` et les pages existantes. |
| 5 | `backend/tests/README.md` | Vérifier que l'arborescence documentée correspond à `ls -R backend/tests/`. |
| 6 | `GUIDE-DEV.md` | Vérifier que les commandes et skills mentionnés existent toujours. |

#### B. Interface Super-Admin

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 7 | `frontend/src/pages/super-admin/SuperAdminLayout.tsx` | Le tableau `navigation` doit refléter toutes les pages existantes dans `frontend/src/pages/super-admin/`. Chaque page doit avoir une entrée, et aucune entrée ne doit pointer vers une page inexistante. |
| 8 | `frontend/src/App.tsx` (section super-admin) | Les `<Route>` sous `/super-admin` doivent correspondre aux pages existantes et aux imports en haut du fichier. |

#### C. Navigation & Sidebar

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 9 | `frontend/src/components/ui/app-sidebar.tsx` | `RH_TEAM_BASE` et `RH_PAIE_ITEMS` doivent lister toutes les pages RH existantes dans `App.tsx`. Pas d'entrée vers une page inexistante. |
| 10 | `frontend/src/components/ui/employee-sidebar.tsx` | `baseNavItems` doit lister toutes les pages collaborateur de `App.tsx`. |
| 11 | `frontend/src/App.tsx` (routes) | Toutes les pages importées doivent être utilisées dans des routes. Toutes les routes doivent avoir un import. |

#### D. Support

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 12 | `frontend/src/pages/support/SupportPage.tsx` | Le tableau `MODULES` doit refléter tous les modules du produit accessibles aux utilisateurs. Si un nouveau module a été ajouté (ex: badgeuse, CSE, recrutement, suivi médical), il doit avoir une entrée dans `MODULES`. |
| 13 | `frontend/src/pages/support/TicketsHistoryPage.tsx` | `MODULE_OPTIONS` doit correspondre exactement aux labels de `MODULES` dans `SupportPage.tsx`. |

#### E. Routeur API Backend

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 14 | `backend/app/api/router.py` | Chaque module sous `backend/app/modules/` qui expose un `api/router.py` doit être importé et inclus. Aucun import cassé (module supprimé). |

#### F. Tests

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 15 | `backend/tests/e2e/test_smoke_modules.py` | Doit contenir un test smoke pour chaque module exposé via le routeur API. Si un module a été ajouté, ajouter son test smoke. |

#### G. Constantes & Configuration

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 16 | `frontend/src/constants/contracts.ts` | `CONTRACT_TYPES` et `EMPLOYEE_STATUSES` — vérifier si de nouvelles valeurs apparaissent dans le code ou les schémas backend. |

#### H. Onglets CSE

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 17 | `frontend/src/pages/CSE.tsx` | Les tabs et imports doivent correspondre aux fichiers existants dans `frontend/src/pages/cse/`. |

#### I. Règles IA (Claude Code & Cursor)

Les fichiers `.claude/rules/` et `.cursor/rules/` doivent rester **synchronisés entre eux** (mêmes conventions) et **cohérents avec l'état réel du code**.

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 18 | `.claude/rules/backend.mdc` | Les conventions mentionnées (point d'entrée, couches d'import, logging, style, tests/CI) correspondent toujours à l'état réel du backend. Si de nouvelles conventions ont émergé (nouveaux outils, nouvelles couches, changement de structure), les ajouter. |
| 19 | `.claude/rules/frontend.mdc` | Les conventions mentionnées (stack, imports, UX/copie, lint) correspondent toujours à l'état réel du frontend. Vérifier que la stack mentionnée (React, Vite, TypeScript, Radix/shadcn) est toujours correcte et complète. |
| 20 | `.cursor/rules/backend.mdc` | Doit être **identique** à `.claude/rules/backend.mdc`. Si l'un a été modifié, reporter les changements dans l'autre. |
| 21 | `.cursor/rules/frontend.mdc` | Doit être **identique** à `.claude/rules/frontend.mdc`. Si l'un a été modifié, reporter les changements dans l'autre. |

#### J. Documentation de configuration IA

| # | Fichier | Quoi vérifier |
|---|---------|---------------|
| 22 | `.claude/README.md` | La structure documentée doit refléter le contenu réel de `.claude/` (rules, commands). Si des skills ou rules ont été ajoutés/supprimés, mettre à jour les sections correspondantes. |
| 23 | `.cursor/README.md` | La structure documentée doit refléter le contenu réel de `.cursor/` (rules, skills). Si des skills ou rules ont été ajoutés/supprimés, mettre à jour les sections correspondantes. |

---

### Etape 3 — Rapport

Après toutes les vérifications, affiche un **rapport concis** au format :

```
## Rapport /update

### Fichiers modifiés
- `chemin/fichier.ext` — description courte du changement

### Fichiers déjà à jour
- `chemin/fichier.ext` (liste groupée)

### Alertes
- Toute incohérence détectée mais non corrigible automatiquement (ex: test manquant nécessitant du code métier)
```

## Règles

- Ne modifie **que** ce qui est nécessaire pour remettre les fichiers en phase. Pas de refactoring, pas d'ajout de fonctionnalités.
- Préserve le style et le formatage existant de chaque fichier.
- Pour les README, mets à jour la date "Dernière mise à jour" avec le mois et l'année courants.
- Si un module backend existe mais n'a pas d'entrée dans le Support (`MODULES`), **ajoute-le** seulement s'il est pertinent pour l'utilisateur final (pas les modules purement techniques comme `access_control`, `uploads`, `dashboard`, `rates`, `super_admin`).
- Si tu détectes une incohérence que tu ne peux pas résoudre automatiquement (ex: une page importée dans App.tsx mais le fichier n'existe pas), signale-la dans les **Alertes** du rapport.
