# Prompt Cursor — Amélioration des agents et modes MONV

> Copie-colle tout ce qui suit dans Cursor (mode Agent). Le prompt est structuré en phases.
> Chaque phase doit être complétée et validée avant de passer à la suivante.

---

## Rôle

Tu es un ingénieur IA senior spécialisé dans la conception de pipelines d'agents LLM pour des applications B2B.
Tu maîtrises : FastAPI, Pydantic, Next.js 15 App Router, React 19, TypeScript, Tailwind, et les meilleures pratiques
en matière de pipelines multi-agents (ReAct, Chain-of-Thought, RAG, scoring LLM, prompt engineering 2025).

**Contraintes absolues :**
- Tu ne casses AUCUNE route existante (`/api/chat`, `/api/agent/*`, `/api/search/*`, `/api/auth/*`, `/api/credits/*`).
- Tu ne modifies pas le schéma Supabase sans créer un fichier de migration dans `backend/supabase/migrations/`.
- Tu respectes les conventions de `backend.mdc` et `frontend.mdc` (lire `.cursor/rules/`).
- Tu travailles sur la branche `dev`, jamais sur `main` directement.
- Tout code ajouté est couvert par au moins un test pytest (`backend/tests/`).
- Les messages utilisateur restent en **français**.

---

## Contexte projet MONV

**Architecture** : `backend/` (FastAPI + Python 3.11) + `frontend/` (Next.js 15 App Router).

**Pipeline chat** : Filter → Guard → Conversationalist → Orchestrator → Plan Patches → API Engine
(SIRENE / Google Places / Pappers / BODACC / DECP) → Signals → Relevance → Output.

**Cinq agents** (définis dans `backend/services/agent_registry.py`) :

| Agent ID | Nom UI | Fichiers clés |
|---|---|---|
| `prospection` | Prospection commerciale | `services/orchestrator.py`, `services/digital_pitch_enrichment.py` |
| `sous_traitant` | Recherche de sous-traitants | `services/orchestrator.py`, `routers/chat.py` |
| `benchmark` | Benchmark concurrentiel | `services/benchmark_stats.py`, `routers/chat.py` |
| `rachat` | Reprise / Rachat d'entreprise | `services/bodacc.py`, `services/marches_publics.py`, `services/signals.py` |
| `atelier` | Création d'entreprise | `services/agent.py`, `services/atelier_*.py`, `services/atelier_checklist_pipeline.py` |

**Couches LLM** : chaque nœud LLM est configurable via des overrides Supabase
(voir `backend/services/agent_config.py` → `resolve_llm_for_block`).
Les modèles par défaut sont définis dans `backend/config.py` via les variables
`FILTER_MODEL`, `GUARD_MODEL`, `ORCHESTRATOR_MODEL`, `RELEVANCE_FILTER_MODEL`,
`ATELIER_BUSINESS_MODEL`, `DIGITAL_PITCH_ENRICH_MODEL`.

**Scoring/pertinence** : `backend/services/relevance.py` — score 0–10 par ligne,
seuil dynamique selon le mode. Problème connu : filtre silencieux (l'utilisateur
ne voit pas pourquoi des lignes sont exclues).

---

## Phase 0 — Recherche web & état de l'art (OBLIGATOIRE avant tout code)

> Pour chaque sous-tâche ci-dessous, utilise l'outil de recherche web de Cursor.
> Résume tes trouvailles dans un fichier `docs/research_agents_2025.md`.

### 0-A : Meilleures pratiques prompt engineering pour agents LLM (2024-2025)

Recherche : `"LLM agent prompt engineering best practices 2025"`,
`"chain-of-thought agent pipeline scoring"`, `"ReAct agent pattern production"`.

Questions clés à résoudre :
- Quelle structure de prompt maximise la précision de l'extraction d'entités (Guard) ?
- Comment structurer le prompt de l'Orchestrateur pour minimiser les plans vides ou incohérents ?
- Quels patterns de few-shot examples améliorent le scoring de pertinence ?

### 0-B : Prospection B2B — meilleures pratiques qualification de leads (2024-2025)

Recherche : `"B2B lead qualification AI pipeline best practices"`,
`"ICP ideal customer profile LLM extraction"`,
`"intent signal B2B prospection AI"`.

Questions clés :
- Quels signaux business (financement, recrutement, appels d'offres, actualités) sont les
  plus prédictifs d'une opportunité commerciale en France ?
- Comment segmenter les leads par niveau de maturité/urgence ?
- Quelles colonnes de résultats les commerciaux trouvent les plus utiles (benchmark SaaS B2B) ?

### 0-C : Reprise/Rachat d'entreprise — signaux de cédabilité

Recherche : `"cession entreprise signaux détection algorithme"`,
`"transmission PME indicateurs automatique France"`,
`"BODACC signaux rachat ML"`.

Questions clés :
- Quels sont les meilleurs indicateurs publics de cédabilité d'une PME française ?
- Existe-t-il des datasets ou APIs complémentaires à BODACC/SIRENE pour la détection
  de dirigeants proches de la retraite (> 60 ans) ?
- Comment scorer la probabilité de cession sur une échelle 0–100 ?

### 0-D : Benchmark concurrentiel — méthodologies automatisées

Recherche : `"automated competitive benchmark LLM pipeline"`,
`"competitive analysis AI tools 2025"`,
`"market positioning score algorithm"`.

Questions clés :
- Quels axes de comparaison (CA, effectifs, ancienneté, spécialisation) donnent les
  meilleures insights pour un benchmark PME en France ?
- Comment calculer un score de positionnement relatif (où je me situe dans mon marché) ?

### 0-E : Recherche de sous-traitants — qualification automatique

Recherche : `"subcontractor qualification AI automatic B2B"`,
`"fournisseur scoring capacité automatique"`,
`"supply chain risk scoring SME France"`.

Questions clés :
- Quels critères de qualification sont les plus importants pour un donneur d'ordre français ?
- Comment évaluer automatiquement la capacité de production à partir de données publiques ?

### 0-F : Agent création d'entreprise — structure optimale du dossier

Recherche : `"business plan AI agent best practices 2025"`,
`"lean canvas vs business model canvas AI generation"`,
`"startup feasibility score LLM"`.

Questions clés :
- Quelle structure de dossier business (canvas, checklist, budget) les outils SaaS
  concurrents (Joorney, Bpifrance Créateur, etc.) utilisent-ils ?
- Comment structurer un budget prévisionnel généré par LLM pour qu'il soit crédible ?
- Quels blocs sont les plus souvent demandés par les banques / BPI pour un financement ?

---

## Phase 1 — Audit du code existant

Lis attentivement les fichiers suivants avant de proposer des modifications :

```
backend/services/guard.py                    # Extraction d'entités
backend/services/orchestrator.py             # Génération du plan d'exécution
backend/services/relevance.py                # Scoring de pertinence
backend/services/digital_pitch_enrichment.py # Enrichissement prospection
backend/services/signals.py                  # Signaux business (rachat)
backend/services/benchmark_stats.py          # Stats benchmark
backend/services/agent.py                    # Orchestration agent atelier
backend/services/atelier_checklist_pipeline.py  # Checklist atelier
backend/services/modes.py                    # Définitions des modes
backend/services/agent_registry.py           # Graphes des agents (source de vérité)
backend/config.py                            # Variables d'environnement
backend/models/schemas.py                    # Schémas Pydantic
```

Pour chaque fichier, identifie :
1. Les prompts LLM actuels (balises system/user).
2. Les heuristiques codées en dur qui pourraient être améliorées.
3. Les points de défaillance silencieux (erreurs avalées sans log).
4. Les colonnes de résultats manquantes ou redondantes.

Synthèse dans `docs/audit_agents.md` (max 3 points par agent).

---

## Phase 2 — Améliorations par agent

Implémente les améliorations dans l'ordre suivant. Après chaque sous-phase, lance :
```bash
cd backend && python -m pytest tests/ -x -q
```

### 2-A : Guard (`services/guard.py`) — amélioration extraction d'entités

**Objectif :** Réduire les `clarification_needed=True` inutiles et mieux extraire les entités implicites.

Améliorations à implémenter :
1. **Few-shot examples** : Ajoute 3–5 exemples annotés dans le prompt système du Guard,
   couvrant les cas ambigus fréquents de MONV (ex : « plombier » → artisan B2C vs grossiste B2B,
   « restaurant japonais » → clientèle vs fournisseur vs concurrent).
   Les exemples doivent être dans une variable `GUARD_FEW_SHOT_EXAMPLES` importée depuis
   un nouveau fichier `backend/services/guard_examples.py`.

2. **Extraction de l'intent de mode implicite** : Si la requête contient des mots-clés de rachat
   (« reprendre », « céder », « transmission », « succession ») ou de benchmark (« comparer »,
   « concurrents », « panel »), le Guard doit renseigner un champ `suggested_mode` dans son output
   JSON. Ne pas changer le mode automatiquement — juste suggérer via le champ.

3. **Tolérance aux fautes de frappe** : Normalise les codes NAF et noms de secteurs avant
   extraction (lemmatisation légère via `unidecode` + lookup dans une table de synonymes
   `SECTOR_SYNONYMS` dans `services/guard_examples.py`).

Schéma de sortie Guard mis à jour (Pydantic dans `models/schemas.py`) :
```python
class GuardResult(BaseModel):
    ...  # champs existants inchangés
    suggested_mode: str | None = None   # nouveau : "rachat" | "benchmark" | None
    sector_synonyms_used: list[str] = []  # nouveau : pour debug
```

### 2-B : Orchestrateur (`services/orchestrator.py`) — réduction des plans vides

**Objectif :** Éliminer les plans d'exécution vides ou incohérents qui causent des résultats nuls.

Améliorations à implémenter :
1. **Plan de secours déterministe renforcé** : Le fallback actuel existe mais est minimal.
   Crée une fonction `build_deterministic_plan(guard_result, mode)` dans un nouveau
   fichier `services/orchestrator_fallback.py` qui génère un plan SIRENE valide à partir
   des entités Guard même sans LLM. Couvre les 5 modes.

2. **Validation du plan avant dispatch** : Ajoute une fonction `validate_execution_plan(plan)`
   qui vérifie : au moins 1 source active, secteur non vide, zone géographique cohérente.
   Si invalide → applique le plan déterministe de secours + log `[MONV.pipeline] plan_fallback`.

3. **Prompt addendum par mode** : Chaque mode doit avoir un addendum de prompt spécifique
   injecté dans l'Orchestrateur (actuellement vide pour prospection). Structure dans
   `services/orchestrator.py` :
   ```python
   MODE_ADDENDUMS: dict[str, str] = {
       "prospection":   "...",  # focus CA > 0, actif, enrichissement digital si pertinent
       "sous_traitant": "...",  # force NAF + tranche effectif ≥ 3, zone stricte
       "benchmark":     "...",  # panel représentatif, variantes régionales
       "rachat":        "...",  # ancienneté ≥ 10 ans, biais transmission/succession
   }
   ```

### 2-C : Pertinence (`services/relevance.py`) — scoring explicable

**Objectif :** Rendre le filtrage visible côté utilisateur et améliorer la précision du scoring.

Améliorations à implémenter :
1. **Raison d'exclusion** : Le scoring LLM doit retourner non seulement le score mais aussi
   une `reason` courte (max 10 mots) justifiant l'exclusion si score < seuil. Ce champ
   doit être stocké dans `CompanyResult.relevance_reason` (nouveau champ Pydantic, nullable).

2. **Seuils dynamiques par mode** :
   - `prospection` : seuil actuel (laisser tel quel ou ajuster si ratio exclusions > 50%)
   - `sous_traitant` : seuil plus strict (+1 point) car besoin de précision > rappel
   - `benchmark` : seuil bas (-1 point) car besoin d'un panel large et représentatif
   - `rachat` : seuil modéré, bonus automatique +2 si signal BODACC détecté

3. **Bouton "Voir les N exclus"** : Expose les lignes exclues dans la réponse API avec
   `excluded: true` et `relevance_reason` renseigné. Le frontend peut les masquer par défaut
   mais les afficher sur demande (composant `ExcludedResultsToggle.tsx` à créer).

### 2-D : Prospection (`services/digital_pitch_enrichment.py`) — enrichissement web

**Objectif :** Améliorer la qualité des insights générés pour les agences digitales / web.

Améliorations à implémenter :
1. **Détection du site web** : Si l'entreprise a un `website` renseigné (via Pappers ou Google
   Places), passe le domaine à un nouveau nœud `WebPresenceCheck` qui évalue la présence
   digitale via des heuristiques (âge du domaine estimé, HTTPS, présence mobile via
   user-agent, méta description présente). Pas de crawl complet — juste un HEAD request
   avec timeout 3s max. Expose les résultats dans 3 colonnes : `has_website`,
   `website_quality_score` (0–3), `website_issues` (liste).

2. **Score d'opportunité digitale** : Combine `website_quality_score` + secteur + CA estimé
   en un seul champ `digital_opportunity_score` (0–10) calculé localement (pas de LLM).
   Formule à documenter dans un docstring.

3. **Prompt mis à jour** : Intègre les nouvelles données de présence web dans le prompt
   LLM d'enrichissement pour que le « pitch rapide » généré mentionne des éléments concrets
   (ex : « site sans HTTPS, pas de présence mobile »).

### 2-E : Rachat (`services/signals.py`, `services/bodacc.py`) — scoring de cédabilité

**Objectif :** Produire un score de cédabilité consolidé visible dans le tableau de résultats.

Améliorations à implémenter :
1. **Score de cédabilité** : Crée une fonction `compute_cessation_score(company, signals) -> int`
   dans `services/signals.py`. Score de 0 à 100 basé sur :
   - Ancienneté ≥ 15 ans : +20
   - Dirigeant probable > 60 ans (si Pappers disponible) : +25
   - Signal BODACC vente/cession dans les 24 mois : +30
   - Aucun recrutement récent détectable : +10
   - CA stable ou en légère baisse sur 3 ans : +15
   Documente chaque facteur et sa source de données.

2. **Label signal prioritaire** : Ajoute un champ `priority_signal` sur `CompanyResult`
   (valeurs : `"cession_imminente"` | `"profil_transmission"` | `"à_surveiller"` | `None`).
   Calcul : `cession_imminente` si score ≥ 70, `profil_transmission` si 40–69, etc.

3. **Framing mis à jour** : Le markdown généré par `_build_rachat_framing` dans
   `routers/chat.py` doit inclure une mini-légende expliquant les signaux affichés.
   Max 3 lignes, ton factuel (pas de conseil d'acquisition).

### 2-F : Benchmark (`services/benchmark_stats.py`) — positionnement relatif

**Objectif :** Donner à l'utilisateur une lecture immédiate de sa position dans le panel.

Améliorations à implémenter :
1. **Score de positionnement** : Ajoute une colonne `benchmark_position_score` (0–100)
   calculée comme le percentile de l'entreprise dans le panel sur 4 axes pondérés :
   CA (40%), effectif (30%), ancienneté (20%), croissance CA YoY (10%).
   Fonction : `compute_position_score(row, panel_stats) -> float` dans `benchmark_stats.py`.

2. **Catégorie de position** : Ajoute `benchmark_tier` (`"leader"` | `"challenger"` | `"suiveur"` | `"entrant"`)
   basé sur les quartiles du panel.

3. **Stats panel enrichies** : Le `panel_stats` dict retourné par `enrich_with_benchmark_positions`
   doit inclure : médiane CA, médiane effectif, distribution par tier (nb par catégorie),
   zone géographique dominante. Utilisé dans le `_build_benchmark_framing`.

### 2-G : Sous-traitant (`routers/chat.py`, `services/orchestrator.py`) — qualification capacité

**Objectif :** Améliorer la pertinence des sous-traitants retournés.

Améliorations à implémenter :
1. **Score de capacité estimée** : Crée `compute_capacity_score(company, guard_entities) -> int`
   dans un nouveau `services/sous_traitant_scoring.py`. Inputs : tranche d'effectif SIRENE,
   CA Pappers si disponible, labels SIRENE (artisan, industrie), NAF.
   Score 0–100 : effectif ≥ 10 → +30, CA > 500k → +20, spécialisation NAF exacte → +30, etc.

2. **Colonne `capacity_score`** sur les résultats du mode sous-traitant, visible dans le tableau.

3. **QCM amélioré** : Les questions générées pour le mode sous-traitant doivent inclure une
   question sur la **taille minimale** souhaitée (1–5 / 5–20 / 20+ salariés).
   Modifier le prompt dans `services/conversationalist.py` sous la clé mode `sous_traitant`.

### 2-H : Agent Atelier (`services/agent.py`, `services/atelier_checklist_pipeline.py`) — dossier structuré

**Objectif :** Aligner la structure de sortie sur les 9 blocs définis dans le prompt de refonte atelier
(voir `CURSOR_PROMPT_refonte_atelier.md`). Cette phase est la plus lourde — la décomposer en 3 itérations.

**Itération H-1 : Bloc 0 + Bloc 1 (Carte d'identité + Verdict express)**

1. Ajoute un nœud LLM `verdict_express` dans `services/agent.py`, appelé après `dossier_fill`.
   Input : le dossier complet. Output JSON :
   ```json
   {
     "feu_tricolore": "vert|orange|rouge",
     "justification": "...",
     "forces": ["...", "...", "..."],
     "risques": [{"libelle": "...", "severite": "critique|important|modere"}],
     "actions_semaine": [{"action": "...", "delai": "...", "cout": "..."}]
   }
   ```
2. Expose ce champ dans `BusinessDossier` (nouveau champ `verdict_express: VerdictExpress | None`
   dans `models/schemas.py`).
3. Frontend : crée `frontend/src/components/VerdictExpress.tsx` affichant le feu tricolore
   (vert/orange/rouge avec icône lucide-react) + les 3 forces + 3 risques.

**Itération H-2 : Bloc 2 (Modèle économique — 7 questions)**

Remplace le Business Model Canvas 3×3 actuel par le format 7 questions :
Q1 Qu'est-ce que je vends, Q2 À qui, Q3 Comment je les atteins, Q4 Comment je gagne,
Q5 Ce que je produis, Q6 Ce dont j'ai besoin, Q7 Avec qui.

1. Modifie le prompt `dossier_fill` pour générer un champ `business_model_7q` au lieu
   (ou en complément) du `business_canvas`.
2. Crée `frontend/src/components/BusinessModel7Q.tsx`.
3. Garde `BusinessModelCanvas.tsx` comme fallback si `business_model_7q` est absent.

**Itération H-3 : Bloc 6 (Budget — fourchette basse / haute)**

1. Le prompt Atelier doit générer `budget_low` et `budget_high` (objets JSON avec
   `total_keur`, `hypotheses: string[]`, `postes: [{label, montant_keur, pct_total}]`).
2. Corriger le bug de troncature du budget final (message tronqué à « fonds de roulement 6 »)
   en augmentant `max_tokens` du nœud `dossier_fill` à 20 000 et en vérifiant que le JSON
   est parsé intégralement dans `services/atelier_coerce.py`.

---

## Phase 3 — Qualité & tests

Après chaque phase 2-X :

1. **Tests unitaires** : Ajoute dans `backend/tests/` un fichier `test_<nom_du_module>.py`
   avec au moins :
   - 1 test du happy path
   - 1 test de fallback (LLM vide ou réseau down)
   - 1 test des nouveaux champs Pydantic

2. **Test d'intégration** : Si une route API est modifiée, ajoute un test d'intégration
   via `httpx.AsyncClient` sur le router concerné (voir les tests existants comme modèle).

3. **Vérification build** : Après tout changement frontend :
   ```bash
   cd frontend && npm run build 2>&1 | tail -20
   ```
   Zéro erreur TypeScript autorisée.

4. **Lint backend** :
   ```bash
   cd backend && python -m flake8 services/ --max-line-length=120 --ignore=E501
   ```

---

## Phase 4 — Documentation

Pour chaque agent amélioré, mets à jour :

1. **`backend/services/agent_registry.py`** : Met à jour les `default_prompt_preview` des nœuds
   modifiés pour refléter les nouveaux prompts.

2. **`.cursor/rules/backend.mdc`** : Ajoute les nouvelles fonctions et fichiers dans la section
   « Résumé des services ».

3. **`README.md`** (section Pipeline côté backend) : Une ligne par amélioration majeure,
   format `- [Phase 2-X] Description courte`.

4. **`docs/research_agents_2025.md`** : Finalise le document de recherche de la Phase 0
   avec les liens sources utilisés.

---

## Phase 5 — Vérification finale

Avant de soumettre le PR :

```bash
# Backend : tous les tests passent
cd backend && python -m pytest tests/ -v --tb=short

# Frontend : build propre
cd frontend && npm run build

# Vérification no-regression API
curl -s http://localhost:8000/api/health | python -m json.tool

# Vérification graphes agents (doit retourner 5 agents sans KeyError)
cd backend && python -c "
from services.agent_registry import list_all_agent_definitions
defs = list_all_agent_definitions()
print([d['agent_id'] for d in defs])
assert len(defs) == 5
print('OK')
"
```

Si tout est vert → créer un commit par phase avec message conventionnel :
```
feat(agent): [Phase 2-X] description courte
```

---

## Annexe — Fichiers de référence à lire en priorité

| Fichier | Pourquoi le lire |
|---|---|
| `backend/services/agent_registry.py` | Source de vérité sur la topologie des 5 agents |
| `backend/services/orchestrator.py` | Prompt orchestrateur + addendums par mode |
| `backend/models/schemas.py` | Tous les schémas Pydantic — ne pas casser la compatibilité |
| `backend/services/relevance.py` | Prompt scoring + seuils actuels |
| `backend/services/agent.py` | Orchestration atelier (QCM → plan → dossier → segments) |
| `.cursor/rules/backend.mdc` | Conventions backend obligatoires |
| `.cursor/rules/frontend.mdc` | Conventions frontend obligatoires |
| `CURSOR_PROMPT_refonte_atelier.md` | Structure cible des 9 blocs du dossier atelier |
| `docs/research_agents_2025.md` | (à créer en Phase 0) Synthèse de tes recherches web |

---

## Ordre d'exécution recommandé

```
Phase 0 → (docs/research_agents_2025.md produit)
Phase 1 → (docs/audit_agents.md produit)
Phase 2-A (Guard)
Phase 2-B (Orchestrateur)
Phase 2-C (Pertinence)      ← impact cross-modes, faire tôt
Phase 2-D (Prospection)
Phase 2-E (Rachat)
Phase 2-F (Benchmark)
Phase 2-G (Sous-traitant)
Phase 2-H (Atelier H-1 → H-2 → H-3)
Phase 3   (Tests + build)
Phase 4   (Docs)
Phase 5   (Vérification finale + PR)
```

**Ne saute pas la Phase 0.** Les recherches web conditionneront la qualité des prompts
que tu écriras en Phase 2. Un prompt LLM sans few-shot fondé sur des exemples réels
du domaine sera systématiquement moins précis.
