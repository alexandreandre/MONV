from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Any


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
    # 4 modes d'usage : prospection (défaut), sous_traitant, client, rachat.
    # Voir backend/services/modes.py. Validation tolérante côté serveur.
    mode: str | None = None


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
    messages: list[MessageOut] = []


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
