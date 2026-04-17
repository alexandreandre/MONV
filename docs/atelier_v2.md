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

## Phases suivantes (non livrées ici)

TL;DR UI, endpoints de régénération, `AtelierDossier.tsx`, feature flag `atelier_v2_enabled` — voir cahier des charges projet.
