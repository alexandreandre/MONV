from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Any, Literal


# --- Auth ---

class UserRegister(BaseModel):
    email: EmailStr
    name: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    credits: int
    credits_unlimited: bool = False
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Chat ---

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str
    # 4 modes d'usage : prospection (défaut), sous_traitant, benchmark, rachat.
    # Voir backend/services/modes.py. Validation tolérante côté serveur.
    mode: str | None = None
    # Nouvelle conversation rattachée à un projet (vue PROJETS).
    folder_id: str | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    message_type: str
    metadata_json: str | None = None
    created_at: datetime


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    mode: str | None = None
    folder_id: str | None = None
    messages: list[MessageOut] = []


class ProjectFolderCreate(BaseModel):
    name: str = "Nouveau projet"


class ProjectFolderPatch(BaseModel):
    name: str | None = None
    sort_position: int | None = None


class ProjectFolderOut(BaseModel):
    id: str
    name: str
    sort_position: int
    created_at: datetime
    updated_at: datetime


class ConversationFolderPatch(BaseModel):
    folder_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    messages: list[MessageOut]


# --- Guard (Layer 1) ---

class GuardEntity(BaseModel):
    localisation: str | None = None
    departement: str | None = None
    region: str | None = None
    secteur: str | None = None
    code_naf: str | None = None
    taille_min: int | None = None
    taille_max: int | None = None
    ca_min: float | None = None
    ca_max: float | None = None
    date_creation_apres: str | None = None
    date_creation_avant: str | None = None
    mots_cles: list[str] = []
    forme_juridique: str | None = None


class GuardResult(BaseModel):
    intent: str  # recherche_entreprise, recherche_dirigeant, enrichissement, hors_scope
    entities: GuardEntity
    confidence: float
    clarification_needed: bool = False
    clarification_question: str | None = None
    missing_criteria: list[str] = []  # ex: ["secteur", "zone_geo", "taille"]
    sector_ambiguous: bool = False
    # True si le secteur détecté peut correspondre à plusieurs activités
    # distinctes (ex: "padel" vs "paddle", "yoga" studio vs produit, etc.)
    sector_confirmed: str | None = None
    # Terme exact confirmé par l'utilisateur après clarification
    original_query: str = ""


# --- QCM (clarification) ---

class QcmOption(BaseModel):
    id: str
    label: str
    free_text: bool = False  # si True, l'utilisateur peut saisir un texte libre ("Autre")

class QcmQuestion(BaseModel):
    id: str            # ex: "secteur", "zone_geo", "taille"
    question: str      # texte affiché
    options: list[QcmOption]
    multiple: bool = False  # sélection multiple autorisée


# --- Orchestrator (Layer 2) ---

class APICall(BaseModel):
    source: str  # sirene, pappers, dropcontact
    action: str  # search, enrich, get_dirigeants, get_finances
    params: dict[str, Any] = {}
    priority: int = 1


class ExecutionPlan(BaseModel):
    api_calls: list[APICall]
    estimated_credits: int
    description: str
    columns: list[str] = []
    clarification_needed: bool = False
    clarification_question: str | None = None


# --- Signaux business ---

class BusinessSignal(BaseModel):
    type: str       # entreprise_recente, forte_croissance, ca_en_baisse, nouveau_dirigeant, augmentation_capital, resultat_negatif
    label: str      # libellé affiché (français)
    detail: str | None = None
    severity: str   # positive, warning, info


# --- Results ---

class CompanyResult(BaseModel):
    siren: str
    siret: str | None = None
    nom: str
    activite_principale: str | None = None
    libelle_activite: str | None = None
    adresse: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    region: str | None = None
    departement: str | None = None
    tranche_effectif: str | None = None
    effectif_label: str | None = None
    date_creation: str | None = None
    forme_juridique: str | None = None
    dirigeant_nom: str | None = None
    dirigeant_prenom: str | None = None
    dirigeant_fonction: str | None = None
    categorie_entreprise: str | None = None  # ex. PME / ETI (SIRENE)
    chiffre_affaires: float | None = None
    resultat_net: float | None = None
    annee_dernier_ca: int | None = None  # exercice du dernier CA connu
    date_cloture_exercice: str | None = None
    marge_brute: float | None = None
    ebe: float | None = None  # excédent brut d'exploitation
    capitaux_propres: float | None = None
    effectif_financier: float | None = None  # effectif déclaré sur l'exercice (comptes)
    capital_social: float | None = None
    numero_tva: str | None = None
    ca_n_minus_1: float | None = None
    resultat_n_minus_1: float | None = None
    annee_n_minus_1: int | None = None
    variation_ca_pct: float | None = None
    dirigeant_2_nom: str | None = None
    dirigeant_2_fonction: str | None = None
    email: str | None = None
    telephone: str | None = None
    site_web: str | None = None
    lien_annuaire: str | None = None
    google_maps_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    signaux: list[BusinessSignal] = []


class SearchResults(BaseModel):
    total: int
    results: list[CompanyResult]
    columns: list[str]
    credits_required: int
    search_id: str | None = None


# --- Credits ---

class CreditPack(BaseModel):
    id: str
    name: str
    credits: int
    price_euros: float
    price_per_credit: float


class CreditHistory(BaseModel):
    search_id: str
    query: str
    credits_used: int
    results_count: int
    created_at: datetime


# --- Export ---

class ExportRequest(BaseModel):
    search_id: str
    format: str = "xlsx"  # xlsx, csv


class ExportResponse(BaseModel):
    download_url: str
    filename: str
    credits_used: int


# --- Agent "Atelier" ---------------------------------------------------------
#
# L'Atelier est un agent supérieur aux 4 modes : il orchestre *plusieurs*
# recherches MONV (une par segment d'entreprise pertinent pour un projet de
# création) et produit un dossier structuré (identité, canvas, flux, synthèse).
# Les livrables sont stockés dans `Message.metadata_json` avec le
# message_type="business_dossier". Le QCM de clarification réutilise le
# message_type="agent_brief" (variante du QCM existant) afin de ne pas
# perturber le flux `/api/chat/send` classique.

class AgentRequest(BaseModel):
    """Point d'entrée unifié pour le flow Atelier.

    - Premier tour : `pitch` seul → déclenche un QCM de clarification.
    - Second tour : `conversation_id` + `answers` → déclenche la génération
      du dossier complet. Si le QCM du premier tour était vide (`questions: []`),
      `answers` peut être vide ou absent : le dossier est généré à partir du pitch seul.

    Premier tour — `folder_id` :
    - absent / null : crée un **nouveau** projet PROJETS et rattache la conversation ;
    - renseigné : rattache la conversation à ce projet (doit appartenir à l'utilisateur).
    """
    conversation_id: str | None = None
    pitch: str | None = None
    answers: str | None = None
    folder_id: str | None = None


class BusinessCanvas(BaseModel):
    """Business Model Canvas — 9 cases, chacune une liste de bullets courts."""
    proposition_valeur: list[str] = []
    segments_clients: list[str] = []
    canaux: list[str] = []
    relation_client: list[str] = []
    sources_revenus: list[str] = []
    ressources_cles: list[str] = []
    activites_cles: list[str] = []
    partenaires_cles: list[str] = []
    structure_couts: list[str] = []


class FlowEdge(BaseModel):
    """Arc d'un diagramme de flux : `from` → `to`, étiqueté."""
    origine: str
    destination: str
    label: str
    # Détail affiché au clic (analyse, risque, obligation, etc.)
    detail: str | None = None
    # "solid" (défaut) ou "dashed" (flux indirect, informationnel léger…)
    pattern: str | None = None


class FlowActor(BaseModel):
    """Acteur du schéma de flux ; `segment_key` relie optionnellement au tableau MONV du même `key`."""
    label: str
    segment_key: str | None = None
    # Identifiant stable optionnel (slug) — utile pour évolutions UI
    actor_id: str | None = None
    # Rôle métier court affiché sur le schéma (ex. « Prescripteur », « Infra »)
    role: str | None = None
    # Indice utilisateur (info-bulle) — pas un paragraphe marketing
    hint: str | None = None
    # "primary" = acteur central / pivot ; "secondary" = satellite
    emphasis: str | None = None


class FlowMap(BaseModel):
    """Cartographie à 3 couches — valeur, financier, information."""
    acteurs: list[FlowActor] = []
    flux_valeur: list[FlowEdge] = []
    flux_financiers: list[FlowEdge] = []
    flux_information: list[FlowEdge] = []
    # Métadonnées UI / lecture — toutes optionnelles pour rétrocompatibilité
    diagram_title: str | None = None
    # "radial" | "horizontal" | "vertical" — sinon le front choisit une heuristique
    layout: str | None = None
    # Une phrase d'orientation pour l'utilisateur (pas du remplissage)
    flow_insight: str | None = None


class SegmentBrief(BaseModel):
    """Une catégorie d'entreprises à chercher via le pipeline MONV.

    `mode` est l'un des 4 modes existants (jamais "atelier").
    `query` est la requête en langage naturel passée au Guard.
    """
    key: str           # identifiant technique (ex: "fournisseurs")
    label: str         # libellé UI (ex: "Fournisseurs clés")
    description: str   # explication courte du segment pour l'utilisateur
    mode: str          # "prospection" | "sous_traitant" | "rachat"
    query: str         # requête qui sera passée au pipeline MONV
    icon: str = "building"  # nom Lucide pour l'UI
    # Hors périmètre SIRENE / Pappers / Places France : pas d'appel pipeline
    out_of_scope: bool = False
    out_of_scope_note: str | None = None


class SegmentResult(BaseModel):
    """Résultat d'un appel pipeline pour un segment — identique au rendu
    d'un message `results` classique, enrichi d'une étiquette UI."""
    key: str
    label: str
    description: str
    mode: str
    icon: str
    query: str
    search_id: str | None = None
    total: int = 0
    credits_required: int = 0
    columns: list[str] = []
    preview: list[dict] = []
    map_points: list[dict] = []
    error: str | None = None
    out_of_scope: bool = False
    out_of_scope_note: str | None = None
    # Agrégats segment (prévisualisation enrichie pertinence / dédup)
    total_relevant: int | None = None
    relevance_threshold: int | None = None


class ProjectBrief(BaseModel):
    """Brief structuré extrait du pitch + QCM."""
    nom: str              # nom court généré pour le projet
    tagline: str          # accroche 1 ligne
    secteur: str          # description textuelle du secteur
    localisation: str     # ville, département ou région
    cible: str            # "B2B" | "B2C" | "B2B2C" | "Les deux"
    budget: str           # fourchette en français (phrase complète, non tronquée)
    modele_revenus: str   # modèle de revenus pressenti
    ambition: str         # taille visée à 2-3 ans
    budget_min_eur: int | None = None
    budget_max_eur: int | None = None
    budget_hypotheses: list[str] = []


class ChecklistItem(BaseModel):
    """Une action de la checklist Atelier avec texte d’accompagnement."""
    label: str = ""
    guide: str = ""


class ChecklistSection(BaseModel):
    """Bloc thématique (phase, étape, pièges…)."""
    title: str = ""
    subtitle: str | None = None
    items: list[ChecklistItem] = []


class AtelierChecklist(BaseModel):
    """Feuille de route actionnable (optionnelle selon génération LLM)."""
    headline: str = ""
    lede: str | None = None
    sections: list[ChecklistSection] = []
    pitfalls_title: str | None = None
    pitfalls: list[ChecklistItem] = []


class AgentSynthesis(BaseModel):
    """Synthèse produite à la fin du parcours Atelier."""
    forces: list[str] = []
    risques: list[str] = []
    prochaines_etapes: list[str] = []
    kpis: list[str] = []
    budget_estimatif: str | None = None
    # Ouverture « fiche conseil » (puces courtes, pas de blabla marketing)
    ordres_grandeur: list[str] = []
    conseil_semaine: str | None = None
    checklist: AtelierChecklist | None = None


class BusinessDossier(BaseModel):
    """Livrable final de l'Atelier — sérialisé dans metadata_json."""
    brief: ProjectBrief
    canvas: BusinessCanvas
    flows: FlowMap
    segments: list[SegmentResult]
    synthesis: AgentSynthesis
    version: int = 1
    generated_at: datetime | None = None
    total_raw: int = 0
    total_unique: int = 0
    total_relevant: int = 0
    total_credits: int = 0


class AgentResponse(BaseModel):
    conversation_id: str
    messages: list[MessageOut]
    # Projet PROJETS lié (créé ou existant) — renvoyé au premier tour pour la sidebar.
    folder_id: str | None = None


class AtelierSegmentRegenerateRequest(BaseModel):
    conversation_id: str
    query_override: str | None = None
    mode_override: str | None = None


class AtelierCanvasRegenerateRequest(BaseModel):
    conversation_id: str


class AtelierBriefUpdateRequest(BaseModel):
    conversation_id: str
    brief: ProjectBrief
    impacts: list[Literal["canvas", "flows", "segments"]]


class AtelierGenerationStats(BaseModel):
    llm_calls: int = 0
    api_calls: int = 0
    credits_charged: int = 0
    relevance_removed_per_segment: dict[str, int] = {}


class AtelierDossierMutationResponse(BaseModel):
    """Réponse des endpoints qui mettent à jour le dernier dossier Atelier."""
    dossier: BusinessDossier
    generation_stats: AtelierGenerationStats
    credits_remaining: int | None = None


class AtelierDossierGetResponse(BaseModel):
    message_id: str
    dossier: dict[str, Any]
