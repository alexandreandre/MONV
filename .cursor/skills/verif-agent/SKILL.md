---
name: verif-agent
description: Audite la composition complète d’un agent MONV (prospection, rachat, benchmark, sous_traitant, atelier) comme un expert — prompts, modes, colonnes, pipeline, graphe admin, overrides Supabase, cohérence front/back — et liste tous les problèmes par gravité. À utiliser quand l’utilisateur tape /verif-agent, demande une vérification d’agent, un audit de prompt, ou attache explicitement ce skill.
disable-model-invocation: true
---

# /verif-agent — Audit composition d’agent MONV

## Quand s’appliquer

Dès que l’utilisateur nomme un **agent** à auditer parmi : **prospection**, **rachat**, **benchmark**, **sous-traitant** (ou synonymes ci-dessous), **création d’entreprise** / **atelier**. Objectif : **relever tous les problèmes** (incohérences, trous, risques produit, dette technique, divergence front/back, JSON/schema, perf/coût, légalité des formulations).

## Normalisation des identifiants

| Entrée utilisateur | `agent_id` / mode code |
|--------------------|-------------------------|
| prospection | `prospection` |
| rachat | `rachat` |
| benchmark | `benchmark` |
| sous-traitant, sous traitant, fournisseurs (legacy) | `sous_traitant` |
| atelier, création d’entreprise, agent création d’entreprise | `atelier` |

Si l’identifiant est ambigu, demander une précision en une phrase ; sinon appliquer ce tableau.

## Méthode (obligatoire)

1. **Cartographier** l’agent avec le code : ne pas improviser hors dépôt.
2. **Lire en parallèle** les zones pertinentes (grep ciblé + lectures ciblées), pas seulement un fichier.
3. **Traverser la chaîne complète** pour cet agent : UI → requêtes API → router → services (filtre, guard, conversationaliste, orchestrateur, moteur, pertinence, signaux, enrichissements, atelier si `atelier`) → schémas → registre graphe → overrides DB.
4. **Comparer** : `backend/services/modes.py` ↔ `frontend/src/lib/modes.ts` (pour les 4 modes) ; libellés admin ↔ `MODE_LABELS` / `AGENT_IDS`.
5. **Vérifier** s’il existe une version active Supabase (`agent_versions.overrides_json` par `agent_id`) — schéma `backend/supabase/migrations/004_admin_agents.sql`, résolution dans `backend/services/agent_config.py`.
6. **Conclure** avec le format de sortie ci-dessous ; rien n’est « hors sujet » si ça impacte le comportement ou la promesse produit de l’agent.

## Périmètre « composition entière » (checklist)

Cocher mentalement chaque axe ; documenter toute anomalie.

### A. Identité & surface produit

- Libellés, placeholders, descriptions (front) pour ce mode / atelier.
- Cohérence ton et promesse (prospection vs prestataire vs benchmark vs rachat vs atelier).

### B. Mode & orchestration (`agent_id` = mode pour le chat)

- `MODE_ORCHESTRATOR_ADDENDUM`, `MODE_PRIORITY_COLUMNS`, `apply_result_columns_for_mode`, `credits_floor_for_mode` dans `backend/services/modes.py`.
- Injection addendum + colonnes dans `backend/services/orchestrator.py` et consommateurs (`chat`, export, relevance).
- Règles spécifiques mode dans l’API engine (ex. remplacement Pappers, signaux) — grep le `mode` ou `agent_id`.

### C. Couches LLM partagées (overrides par bloc)

Blocs typiques : `filter`, `guard`, `orchestrator`, `conversationalist`, `relevance`, enrichissements, blocs atelier. Pour chaque appel `resolve_llm_for_block(..., agent_id=...)` : le **même** `agent_id` que le mode est-il bien passé ? Y a-t-il des defaults hardcodés (`"prospection"`) qui court-circuitent l’agent demandé ?

### D. Guard & intents

- Instructions contradictoires entre `guard.py` et l’addendum orchestrateur pour ce mode (ex. zone, `mots_cles`, Pappers).
- Cas tests dans `backend/tests/` qui verrouillent le comportement (ex. clarification QCM / rachat).

### E. Données, colonnes, export

- Colonnes promises dans l’addendum vs colonnes réellement produites / exportées.
- Mode prospection : `PROSPECTION_RESULT_COLUMNS` (liste figée).

### F. Signaux & sources externes

- `signals.py`, BODACC, marchés publics, etc. — activation ou silence selon le mode (ex. rachat).

### G. Agent `atelier` (création d’entreprise)

- `backend/services/agent_registry.py` (`AGENT_IDS`, `build_chat_graph`, graphe atelier).
- Services `atelier_*`, routers, composants `frontend/src/components/Atelier*.tsx`, métadonnées `AGENT_META.atelier`.
- Modèles dédiés `ATELIER_*` dans `backend/config.py` si présents.

### H. Admin & observabilité

- Endpoint graphe `/api/admin/...` (cf. `backend/routers/admin.py`) et cohérence avec `agent_registry.py`.
- Tables `agent_versions`, `agent_runs`, `agent_run_steps` — traçabilité des blocs.

### I. Tests & CI

- Tests qui couvrent ce mode ; gaps manifestes.

### J. Sécurité & conformité produit

- Formulations interdites (conseil en investissement, valorisation) pour rachat ; données personnelles ; fuites de prompt.

## Format de sortie (obligatoire, en français)

1. **Résumé exécutif** (3–6 phrases) : état global de l’agent.
2. **Tableau ou liste des problèmes** triés par gravité :
   - **Critique** — casse fonctionnel, régression, incohérence majeure promesse/réalité, risque légal fort.
   - **Important** — bug partiel, mauvaise UX, divergence front/back, coût/crédits incohérents.
   - **Suggestion** — dette, lisibilité, micro-copies, tests manquants non bloquants.
3. Pour **chaque** problème : **symptôme**, **cause probable** (fichier ou zone), **impact utilisateur**, **piste de correction** (sans implémenter sauf demande).
4. **Fichiers consultés** (liste courte, chemins relatifs au repo).
5. Si des zones n’ont pas pu être vérifiées (secrets, DB distante) : section **Inconnu / à valider manuellement**.

## Fichiers pivots (point de départ grep/read)

- `backend/services/modes.py`
- `backend/services/agent_registry.py`
- `backend/services/agent_config.py`
- `backend/routers/chat.py`
- `backend/services/orchestrator.py`, `guard.py`, `filter.py`, `conversationalist.py`, `relevance.py`
- `frontend/src/lib/modes.ts`, `frontend/src/components/Sidebar.tsx`, `frontend/src/app/admin/modes/`
- `backend/supabase/migrations/004_admin_agents.sql`

## Règles de qualité d’audit

- Être **exhaustif** sur la composition ; ne pas se limiter aux prompts système.
- Citer le code avec le format projet : blocs ```startLine:endLine:chemin``` lorsque une preuve précise est nécessaire.
- Ne pas confondre **mode** et **feature** non liée ; rester centré sur l’agent demandé.
- Si l’utilisateur fournit une **version** ou un **diff** précis, prioriser cette portée puis élargir si pertinent.

## Exemple d’invocation

> « /verif-agent benchmark »  
→ Normaliser `benchmark`, exécuter la méthode, sortie structurée avec Critique / Important / Suggestion.
