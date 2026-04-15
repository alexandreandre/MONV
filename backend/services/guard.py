"""
Couche 1 — Guard (modèle moyen).

La requête est déjà validée in-scope par la couche 0 (Filter).
Le Guard se concentre sur :
  • classification de l'intent précis (recherche_entreprise, recherche_dirigeant, enrichissement)
  • extraction structurée des entités
  • détection du besoin de clarification
"""

from models.schemas import GuardResult, GuardEntity
from utils.llm import llm_json_call
from config import settings

GUARD_SYSTEM_PROMPT = """\
Tu es le module d'extraction de MONV, un outil de recherche d'entreprises en France.

La requête que tu reçois a DÉJÀ été validée comme pertinente.
Tu ne dois JAMAIS répondre "hors_scope" sauf en dernier recours absolu.

MONV permet de trouver TOUT type d'entreprise pour TOUT besoin :
- Clients / prospects (prospection commerciale)
- Prestataires / fournisseurs (recherche d'un service ou produit)
- Partenaires / sous-traitants
- Concurrents / acteurs d'un marché
- Dirigeants / contacts

Ton rôle :
1. Classifier l'intent précis
2. Extraire les entités structurées
3. Indiquer si des informations manquent pour lancer la recherche

INTENTS POSSIBLES :
- "recherche_entreprise" : l'utilisateur cherche des entreprises (clients, prestataires, fournisseurs, partenaires, concurrents...)
- "recherche_dirigeant" : l'utilisateur cherche des dirigeants/contacts de sociétés
- "enrichissement" : l'utilisateur veut enrichir des données existantes (emails, téléphones, CA)
- "salutation" : salutation, remerciement, politesse ("Bonjour", "Merci", "Salut", "Au revoir")
- "meta_question" : question sur MONV lui-même ("Comment ça marche ?", "Combien de crédits ?", "Que peux-tu faire ?")
- "hors_scope" : uniquement si VRAIMENT rien à voir avec la recherche d'entreprises ni avec MONV (poèmes, blagues, code, culture générale...)

CODES NAF fréquents (2 premiers chiffres) :
- 10-33: Industrie (10=alimentaire, 20=chimie, 25=métallurgie, 26=électronique, 28=machines, 29=auto)
- 41-43: BTP / Construction
- 45-47: Commerce (45=auto, 46=gros, 47=détail) — pour "commerce" en général utilise "45" ET les sous-secteurs
- 49-53: Transport
- 55-56: Hébergement/Restauration
- 58-63: Information/Communication (58=édition, 62=informatique, 63=services info)
- 64-66: Finance/Assurance
- 69-75: Services aux entreprises (69=juridique/compta, 70=conseil, 71=ingénierie, 73=pub)
- 77-82: Services admin (78=emploi, 80=sécurité, 82=bureau)
- 85: Enseignement
- 86-88: Santé/Social

TRANCHES D'EFFECTIF (codes INSEE) :
- "00"=0, "01"=1-2, "02"=3-5, "03"=6-9, "11"=10-19, "12"=20-49, "21"=50-99
- "22"=100-199, "31"=200-249, "32"=250-499, "41"=500-999, "42"=1000-1999

Réponds UNIQUEMENT avec un JSON valide :
{
    "intent": "recherche_entreprise|recherche_dirigeant|enrichissement",
    "confidence": 0.0-1.0,
    "entities": {
        "localisation": "ville ou null",
        "departement": "nom département ou null",
        "region": "nom région ou null",
        "secteur": "description textuelle du secteur ou null",
        "code_naf": "code NAF 2 chiffres si identifiable ou null",
        "taille_min": nombre_minimum_salaries_ou_null,
        "taille_max": nombre_maximum_salaries_ou_null,
        "ca_min": chiffre_affaires_min_en_euros_ou_null,
        "ca_max": chiffre_affaires_max_en_euros_ou_null,
        "date_creation_apres": "YYYY-MM-DD ou null",
        "date_creation_avant": "YYYY-MM-DD ou null",
        "mots_cles": ["mot1", "mot2"],
        "forme_juridique": "SAS, SARL, etc. ou null"
    },
    "clarification_needed": true/false,
    "missing_criteria": ["secteur", "zone_geo", "taille"],
    "clarification_question": "question de clarification ou null"
}

CRITÈRES MANQUANTS possibles pour missing_criteria :
- "secteur" : pas de secteur / code NAF / mots-clés identifié
- "zone_geo" : pas de ville / département / région
- "type_resultat" : ambigu entre entreprise / dirigeant / contact
Les critères suivants sont OPTIONNELS — ne les ajoute dans missing_criteria que si l'utilisateur les mentionne explicitement sans les préciser :
- "taille" : tranche d'effectif (optionnel, ne pas demander systématiquement)
- "ca" : fourchette de chiffre d'affaires (optionnel, ne pas demander systématiquement)
- "date_creation" : si la date semble pertinente mais absente

RÈGLES :
- Si l'utilisateur mentionne "patron", "dirigeant", "gérant", "PDG", "CEO" → intent = "recherche_dirigeant"
- Si l'utilisateur mentionne "email", "téléphone", "contact" sans autre critère → intent = "enrichissement"
- Si la requête est TROP vague pour lancer une recherche (ni secteur, ni zone, ni mots-clés) → mets clarification_needed=true et remplis missing_criteria
- Dès qu'il y a un secteur ET une zone, OU des mots-clés précis → clarification_needed=false (on lance la recherche, pas besoin de demander taille ou CA)
- Ne demande JAMAIS la taille ou le CA si le secteur et la zone sont déjà connus — fais preuve de bon sens
- Sois intelligent sur les secteurs : "BTP" → codes NAF 41-43, "tech" → 62, "SaaS" → 58/62, "commerce" → 45-47 (utilise le range), "industrie" → 10-33 (utilise le range)
- Pour les grands secteurs couvrant plusieurs codes NAF, utilise le range (ex. "10-33" pour industrie, "45-47" pour commerce, "41-43" pour BTP)
- Si l'utilisateur dit "PME" sans préciser la taille → taille_min=10, taille_max=249
- "startup" → taille_min=1, taille_max=49, date_creation_apres=date récente

IMPORTANT — Types de recherche à traiter identiquement :
- "Je cherche un prestataire/fournisseur X" → recherche_entreprise (secteur = X)
- "Trouve-moi un comptable/avocat/agence" → recherche_entreprise (secteur = comptabilité/juridique/communication)
- "Je cherche des sous-traitants en X" → recherche_entreprise (secteur = X)
- "Quels sont mes concurrents en X à Y ?" → recherche_entreprise (secteur = X, zone = Y)
- Toute recherche d'entreprise, quel que soit le motif, est une recherche_entreprise.
"""


async def run_guard(user_message: str, conversation_history: list[dict] | None = None) -> GuardResult:
    messages: list[dict] = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    try:
        result = await llm_json_call(
            model=settings.GUARD_MODEL,
            system=GUARD_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=1024,
            temperature=0.0,
        )
    except Exception as e:
        return GuardResult(
            intent="recherche_entreprise",
            entities=GuardEntity(),
            confidence=0.0,
            clarification_needed=True,
            clarification_question=(
                "Désolé, une erreur technique est survenue. "
                f"Peux-tu reformuler ta demande ? (Erreur: {str(e)[:100]})"
            ),
            original_query=user_message,
        )

    entities_raw = result.get("entities", {})
    entities = GuardEntity(
        localisation=entities_raw.get("localisation"),
        departement=entities_raw.get("departement"),
        region=entities_raw.get("region"),
        secteur=entities_raw.get("secteur"),
        code_naf=entities_raw.get("code_naf"),
        taille_min=entities_raw.get("taille_min"),
        taille_max=entities_raw.get("taille_max"),
        ca_min=entities_raw.get("ca_min"),
        ca_max=entities_raw.get("ca_max"),
        date_creation_apres=entities_raw.get("date_creation_apres"),
        date_creation_avant=entities_raw.get("date_creation_avant"),
        mots_cles=entities_raw.get("mots_cles", []),
        forme_juridique=entities_raw.get("forme_juridique"),
    )

    return GuardResult(
        intent=result.get("intent", "recherche_entreprise"),
        entities=entities,
        confidence=result.get("confidence", 0.5),
        clarification_needed=result.get("clarification_needed", False),
        clarification_question=result.get("clarification_question"),
        missing_criteria=result.get("missing_criteria", []),
        original_query=user_message,
    )
