# Atelier MONV — refonte progressive (v2)

Ce document suit la refonte de l’Agent Atelier. **Phase 1 (backend)** : correctifs budget, périmètre des segments, pertinence exposée sur chaque ligne de prévisualisation, tags multi-segments après fusion, totaux dossier.

## Schémas (`backend/models/schemas.py`)

- `ProjectBrief` : `budget_min_eur`, `budget_max_eur`, `budget_hypotheses` ; le texte `budget` accepte jusqu’à 400 caractères (phrase complète).
- `SegmentBrief` / `SegmentResult` : `out_of_scope`, `out_of_scope_note` ; `total_relevant`, `relevance_threshold` sur le résultat.
- `BusinessDossier` : `version`, `generated_at`, `total_raw`, `total_unique`, `total_relevant`, `total_credits` (valeurs par défaut rétrocompatibles).

## Pertinence (`backend/services/relevance.py`)

- `compute_relevance_scores` : calcule notes 0–10 et seuil sans filtrer la liste.
- `filter_results_by_relevance` (chat) : réutilise ce calcul ; comportement inchangé pour l’API chat.
- `relevance_flag_for_score` / `relevance_reason_excluded_fr` : classification pour l’UI Atelier.

## Agent Atelier (`backend/services/agent.py`)

- Chaque ligne de `preview` inclut `_dedup_key`, `relevance_score` (0–1), `relevance_flag` (`ok` | `warning` | `excluded`), `reason_excluded`, `segments` (mono-segment puis enrichi).
- `merge_atelier_cross_segment_tags` : union des `segment_key` par entreprise.
- `atelier_dossier_rollup_fields` : agrégats pour le dossier.
- Segments `out_of_scope` : aucun appel Guard / pipeline ; message explicite côté `SegmentResult`.
- Prévisualisation plafonnée à 400 lignes par segment (`_ATELIER_PREVIEW_MAX_ROWS`).

## Router (`backend/routers/agent.py`)

- Après les recherches : fusion des tags inter-segments, remplissage des totaux et `generated_at` sur `BusinessDossier`.

## Anciens dossiers

À la lecture, les champs absents sont hydratés par les **défauts Pydantic** (`version=1`, totaux à 0, pas de champs pertinence sur les lignes d’historique). Le front peut traiter l’absence de `relevance_flag` comme affichage neutre.

## Phase 2 — Quick wins UI (historique)

- Bandeau **Synthèse express** : 3 cartes Force / Risque / Action.
- **Pertinence** et **Segments** dans `ResultsTable` : badges, tags multi-segments, masquage des lignes `excluded` avec lien pour les réafficher.
- **Exporter tout le dossier** : enchaîne les exports Excel segment par segment (`handleExportAllAtelier` dans `page.tsx`).
- Totaux dossier et budget structuré dans le header quand l’API les fournit.

## Phase 3 — itération dossier (API)

Toutes les routes sont sous **`/api/agent`**, authentification Bearer comme le reste de l’API.

### `GET /api/agent/dossier/{conversation_id}`

Retourne le **dernier** message dossier de la conversation Atelier.

- **Réponse** : `{ "message_id": "<uuid>", "dossier": { ... } }` où `dossier` est le JSON métier (même forme que `metadata_json` parsé d’un `business_dossier`).
- **404** si la conversation n’existe pas, n’est pas en mode atelier, ou aucun dossier n’a encore été généré.

### `POST /api/agent/segments/{segment_key}/regenerate`

Relance le pipeline MONV pour **un** segment (clé d’URL = `key` du segment, insensible à la casse).

- **Corps** : `{ "conversation_id": "...", "query_override"?: string, "mode_override"?: string }`
- **Crédits** : 1 crédit par appel si l’utilisateur n’est pas illimité ; segment `out_of_scope` → **400**.
- **Réponse** : `AtelierDossierMutationResponse` (`dossier` complet mis à jour, `generation_stats`, `credits_remaining`).

### `POST /api/agent/canvas/regenerate`

Régénère uniquement le **canvas** BMC (LLM), incrémente `version` / `generated_at`.

- **Corps** : `{ "conversation_id": "..." }`
- **Réponse** : `AtelierDossierMutationResponse`.

### `POST /api/agent/brief/update`

Applique un nouveau **`brief`**, puis recalcule les zones listées dans **`impacts`** (au moins une).

- **Corps** : `{ "conversation_id": "...", "brief": ProjectBrief, "impacts": ["canvas"|"flows"|"segments", ...] }`
- **`segments`** : relance toutes les recherches segment, fusion des tags, rollups, une montée de version.
- **Sans `segments`** : fusion / rollups sur les segments existants + une montée de version (canvas et/ou flows régénérés si demandés).

Client TypeScript : `getAtelierDossier`, `regenerateAtelierSegment`, `regenerateAtelierCanvas`, `updateAtelierBrief` dans `frontend/src/lib/api.ts`.

## Phase 4 — UI dossier v2

- Composant principal : `frontend/src/components/AtelierDossier.tsx` (onglets **Carte** / **Tableaux** / **Rapport**, tiroir brief, relance segment).
- Modules : `DossierHeader.tsx`, `DossierTldr.tsx`, `DossierTabs.tsx`, `DossierSegments.tsx`, `DossierSynthesis.tsx`, `DossierExportAllBar.tsx`, `DossierSection.tsx`, `BriefDrawer.tsx`.
- `ChatMessage` rend **toujours** `AtelierDossier` pour un `business_dossier`. Sans `conversation_id` / callbacks côté page, l’UI reste **lecture seule** (pas d’« Affiner le brief » ni relance segment).

## Phase 5 — Validation & consolidation

- **Tests API** : `backend/tests/test_atelier_api.py` (401 sans Bearer, `GET /api/agent/dossier` 200 / 404 avec mocks `conversation_get` + `messages_list_asc`).
- **Tests manuels** (checklist produit, à faire sur environnement branché) :
  - pitch **restaurant / niche** : segments cohérents, exports, relance segment ;
  - pitch **SaaS B2B** : flux + tableaux ;
  - pitch **PME industrielle** : budget structuré, TL;DR, brief drawer + impacts.
- **Legacy** : le composant monolithique `BusinessDossier.tsx` et le feature flag `atelier_v2_enabled` ont été retirés ; l’UI unique est `AtelierDossier`.

## Phases suivantes

Affinements `TabCarte` (drawer acteur), `ActorDrawer`, carte consolidée, export PDF — voir `CURSOR_PROMPT_refonte_atelier.md`.
