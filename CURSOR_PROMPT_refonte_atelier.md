# Prompt Cursor — Refonte du rendu Agent « Atelier » (MONV)

Copie-colle tout ce qui suit dans Cursor. Le prompt est pensé pour qu'il soit exécuté en plusieurs passes (phases) sans tout casser.

---

## Rôle

Tu es un ingénieur full-stack senior chargé de refondre le rendu de l'Agent Atelier dans MONV. Tu connais : FastAPI, Pydantic, Next.js 15 (App Router), React 19, TypeScript, Tailwind, lucide-react, react-markdown. Tu respectes strictement l'architecture existante (pipeline Guard → Orchestrator → API Engine, Supabase via service_role, crédits, modes d'usage).

Tu ne casses AUCUNE route existante. Tu ajoutes des endpoints et des composants, tu déprécies progressivement l'ancien rendu `BusinessDossier.tsx` en gardant un fallback.

## Contexte projet

- Dépôt : `MONV/` — `backend/` (FastAPI) + `frontend/` (Next.js 15).
- Agent Atelier : `POST /api/agent/send` → `routers/agent.py` + `services/agent.py` + `services/atelier_*.py`. Il produit un `BusinessDossier` (voir `backend/models/schemas.py`) composé de `ProjectBrief`, `BusinessCanvas`, `FlowMap`, `list[SegmentResult]`, `AgentSynthesis`. Le dossier est stocké dans `Message.metadata_json` avec `message_type="business_dossier"`.
- Rendu actuel : `frontend/src/components/BusinessDossier.tsx` (+ `BusinessModelCanvas.tsx`, `FlowDiagram.tsx`, `ResultsTable.tsx`, `ResultsMap.tsx`).
- Pipeline MONV : `routers/chat.py` utilise les couches Filter → Guard → Conversationalist → Orchestrator → API Engine → Relevance. Chaque segment de l'Atelier est en fait un appel du pipeline MONV avec une `query` et un `mode` parmi `prospection | sous_traitant | benchmark | rachat`.
- Crédits : voir `utils/credits_policy.py`, règles décrites dans le prompt de `services/orchestrator.py`.

## Diagnostic à résoudre (ce que tu corriges)

1. Le dossier est une page scroll-all verticale : header, canvas 3×3, graphe, 5 tableaux segment, synthèse. Aucun TL;DR, pas de hiérarchie, pas de CTA terminal.
2. Redondances fortes : budget répété 3×, chef japonais 4×, licence alcool 4×, 3 canaux dispersés partout.
3. Segments MONV incohérents : « Producteurs japonais » retourne des épiceries lyonnaises, « Importateurs spécialisés » contient Crédit Lyonnais / Adecco / Comptoir Électrique Français, « Clientèle gastronomique » retourne des restaurants (concurrents). 30-40% de doublons cross-segments.
4. Pertinence (`services/relevance.py`) filtre silencieusement : l'utilisateur ne voit pas pourquoi des lignes évidentes restent.
5. Pas d'itération partielle (regénérer un segment, affiner le canvas).
6. Pas de traçabilité du brief (pitch initial + réponses QCM) après génération.
7. Tableaux collés : SIREN/SIRET/NAF illisibles, pas de filtres inline, export segment par segment.
8. Budget final tronqué à « fonds de roulement 6 » dans `services/atelier_*` (terminaison manquante).

## Structure de contenu cible (9 blocs hiérarchisés, bullets courts)

Toute la fiche « création d'entreprise » doit suivre cette arborescence stricte. **Aucun paragraphe narratif** dans les blocs 0 à 8 : 1 idée = 1 bullet, verbe + objet + métrique. Narration réservée à l'onglet Rapport (version PDF).

### Bloc 0 — Carte d'identité

- Nom + tagline 1 ligne (12 mots max).
- Secteur · Localisation · Cible (B2B / B2C / Mixte).
- Budget fourchette (min – max k€).
- Ambition 2-3 ans (1 phrase).
- Méta : version · date · crédits consommés · nombre d'entreprises trouvées.

### Bloc 1 — Verdict express

- Feu tricolore global (Vert / Orange / Rouge) + 1 phrase de justification.
- 3 forces clés (1 bullet chacune, 12 mots max).
- 3 risques bloquants + sévérité (Critique / Important / Modéré).
- 3 actions cette semaine : Action → Délai → Coût.

### Bloc 2 — Modèle économique (7 questions, PAS la grille BMC 3×3)

- Q1. Qu'est-ce que je vends ? → 3 bullets proposition de valeur.
- Q2. À qui ? → segments clients par priorité (top 3-5).
- Q3. Comment je les atteins ? → canaux + coût d'acquisition estimé.
- Q4. Comment je gagne de l'argent ? → sources de revenus + marge estimée par canal.
- Q5. Qu'est-ce que je produis ? → activités clés (production / gestion / distribution).
- Q6. De quoi j'ai besoin ? → ressources (humaines / physiques / juridiques).
- Q7. Avec qui ? → partenaires par criticité.

### Bloc 3 — Écosystème (graphe)

- Acteurs par rôle : Amont / Pivot / Aval / Satellites.
- Flux filtrables : Valeur / Cash / Information.
- Dépendances critiques listées.

### Bloc 4 — Marché activable (données MONV)

- Tableau condensé par segment : Segment | Mode | Bruts → Uniques → Pertinents | Crédits export.
- Carte consolidée des entreprises.
- Tags multi-segment sur doublons.
- Lignes écartées masquées par défaut + bouton « Voir les N exclus ».

### Bloc 5 — Plan d'action 90 jours (kanban)

Format uniforme : Tâche → Responsable → Délai → Coût → Dépendance.

- Semaine 1-2 — Décisions fondatrices (juridique / financement / local).
- Mois 1-3 — Mise en route (recrutement / travaux / contrats).
- Mois 3-6 — Lancement (communication / ouverture / premiers KPIs).

### Bloc 6 — Budget détaillé

- Fourchette basse (minimum viable) : montant + hypothèses.
- Fourchette haute (ambition) : montant + hypothèses.
- Postes principaux : ligne par ligne avec % du total.
- Financement envisageable : fonds propres / emprunt / investisseurs.

### Bloc 7 — Pilotage (KPIs)

- KPIs mensuels : revenus, marge, coût d'acquisition.
- KPIs trimestriels : croissance, rétention.
- Par canal : objectif + seuil critique.
- Signaux d'alerte : conditions qui déclenchent une révision du plan.

### Bloc 8 — Risques & parades (par sévérité)

- Critique (bloquant légal / financier) : Risque → Parade → Coût parade.
- Important (opérationnel) : Risque → Parade → Délai.
- Modéré (à surveiller) : Risque → Signal d'alerte.

### Règles de rédaction appliquées partout

- 1 idée = 1 bullet, 1 phrase max.
- Chaque bullet est actionnable (verbe + objet + métrique ou délai).
- Hiérarchie max 3 niveaux : Bloc → Sous-section → Bullet.
- Max 5 bullets par sous-section. Au-delà → tableau ou drawer.
- Codage visuel cohérent : icône sévérité sur risques/actions, couleur par canal, tag par segment MONV.

### Mapping des blocs sur les 3 onglets

- **Onglet Carte** : Bloc 0 (header) + Bloc 1 (TL;DR) + Bloc 3 (graphe central) + Bloc 5 (kanban bas). Clic sur acteur → drawer qui affiche Bloc 2 pertinent + Bloc 4 segment lié + Bloc 8 risques liés.
- **Onglet Tableaux** : Bloc 4 étendu (tableau agrégé + filtres + carte consolidée).
- **Onglet Rapport** : tous les blocs 0 → 8 en mode narratif imprimable PDF.

---

## Architecture UI cible

### Header persistant (toujours visible)

```
[Nom projet]  ·  [Secteur]  ·  [Localisation]
[N entreprises trouvées] · [K segments] · [Budget fourchette] · v[version]
[Affiner le brief] [Exporter tout (X cr.)] [Rapport PDF] [Drawer Brief]
```

### Bandeau TL;DR (sous le header)

3 cartes horizontales (Force / Risque / Action) avec icône de sévérité et lien vers l'acteur du graphe correspondant. Contenu extrait de `AgentSynthesis`.

### 3 onglets de vue principale

**Onglet 1 — Carte (défaut, graph-first)**
- Graphe de flux (réutiliser `FlowDiagram.tsx`) occupant ~65% de la largeur. Le reste : rail gauche condensé (identité + 3 KPIs pilote), timeline kanban en bas (« Cette semaine / Ce mois / Ce trimestre »).
- Chaque nœud cliquable ouvre un **drawer latéral droit** (~30% largeur) agrégeant pour l'acteur cliqué :
  - description et rôle,
  - extrait canvas rattaché (1 à 3 blocs BMC pertinents),
  - top-10 du segment MONV lié (via `SegmentResult.preview`) + bouton « Voir tous »,
  - risques et actions rattachés (via mapping par `segment_key`),
  - actions : « Exporter ce segment », « Relancer avec d'autres mots-clés », « Voir sur carte ».
- Toggle « Valeur / Cash / Info » au-dessus du graphe.
- Bouton « Mode focus » qui masque le rail gauche + TL;DR.

**Onglet 2 — Tableaux (opérationnels)**
- Vue agrégée : union des `SegmentResult.preview` (étendue si l'utilisateur demande « voir tous ») en un seul tableau, avec colonne `segments[]` pour les doublons (multi-tags).
- Filtres transverses : département, tranche effectif, année de création, score pertinence.
- Bandeau compteurs : « X lignes brutes → Y uniques → Z pertinentes ».
- Badges d'alerte sur les lignes évidentes hors-scope (ex. NAF financier dans un segment alimentaire).
- Carte consolidée (réutiliser `ResultsMap.tsx`) affichée à droite du tableau.
- Export groupé (« tout le dossier ») ou sélectif (cases à cocher).

**Onglet 3 — Rapport (narratif, lisible, exportable en PDF)**
- Canvas reformulé en 3 sections orientées décision :
  1. Ce qu'on vend et à qui (proposition de valeur + segments clients + canaux)
  2. Comment on le fabrique (ressources clés + activités clés + partenaires clés)
  3. Comment ça fait de l'argent (sources de revenus + structure de coûts + marges par canal)
- Synthèse sous forme de cards cliquables (forces / risques / KPIs) qui renvoient au nœud du graphe correspondant.
- Plan d'action chronologique (semaine / mois / trimestre) avec dépendances visuelles.
- Budget déplié : fourchette basse, haute, hypothèses.
- Bouton « Export PDF » (rendu via `window.print()` d'une vue dédiée, ou via jsPDF si tu préfères).

### Principes transverses

- **Le contenu pivote autour des acteurs** du graphe, pas autour des sections BMC. Chaque acteur agrège son extrait canvas + son segment MONV + risques/actions associés.
- **Dédoublonnage inter-segments visible** au moment de l'affichage. Le backend expose déjà `_dedup_key` dans `services/api_engine.py`, il faut propager le tag multi-segment au frontend.
- **Pertinence visible** : score de `services/relevance.py` exposé sur chaque ligne ; lignes écartées masquées par défaut avec bouton « Voir les N résultats écartés ».
- **Itération partielle** : pouvoir regénérer un segment seul ou réécrire le canvas, coût crédits transparent.
- **Pitch + QCM épinglés** dans un drawer « Brief » accessible depuis le header, éditable, qui relance le pipeline sur ce qui est impacté.

## Modifications backend

### 1. Modèle de données — `backend/models/schemas.py`

- Ajouter sur `SegmentResult` :
  - `segment_key_aliases: list[str] = []` (segments où apparaît aussi chaque ligne — non, à mettre par ligne),
  - meilleure option : enrichir chaque dict de `preview` avec :
    - `segments: list[str]` (tags multi-segments calculés à la fusion),
    - `relevance_score: float | None`,
    - `relevance_flag: Literal["ok", "warning", "excluded"] | None`,
    - `reason_excluded: str | None`.
- Ajouter `BusinessDossier.version: int = 1`, `BusinessDossier.generated_at: datetime`, `BusinessDossier.total_unique: int`, `BusinessDossier.total_relevant: int`, `BusinessDossier.total_raw: int`, `BusinessDossier.total_credits: int`.
- Ajouter `AgentSynthesis.force_items: list[InsightItem]`, idem `risk_items`, `action_items`, `kpi_items` où `InsightItem` est :
  ```python
  class InsightItem(BaseModel):
      label: str
      severity: Literal["info", "warning", "critical", "positive"] = "info"
      detail: str | None = None
      segment_key: str | None = None   # lien vers le nœud/segment du graphe
      actor_id: str | None = None      # lien vers un acteur de FlowMap
  ```
  Conserver les anciens `forces: list[str]` comme fallback pour compat.
- Ajouter `ProjectBrief.budget_min_eur: int | None`, `budget_max_eur: int | None`, `budget_hypotheses: list[str] = []` en plus du champ texte existant.
- Ajouter `FlowActor.canvas_refs: list[str] = []` (slugs des blocs BMC liés : « partenaires », « activites », etc.) et `FlowActor.segment_key: str | None` déjà présent.

### 2. Agent Atelier — `backend/services/agent.py` + `backend/services/atelier_*.py`

- **Corriger le prompt LLM** qui génère les segments pour qu'il **n'invente pas** de segments hors portée du pipeline MONV (pipeline = entreprises françaises via SIRENE / Pappers / Google Places). Règle explicite à ajouter au prompt :
  - Interdiction de proposer des segments dont la cible est étrangère (ex. producteurs japonais au Japon) ou des particuliers (consommateurs finaux).
  - Si un segment « hors portée » est pertinent pour le projet, le marquer `out_of_scope=true` avec un commentaire, ne **pas** lancer d'appel pipeline et afficher « recherche web recommandée ».
- **Durcir la dédup inter-segments** côté backend : lors du merge des résultats de tous les segments, calculer pour chaque ligne la liste des `segment_key` dans lesquelles elle apparaît ; dédupliquer via `_dedup_key` (SIREN prioritaire).
- **Exposer la pertinence** : après l'appel de `services/relevance.py`, conserver le score et le flag sur chaque ligne du preview (au lieu de filtrer silencieusement). Seules les lignes `excluded` sont masquées par défaut côté UI.
- **Corriger le budget tronqué** : remplacer le texte court qui coupe à « fonds de roulement 6 » par un champ structuré (`budget_min_eur`, `budget_max_eur`, `budget_hypotheses`) et une phrase complète (« fonds de roulement 6 mois »).
- **Déterministe post-LLM** : pour chaque `FlowActor`, attacher `canvas_refs` en croisant son `label`/`role` avec les blocs BMC (matching sur termes clés). Si ambigu, laisser vide.

### 3. Nouveaux endpoints — `backend/routers/agent.py`

- `POST /api/agent/segments/{segment_key}/regenerate` :
  - body : `{ conversation_id, query_override?, mode_override? }`,
  - relance uniquement ce segment via le pipeline MONV,
  - met à jour le `BusinessDossier` sérialisé dans le dernier `message_type="business_dossier"`,
  - débite `1` crédit par relance (sauf unlimited). Cadrage dans `utils/credits_policy.py`.
- `POST /api/agent/canvas/regenerate` :
  - relance uniquement l'étape LLM canvas (pas les segments),
  - débite `0` crédit (pas d'appel API externe) mais consomme un appel LLM.
- `POST /api/agent/brief/update` :
  - body : `{ conversation_id, brief: ProjectBrief, impacts: ["canvas"|"flows"|"segments"] }`,
  - applique les modifs et relance les étapes impactées,
  - coût selon les relances.
- `GET /api/agent/dossier/{conversation_id}` : retourne le dernier `BusinessDossier` hydraté (utile pour les onglets qui rechargent sans re-POST).

### 4. Pipeline log & monitoring

- Ajouter des entrées `plog("atelier_segment_regenerate", ...)`, `plog("atelier_canvas_regenerate", ...)`.
- Ajouter dans la réponse de l'Atelier un objet `generation_stats` : `llm_calls`, `api_calls`, `credits_charged`, `relevance_removed_per_segment`.

## Modifications frontend

### 1. Nouveau layout parent — `frontend/src/components/AtelierDossier.tsx` (nouveau)

- Remplace progressivement `BusinessDossier.tsx` (garder l'ancien comme fallback contrôlé par un flag `experimental_atelier_v2` en feature flag côté front).
- Structure :
  ```
  <DossierHeader />
  <DossierTldr />
  <DossierTabs tabs={["Carte", "Tableaux", "Rapport"]}>
    <TabCarte />
    <TabTableaux />
    <TabRapport />
  </DossierTabs>
  <BriefDrawer />  // piloté par un bouton du header
  ```

### 2. Composants à créer

- `DossierHeader.tsx` : affiche identité + totaux + CTA (Affiner brief, Exporter tout, Rapport PDF).
- `DossierTldr.tsx` : 3 cartes Force / Risque / Action avec clic → focus sur nœud du graphe (émet un event au `TabCarte`).
- `TabCarte.tsx` : layout à 3 zones (rail gauche, graphe central, timeline bas). Le graphe reste `FlowDiagram.tsx` adapté. Clic sur un acteur → ouvre `ActorDrawer.tsx` à droite.
- `ActorDrawer.tsx` : panneau latéral qui reçoit en props `{actor: FlowActor, segment?: SegmentResult, canvasSlice?: Partial<BusinessCanvas>, insights: InsightItem[]}`. Boutons : Exporter ce segment / Relancer / Voir sur carte.
- `TabTableaux.tsx` : tableau consolidé + filtres + `ResultsMap.tsx` à droite + export groupé / sélectif.
- `TabRapport.tsx` : canvas narratif en 3 sections, synthèse en cards cliquables, plan d'action chronologique, budget déplié, bouton Export PDF.
- `BriefDrawer.tsx` : résumé du pitch + QCM + formulaire d'édition + boutons « Relancer canvas » / « Relancer segment X ».
- `KanbanActions.tsx` : 3 colonnes (semaine / mois / trimestre) alimentées par `AgentSynthesis.action_items` ou une répartition heuristique si les champs ne sont pas remplis.
- `ExportAllButton.tsx` : calcule le coût total (somme des `credits_required` par segment) et déclenche l'appel `POST /api/search/export` pour chaque segment avec un zip final (ou génère un .xlsx multi-feuilles en front via SheetJS).

### 3. Composants à retoucher

- `FlowDiagram.tsx` : accepter `onActorClick(actor)`, `focusedSegmentKey`, `filterFlows: "all" | "valeur" | "cash" | "info"`, `compact: boolean`.
- `ResultsTable.tsx` : gérer la colonne `segments[]` (multi-tags), les badges de pertinence (`ok`/`warning`/`excluded`), le tri/filtre par département, tranche effectif, année de création, pertinence.
- `ResultsMap.tsx` : accepter une liste consolidée multi-segments avec couleur par `segment_key`.
- `BusinessModelCanvas.tsx` : continuer d'exister pour compat, mais la vue par défaut devient la version narrative dans `TabRapport.tsx`.

### 4. API client — `frontend/src/lib/api.ts`

- Ajouter :
  - `regenerateSegment(conversationId, segmentKey, opts)`,
  - `regenerateCanvas(conversationId)`,
  - `updateBrief(conversationId, brief, impacts)`,
  - `getDossier(conversationId)`,
  - `exportAllSegments(conversationId)`.
- Typer tout ça depuis `models/schemas.py` (miroir TS).

### 5. Feature flag et routing

- Ajouter une bascule dans `ChatMessage.tsx` (qui rend aujourd'hui `BusinessDossier.tsx` pour `message_type="business_dossier"`) pour choisir entre `BusinessDossier` (legacy) et `AtelierDossier` (v2) via flag localStorage `atelier_v2_enabled`. Par défaut `true` en dev, `false` en prod tant que la refonte n'est pas validée.

## Correctifs spécifiques à activer dans les prompts LLM de l'Atelier

Ces correctifs vont dans `services/atelier_qcm.py` / `services/agent.py` / les prompts de planification des segments :

1. **Interdire les segments hors portée** : ajouter dans le prompt système du planificateur de segments : « Un segment doit être cherchable par le pipeline MONV. Interdit : producteurs étrangers hors de France, consommateurs particuliers. Si le projet a besoin d'une cible de ce type, retourne-la avec `out_of_scope=true` et une note explicative, et ne lance pas d'appel pipeline ».
2. **Cible pertinente par défaut** : pour un projet « restauration + e-commerce alcool France », les segments pipeline-compatibles sont : importateurs B2B en France (code NAF 46.xx boissons), distributeurs / cavistes spécialisés, prescripteurs B2B (hôtels, events, comités), concurrents directs locaux. Les « particuliers CSP+ » ne sont pas cherchables via MONV → basculer en `out_of_scope`.
3. **Durcir le filtrage par NAF** dans les segments : pour « importateurs spécialisés boissons japonaises », verrouiller `section_activite_principale = G` et `activite_principale ∈ {46.34Z, 46.39A, 46.39B}` et activer le filtre de pertinence strict (score minimum à remonter, ex. 0.65).
4. **Bannir de « q » les termes génériques qui polluent** : vérifier que le prompt Orchestrateur (déjà présent dans `services/orchestrator.py`) s'applique bien quand l'appel vient de l'Atelier — sinon on se retrouve avec Crédit Lyonnais et Adecco dans les importateurs.
5. **Corriger la troncature budget** : rechercher dans `services/atelier_*.py` la chaîne « fonds de roulement 6 » et la remplacer par une génération structurée (`budget_min_eur`, `budget_max_eur`, `budget_hypotheses`) + un texte complet.

## Plan d'exécution par phases

Fais les phases dans l'ordre et valide chaque phase avant de passer à la suivante. À chaque phase, tu commits avec un message clair.

### Phase 1 — Quick wins backend (sans refonte UI) — 1-2 jours

- [ ] Corriger le budget tronqué (remplacer le texte par un rendu complet + champs structurés dans `ProjectBrief`).
- [ ] Durcir le prompt planificateur de segments (interdire hors-portée, typer `out_of_scope`).
- [ ] Exposer la pertinence dans `SegmentResult.preview` (score + flag, au lieu de filtrer silencieux).
- [ ] Ajouter le tag multi-segment sur chaque ligne dédupliquée au moment de la fusion.
- [ ] Tests pytest sur `services/agent.py` avec un pitch type « Kappo Lyon » et vérifier les assertions : pas de Crédit Lyonnais dans importateurs, pas de restaurant dans la clientèle, budget non tronqué.

### Phase 2 — Quick wins frontend (sur l'ancien rendu) — 1 jour

- [ ] Ajouter un bandeau TL;DR en tête de `BusinessDossier.tsx` (3 cartes).
- [ ] Afficher les badges de pertinence sur les lignes existantes.
- [ ] Afficher les tags multi-segments dans les tableaux existants.
- [ ] Bouton « Exporter tout le dossier » (coût cumulé visible) en tête.

### Phase 3 — Endpoints d'itération — 1-2 jours

- [ ] Implémenter `POST /api/agent/segments/{segment_key}/regenerate`.
- [ ] Implémenter `POST /api/agent/canvas/regenerate`.
- [ ] Implémenter `POST /api/agent/brief/update`.
- [ ] Implémenter `GET /api/agent/dossier/{conversation_id}`.
- [ ] Mettre à jour `frontend/src/lib/api.ts` et exposer ces appels.

### Phase 4 — Refonte UI v2 — 1 semaine

- [ ] Créer `AtelierDossier.tsx` + `DossierHeader.tsx` + `DossierTldr.tsx` + `DossierTabs.tsx`.
- [ ] Implémenter `TabCarte.tsx` avec `ActorDrawer.tsx` (drawer + mapping acteur ↔ canvas ↔ segment ↔ insights).
- [ ] Implémenter `TabTableaux.tsx` avec filtres, dédup visible, map consolidée, export.
- [ ] Implémenter `TabRapport.tsx` avec canvas narratif, synthèse cards, plan chronologique, export PDF.
- [ ] Implémenter `BriefDrawer.tsx`.
- [ ] Feature flag `atelier_v2_enabled` pour bascule entre v1 et v2.

### Phase 5 — Validation et suppression du legacy — 2 jours

- [ ] Tests manuels sur 3 pitchs types (restaurant niche, SaaS B2B, PME industrielle).
- [ ] Tests pytest couvrant les nouveaux endpoints.
- [ ] Basculer le flag par défaut sur `true` en prod.
- [ ] Supprimer `BusinessDossier.tsx` legacy (après 1 semaine de stabilité).

## Contraintes non négociables

- Ne modifie **aucune signature** existante de `POST /api/agent/send` de façon cassante. Les nouveaux champs (`version`, `generated_at`, `total_unique`, etc.) sont ajoutés avec des défauts.
- Tous les nouveaux endpoints respectent le pattern `get_current_user` et `get_supabase` comme ailleurs.
- Tout appel LLM passe par `utils/llm.py` (pas d'appel direct OpenAI).
- Les tests backend existants doivent rester verts (`.github/workflows/ci.yml`).
- Pas d'emojis dans l'UI. Utiliser lucide-react pour les icônes.
- Respecter Tailwind sans introduire de CSS arbitraire hors `globals.css`.
- Les textes UI sont en français, cohérents avec le reste du produit.

## Critères de validation (ce que je vais vérifier)

Sur le pitch de démonstration « Kappo Lyon — restaurant japonais gastronomique + e-commerce sakés rares, Lyon » :

1. Le header affiche le nom, le secteur, la localisation, le total entreprises, le nombre de segments, la fourchette budget, la version, et 3 boutons CTA.
2. Le TL;DR affiche 3 cartes Force / Risque / Action cliquables.
3. L'onglet Carte s'ouvre par défaut sur le graphe. Cliquer sur un acteur ouvre un drawer cohérent (canvas + segment + actions).
4. L'onglet Tableaux montre 511 lignes brutes → N uniques → M pertinentes, avec badges sur Crédit Lyonnais / Adecco, et ces lignes sont masquées par défaut.
5. Le segment « Producteurs japonais » est soit renommé « Importateurs B2B en France », soit marqué `out_of_scope` avec explication.
6. Le segment « Clientèle gastronomique Lyon » n'existe plus sous cette forme ; il est remplacé par « Prescripteurs B2B » ou marqué `out_of_scope`.
7. Le budget est affiché en clair (fourchette + hypothèses), plus aucune phrase tronquée.
8. Un bouton « Regénérer ce segment » débite bien 1 crédit et met à jour le dossier sans recharger la page.
9. L'onglet Rapport affiche un canvas narratif en 3 sections et s'exporte en PDF propre.
10. Les tests pytest passent et la CI reste verte.

## Livrables attendus

- Commits atomiques (1 commit par phase, voire par sous-étape).
- README rapide de la refonte dans `docs/atelier_v2.md` (architecture + endpoints + flag).
- Capture d'écran de chaque onglet en fonctionnement sur le pitch Kappo Lyon.
- Note de migration pour les anciens dossiers déjà stockés en base (si le format change, prévoir un hydrateur côté lecture qui remplit les nouveaux champs avec des valeurs par défaut).

Commence par la Phase 1. Montre-moi le diff avant de continuer.
