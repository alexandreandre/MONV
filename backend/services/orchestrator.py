"""
Couche 2 — Orchestrateur
Transforme l'intent structuré en plan d'exécution API.
"""

import json
from models.schemas import GuardResult, ExecutionPlan, APICall
from utils.llm import llm_json_call
from config import settings

ORCHESTRATOR_SYSTEM_PROMPT = """Tu es l'orchestrateur de MONV, un outil de recherche d'entreprises en France (clients, prestataires, fournisseurs, partenaires, concurrents).

Tu reçois un intent structuré (JSON) issu de la couche Guard et tu dois produire un plan d'exécution API.

SOURCES DISPONIBLES :
1. "sirene" — API Recherche Entreprises (gratuit, données INSEE)
   Actions :
   - "search" : recherche par critères (section_naf, tranche_effectif, localisation, etc.)
   Params possibles : section_activite_principale (lettre NAF), activite_principale (code APE NAF **complet** au format INSEE, ex. 62.01Z ou 70.22Z — **jamais** une division seule sur 2 chiffres comme 62 ou 70 ; dans ce cas n'envoyer que la section lettre ou des codes complets),
   tranche_effectif_salarie (codes séparés par virgule), code_postal, departement, region,
   code_commune (code INSEE à 5 chiffres uniquement — jamais de nom de ville dans « commune »),
   q (texte libre), page, per_page (max 25)

2. "google_places" — API Google Places (recherche géolocalisée de commerces réels)
   Actions :
   - "search" : recherche textuelle de lieux / commerces / entreprises
   Params :
   - query (OBLIGATOIRE) : termes de recherche métier, ex. "boutique padel", "restaurant japonais", "club de tennis", "coworking"
   - location (optionnel) : contexte géographique en texte, ex. "PACA", "Marseille", "Bouches-du-Rhône", "Lyon"

3. "pappers" — API Pappers (payant, données enrichies)
   Actions :
   - "search" : recherche entreprises avec plus de filtres
   - "get_dirigeants" : récupérer les dirigeants d'une entreprise (par SIREN)
   - "get_finances" : récupérer CA et données financières (par SIREN)
   Params : siren, siret, q, code_naf, departement, region, ville, ca_min, ca_max,
   effectif_min, effectif_max, date_creation_min, date_creation_max

MAPPING NAF sections (pour l'API SIRENE) :
A=Agriculture, B=Industries extractives, C=Industrie manufacturière,
D=Électricité/gaz, E=Eau/déchets, F=Construction, G=Commerce,
H=Transport, I=Hébergement/restauration, J=Information/communication,
K=Finance/assurance, L=Immobilier, M=Activités spécialisées,
N=Services administratifs, O=Administration publique, P=Enseignement,
Q=Santé, R=Arts/spectacles, S=Autres services

MAPPING codes NAF → section lettre :
10-33→C, 41-43→F, 45-47→G, 49-53→H, 55-56→I, 58-63→J,
64-66→K, 68→L, 69-75→M, 77-82→N, 85→P, 86-88→Q

RÈGLES DE COÛT (crédits) :
- Recherche SIRENE seule (<100 résultats) : 1 crédit
- Recherche SIRENE + Pappers (<500 résultats) : 3 crédits
- Recherche enrichie + contacts (<500 résultats) : 5 crédits
- Recherche massive (>500 résultats) : 10 crédits

COLONNES par défaut :
- Toujours : nom, siren, siret, activite_principale, libelle_activite, adresse, code_postal, ville, tranche_effectif, date_creation
- Si google_places utilisé : ajoute telephone, site_web, google_maps_url (données Google)
- Si recherche_dirigeant : + dirigeant_nom, dirigeant_prenom, dirigeant_fonction
- Si recherche financière (ca_min/ca_max mentionné) : + chiffre_affaires, resultat_net
- Si enrichissement : + email, telephone, site_web

Réponds UNIQUEMENT avec un JSON valide :
{
    "api_calls": [
        {
            "source": "sirene|google_places|pappers",
            "action": "search|get_dirigeants|get_finances",
            "params": { ... },
            "priority": 1
        }
    ],
    "estimated_credits": 1-10,
    "description": "Description courte du plan d'exécution",
    "columns": ["nom", "siren", ...],
    "clarification_needed": false,
    "clarification_question": null
}

RÈGLES DE CHOIX DE SOURCE :
- **SIRENE seul** : recherches structurelles larges (secteur NAF + région + taille). Ex. « PME du BTP en IDF », « ESN à Lyon de plus de 50 salariés ».
- **Google Places + SIRENE** : recherches de commerces de niche, boutiques spécialisées, services locaux.
  Le mot-clé principal ne correspond pas bien à un code NAF seul, OU le paramètre "q" de SIRENE
  ne peut pas capturer l'activité réelle. Ex. « boutique de padel en PACA », « restaurant japonais à Marseille »,
  « club de crossfit à Bordeaux », « imprimeur 3D à Toulouse », « salle de coworking à Nantes ».
  → Mets google_places en priority=1 (découverte) ET sirene en priority=2 (complément structurel).
  Pour google_places, le param "query" doit contenir les mots-clés métier (ex. "boutique padel"),
  et "location" le contexte géo (ex. "PACA", "Marseille").
- **Google Places seul** : si le code NAF est trop large pour être utile et que la spécificité vient
  d'un mot-clé sémantique introuvable dans les raisons sociales INSEE.
- **Pappers** : seulement si dirigeants ou CA demandés explicitement.

STRATÉGIE MULTI-APPELS POUR ACTIVITÉS DE NICHE (OBLIGATOIRE) :
Quand l'activité est une niche spécifique (padel, crossfit, yoga, coworking, escape game, salon de
coiffure, restaurant japonais, etc.), tu DOIS générer PLUSIEURS api_calls :

1. google_places (priority=1) — mot-clé métier + zone géo
2. Plusieurs appels sirene SANS "q" (priority=2), chacun avec un code activite_principale différent :
   ⚠️ NE METS JAMAIS le mot-clé niche dans "q" quand tu utilises un code NAF !
   "q" cherche dans le NOM LÉGAL (raison sociale), PAS dans l'activité réelle.
   Un club de padel s'appelle souvent "Le Smash", "Ace Club", "Sport Plus" — pas "Padel XYZ".
3. Un appel sirene avec q="<mot-clé>" SANS filtre NAF (priority=3) pour les rares entreprises
   qui ont le mot dans leur raison sociale

CODES NAF POUR NICHES FRÉQUENTES :
Sports/Loisirs : 93.12Z (clubs de sports), 93.11Z (installations sportives), 93.13Z (centres de
culture physique), 93.29Z (loisirs : escape game, karting, bowling), 47.64Z (magasins de sport),
85.51Z (enseignement sportif)
Restauration : 56.10A (traditionnelle), 56.10C (rapide), 56.30Z (débits de boissons)
Services : 96.02A/96.02B (coiffure/beauté), 96.09Z (tatoueurs, etc.)

EXEMPLE — « boutiques de padel en PACA » :
{
    "api_calls": [
        {"source": "google_places", "action": "search", "params": {"query": "padel", "location": "PACA"}, "priority": 1},
        {"source": "sirene", "action": "search", "params": {"activite_principale": "93.12Z", "region": "93", "per_page": 25}, "priority": 2},
        {"source": "sirene", "action": "search", "params": {"activite_principale": "93.11Z", "region": "93", "per_page": 25}, "priority": 2},
        {"source": "sirene", "action": "search", "params": {"activite_principale": "47.64Z", "region": "93", "per_page": 25}, "priority": 2},
        {"source": "sirene", "action": "search", "params": {"q": "padel", "region": "93", "per_page": 25}, "priority": 3}
    ],
    "estimated_credits": 3,
    "description": "Multi-source padel PACA : Google Places + clubs (93.12Z) + installations (93.11Z) + détaillants sport (47.64Z) + recherche nom",
    "columns": ["nom", "siren", "siret", "activite_principale", "libelle_activite", "adresse", "code_postal", "ville", "tranche_effectif", "date_creation", "telephone", "site_web", "google_maps_url"]
}

RÈGLES GÉNÉRALES :
- Si l'utilisateur demande des dirigeants ou du CA, ajoute une étape Pappers APRÈS la recherche principale
- Limite la recherche SIRENE : utilise les filtres de tranche d'effectif pour réduire les résultats
- Si pas de tranche spécifiée et requête dit "PME" → tranche "11,12,21,22,31,32" (10-499 salariés)
- Maximum 500 résultats par requête (20 pages de 25)
- Si la requête est trop large, mets clarification_needed=true

RÈGLES GÉOGRAPHIE (CRITIQUES) :
- Pour les villes, utilise TOUJOURS "departement" (code à 2 chiffres) et NON "code_postal"
  Exemples : Paris → departement="75", Marseille → departement="13", Lyon → departement="69"
- N'utilise "code_postal" QUE si l'utilisateur donne un code postal exact à 5 chiffres (ex. "75008", "69003")
- NE JAMAIS utiliser code_postal="75000", "13000", "69000" etc. — ces codes n'existent pas
- **Île-de-France / IDF** (toute la région) : utilise **region="11"** (code INSEE région). **Interdit**
  de mettre uniquement **departement="75"** pour représenter l'IDF — le 75, c'est Paris seulement.
  Pour Paris seul, l'utilisateur doit parler explicitement de Paris (alors departement="75" ou code commune).

RÈGLES TEXTE LIBRE « q » (CRITIQUES) :
- Le paramètre "q" cherche dans la raison sociale / nom de l'entreprise, PAS dans la description d'activité
- NE JAMAIS mettre de mots-clés sectoriels dans "q" (SaaS, tech, BTP, fintech, etc.)
  quand section_activite_principale ou activite_principale est déjà renseigné
- "q" est utile UNIQUEMENT pour chercher un nom d'entreprise ou un terme métier très spécifique
- Si le secteur est identifié via code NAF → utilise section_activite_principale, pas "q"
- **Interdit** dans "q" : listes avec **virgules** du type « ESN, agence de développement » — l'API renvoie
  souvent zéro résultat. Un seul terme optionnel (ex. "ESN") ou laisse "q" absent.
- **Ne pas** combiner **q** avec **tranche_effectif_salarie** quand **section_activite_principale** (ou activite_principale) est
  déjà fixée — l'API renvoie souvent 0 résultat ; laisse **q** absent et garde secteur + effectif + zone.
"""

EFFECTIF_MAPPING = {
    (1, 2): "01",
    (3, 5): "02",
    (6, 9): "03",
    (10, 19): "11",
    (20, 49): "12",
    (50, 99): "21",
    (100, 199): "22",
    (200, 249): "31",
    (250, 499): "32",
    (500, 999): "41",
    (1000, 1999): "42",
    (2000, 4999): "51",
    (5000, 9999): "52",
    (10000, 999999): "53",
}

NAF_TO_SECTION = {
    "10": "C", "11": "C", "12": "C", "13": "C", "14": "C", "15": "C",
    "16": "C", "17": "C", "18": "C", "19": "C", "20": "C", "21": "C",
    "22": "C", "23": "C", "24": "C", "25": "C", "26": "C", "27": "C",
    "28": "C", "29": "C", "30": "C", "31": "C", "32": "C", "33": "C",
    "41": "F", "42": "F", "43": "F",
    "45": "G", "46": "G", "47": "G",
    "49": "H", "50": "H", "51": "H", "52": "H", "53": "H",
    "55": "I", "56": "I",
    "58": "J", "59": "J", "60": "J", "61": "J", "62": "J", "63": "J",
    "64": "K", "65": "K", "66": "K",
    "68": "L",
    "69": "M", "70": "M", "71": "M", "72": "M", "73": "M", "74": "M", "75": "M",
    "77": "N", "78": "N", "79": "N", "80": "N", "81": "N", "82": "N",
    "85": "P",
    "86": "Q", "87": "Q", "88": "Q",
}

NICHE_NAF_MAPPING: dict[str, list[str]] = {
    "padel": ["93.12Z", "93.11Z", "47.64Z"],
    "tennis": ["93.12Z", "93.11Z", "47.64Z"],
    "crossfit": ["93.12Z", "93.13Z"],
    "yoga": ["93.13Z", "85.51Z", "93.12Z"],
    "fitness": ["93.13Z", "93.12Z"],
    "musculation": ["93.13Z"],
    "escalade": ["93.12Z", "93.11Z", "93.29Z"],
    "golf": ["93.12Z", "93.11Z"],
    "natation": ["93.12Z", "93.11Z"],
    "surf": ["93.12Z", "93.29Z", "47.64Z"],
    "ski": ["93.12Z", "93.11Z", "47.64Z"],
    "equitation": ["93.12Z", "93.11Z"],
    "danse": ["85.52Z", "90.01Z", "93.12Z"],
    "karting": ["93.29Z", "93.11Z"],
    "bowling": ["93.29Z", "93.11Z"],
    "escape game": ["93.29Z"],
    "laser game": ["93.29Z"],
    "coworking": ["68.20B", "82.11Z"],
    "boulangerie": ["10.71C", "47.24Z"],
    "patisserie": ["10.71C", "47.24Z"],
    "pizzeria": ["56.10A", "56.10C"],
    "restaurant": ["56.10A", "56.10B", "56.10C"],
    "bar": ["56.30Z"],
    "brasserie": ["56.10A", "56.30Z"],
    "fleuriste": ["47.76Z"],
    "coiffeur": ["96.02A", "96.02B"],
    "coiffure": ["96.02A", "96.02B"],
    "beaute": ["96.02B"],
    "tatoueur": ["96.09Z"],
    "garage": ["45.20A", "45.20B"],
    "carrossier": ["45.20A"],
    "sport": ["93.12Z", "93.11Z", "93.13Z", "47.64Z"],
    "salle de sport": ["93.13Z", "93.12Z"],
    "club": ["93.12Z", "93.11Z"],
    "piscine": ["93.11Z", "93.12Z"],
}


def _detect_niche_naf_codes(entities) -> list[str]:
    """Détecte les codes NAF pertinents à partir des mots-clés et du secteur."""
    candidates: set[str] = set()
    terms = [w.lower() for w in (entities.mots_cles or [])]
    if entities.secteur:
        terms.append(entities.secteur.lower())

    for term in terms:
        for keyword, codes in NICHE_NAF_MAPPING.items():
            if keyword in term or term in keyword:
                candidates.update(codes)

    return sorted(candidates) if candidates else []


def _get_tranche_codes(taille_min: int | None, taille_max: int | None) -> list[str]:
    """Convert min/max employees to INSEE tranche codes."""
    if taille_min is None and taille_max is None:
        return []
    codes = []
    for (lo, hi), code in EFFECTIF_MAPPING.items():
        if taille_min is not None and hi < taille_min:
            continue
        if taille_max is not None and lo > taille_max:
            continue
        codes.append(code)
    return codes


async def run_orchestrator(guard_result: GuardResult) -> ExecutionPlan:
    guard_json = json.dumps(guard_result.model_dump(), ensure_ascii=False, default=str)

    try:
        result = await llm_json_call(
            model=settings.ORCHESTRATOR_MODEL,
            system=ORCHESTRATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Intent structuré :\n{guard_json}"}],
            max_tokens=2048,
            temperature=0.0,
        )
    except Exception:
        return _build_fallback_plan(guard_result)

    api_calls = []
    for call in result.get("api_calls", []):
        api_calls.append(APICall(
            source=call.get("source", "sirene"),
            action=call.get("action", "search"),
            params=call.get("params", {}),
            priority=call.get("priority", 1),
        ))

    if not api_calls:
        return _build_fallback_plan(guard_result)

    has_gp = any(c.source == "google_places" for c in api_calls)
    default_cols = _default_columns(guard_result.intent, with_google_places=has_gp)
    columns = result.get("columns", default_cols)
    if has_gp:
        for col in ("telephone", "site_web", "google_maps_url"):
            if col not in columns:
                columns.append(col)

    return ExecutionPlan(
        api_calls=api_calls,
        estimated_credits=result.get("estimated_credits", 1),
        description=result.get("description", "Recherche en cours..."),
        columns=columns,
        clarification_needed=result.get("clarification_needed", False),
        clarification_question=result.get("clarification_question"),
    )


def _build_fallback_plan(guard_result: GuardResult) -> ExecutionPlan:
    """Build a plan without LLM when the orchestrator fails."""
    e = guard_result.entities

    geo_params: dict = {}
    if e.localisation:
        from services.sirene import _ville_to_code_commune, _ville_fallback_departement
        code = _ville_to_code_commune(e.localisation)
        if code:
            geo_params["code_commune"] = code
        else:
            dept_fb = _ville_fallback_departement(e.localisation)
            if dept_fb:
                geo_params["departement"] = dept_fb
    if e.region and "departement" not in geo_params and "code_commune" not in geo_params:
        geo_params["region"] = e.region
    if e.departement and "code_commune" not in geo_params:
        if "region" not in geo_params:
            geo_params["departement"] = e.departement

    tranches = _get_tranche_codes(e.taille_min, e.taille_max)
    tranche_param = ",".join(tranches) if tranches else None

    niche_naf_codes = _detect_niche_naf_codes(e)

    api_calls: list[APICall] = []

    if e.mots_cles and _has_google_places_key():
        location = e.localisation or e.region or e.departement or ""
        if niche_naf_codes:
            gp_query = e.mots_cles[0]
        else:
            gp_query = " ".join(e.mots_cles)
            if e.secteur and e.secteur.lower() not in gp_query.lower():
                gp_query = f"{e.secteur} {gp_query}".strip()
        api_calls.append(APICall(
            source="google_places", action="search",
            params={"query": gp_query, "location": location},
            priority=0,
        ))

    if niche_naf_codes:
        for naf_code in niche_naf_codes[:4]:
            params: dict = {
                "activite_principale": naf_code,
                "per_page": 25,
                "etat_administratif": "A",
            }
            params.update(geo_params)
            if tranche_param:
                params["tranche_effectif_salarie"] = tranche_param
            api_calls.append(APICall(
                source="sirene", action="search", params=params, priority=1,
            ))

        if e.mots_cles:
            q_params: dict = {
                "q": e.mots_cles[0],
                "per_page": 25,
                "etat_administratif": "A",
            }
            q_params.update(geo_params)
            api_calls.append(APICall(
                source="sirene", action="search", params=q_params, priority=2,
            ))
    else:
        params = {"per_page": 25, "etat_administratif": "A"}
        params.update(geo_params)
        if e.code_naf:
            section = NAF_TO_SECTION.get(e.code_naf)
            if section:
                params["section_activite_principale"] = section
        if tranche_param:
            params["tranche_effectif_salarie"] = tranche_param
        if e.mots_cles:
            params["q"] = " ".join(e.mots_cles)
        api_calls.append(APICall(
            source="sirene", action="search", params=params, priority=1,
        ))

    if guard_result.intent == "recherche_dirigeant":
        api_calls.append(APICall(
            source="pappers", action="get_dirigeants", params={}, priority=3,
        ))

    credits = 1
    if guard_result.intent == "recherche_dirigeant":
        credits = 3
    if e.ca_min or e.ca_max:
        credits = 3
    if niche_naf_codes:
        credits = max(credits, 2)

    columns = _default_columns(guard_result.intent)
    if any(c.source == "google_places" for c in api_calls):
        for col in ("telephone", "site_web", "google_maps_url"):
            if col not in columns:
                columns.append(col)

    return ExecutionPlan(
        api_calls=api_calls,
        estimated_credits=credits,
        description="Recherche multi-source via SIRENE + Google Places",
        columns=columns,
    )


def _has_google_places_key() -> bool:
    return bool(settings.GOOGLE_PLACES_API_KEY)


def _default_columns(intent: str, *, with_google_places: bool = False) -> list[str]:
    base = ["nom", "siren", "siret", "activite_principale", "libelle_activite",
            "adresse", "code_postal", "ville", "tranche_effectif", "date_creation"]
    if with_google_places:
        base.extend(["telephone", "site_web", "google_maps_url"])
    if intent == "recherche_dirigeant":
        base.extend(["dirigeant_nom", "dirigeant_prenom", "dirigeant_fonction"])
    return base
