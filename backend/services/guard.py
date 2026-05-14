"""
Couche 1 — Guard (modèle moyen).

La requête est déjà validée in-scope par la couche 0 (Filter).
Le Guard se concentre sur :
  • classification de l'intent précis (recherche_entreprise, recherche_dirigeant, enrichissement)
  • extraction structurée des entités
  • détection du besoin de clarification
  • ambiguïté sectorielle : second passage LLM optionnel (prompt long) si détecteur lexical
"""

from models.schemas import GuardResult, GuardEntity, GUARD_INTENT_VALUES
from services.guard_ambiguity import (
    message_triggers_sector_ambiguity_check,
    run_guard_sector_ambiguity,
)
from services.zone_policy import post_process_guard_geography
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
sector_ambiguous — NOYAU (liste longue en second passage conditionnel)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Un **second module** applique la longue liste d’ambiguïtés sectorielles B2B (sport, restauration,
services, etc.) **uniquement** lorsqu’un détecteur lexical interne l’active. Tu n’as **pas** cette liste
dans ce prompt.

Règles pour **cet** appel :
- Si le message énumère **plusieurs types d’établissements complémentaires** (souvent après QCM,
  ex. boutiques de padel **et** clubs de padel) : **sector_ambiguous: false**, retire **"secteur_confirmation"**
  de missing_criteria, et mets **tous** les types dans **mots_cles** ; ne redemande pas de clarification
  sectorielle unique pour ce cas.
- Sinon : **sector_ambiguous: true** seulement si tu es **sans doute** que le cœur métier est polysémique
  B2B **sans** la longue liste (ex. « spa » seul, « laser » seul, « pressing » sans précision…).
- Si tu doutes : **false** (le second passage reprendra quand le détecteur l’ordonnera).

Quand sector_ambiguous: true :
- clarification_needed DOIT être true
- missing_criteria DOIT contenir "secteur_confirmation"
- Si aucune zone géographique explicite (voir bloc « ZONE EXPLICITE » plus bas), ajoute aussi "zone_geo".

Quand sector_ambiguous: false : ne mets pas "secteur_confirmation" dans missing_criteria **pour cause**
d’ambiguïté sectorielle seule.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Réponds UNIQUEMENT avec un JSON valide :
{
    "intent": "recherche_entreprise|recherche_dirigeant|enrichissement|salutation|meta_question|hors_scope",
    "confidence": 0.0-1.0,
    "context_hints": [],
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
    "missing_criteria": [],
    "clarification_question": "question de clarification ou null",
    "sector_ambiguous": false,
    "sector_confirmed": null
}

Champ **context_hints** (tableau de 0 à 5 courtes chaînes en français) :
- Nuances utiles pour adapter le **ton** et les **libellés** du QCM de clarification (contrainte budget,
  urgence, type de décideur, cible B2B précise, etc.).
- **Interdit** d'y mettre une zone ou un secteur si ce n'est pas déjà dans entities ou le message :
  pour la géographie et le métier, utilise entities et missing_criteria.
- Ne remplace **jamais** missing_criteria : ce sont des indices conversationnels, pas des critères structurés.

Les champs sector_ambiguous (bool) et sector_confirmed (string ou null, rempli seulement après clarification utilisateur — laisse null à l'extraction) doivent TOUJOURS être présents dans le JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ZONE GÉOGRAPHIQUE — EXIGENCE (recherche_entreprise & recherche_dirigeant)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Remplis localisation / departement / region **uniquement** si l'utilisateur les formule
explicitement dans son message. Aucune inférence géographique (pas de « probablement à Paris »,
pas de zone déduite du secteur seul).

Considère qu'une zone est **explicite** si le texte contient par exemple :
- une ou plusieurs communes / villes (« à Lyon », « Paris et petite couronne ») ;
- un département nommé ou numéroté (« 69 », « Hérault ») ;
- une région française (« PACA », « Grand Est », « Île-de-France ») ;
- un périmètre national clair (« France entière », « toute la France », « en France » pour
  le territoire de recherche, « échelle nationale », « sans limite géographique »).

Si aucune de ces informations n'est présente → laisse localisation, departement et region à
**null** et inclus **"zone_geo"** dans missing_criteria (même si le secteur est déjà clair,
même en mode benchmark / rachat / sous-traitant côté intention — le mode ne dispense pas
de cadrer la géographie).

Intent **enrichissement** (fiche SIREN, contacts d'une société déjà identifiée) : n'ajoute pas
"zone_geo" sauf si l'utilisateur lance une recherche ouverte d'établissements.

CRITÈRES MANQUANTS possibles pour missing_criteria :
- "secteur_confirmation" : secteur ambigu (sector_ambiguous true) — précision d'activité
- "secteur" : pas de secteur / code NAF / mots-clés identifié
- "zone_geo" : pas de ville / département / région / périmètre national explicite dans le message
- "type_resultat" : ambigu entre entreprise / dirigeant / contact
Les critères suivants sont OPTIONNELS — ne les ajoute dans missing_criteria que si l'utilisateur les mentionne explicitement sans les préciser :
- "taille" : tranche d'effectif (optionnel, ne pas demander systématiquement)
- "ca" : fourchette de chiffre d'affaires (optionnel, ne pas demander systématiquement)
- "date_creation" : si la date semble pertinente mais absente

RÈGLES :
- Si l'utilisateur mentionne "patron", "dirigeant", "gérant", "PDG", "CEO" → intent = "recherche_dirigeant"
- Si l'utilisateur mentionne "email", "téléphone", "contact" sans autre critère → intent = "enrichissement"
- Si la requête est TROP vague pour lancer une recherche (ni secteur, ni zone, ni mots-clés) → mets clarification_needed=true et remplis missing_criteria
- Dès qu'il y a un secteur non ambigu ET une zone **explicitement** posée dans le message (voir bloc ZONE), OU des mots-clés précis sans ambiguïté sectorielle ET une zone explicite → clarification_needed=false pour les seuls critères optionnels (on ne demande pas taille ni CA). Sans zone explicite → garde ou ajoute "zone_geo" et clarification_needed=true. Si sector_ambiguous=true, clarification_needed reste true ; missing_criteria contient au minimum "secteur_confirmation" et "zone_geo" si la zone n'est pas dans le message.
- Ne demande JAMAIS la taille ou le CA si le secteur et la zone sont déjà connus — fais preuve de bon sens
- Sois intelligent sur les secteurs : "BTP" → codes NAF 41-43, "tech" → 62, "SaaS" → 58/62, "commerce" → 45-47 (utilise le range), "industrie" → 10-33 (utilise le range)
- Pour les grands secteurs couvrant plusieurs codes NAF, utilise le range (ex. "10-33" pour industrie, "45-47" pour commerce, "41-43" pour BTP)
- Si l'utilisateur dit "PME" sans préciser la taille → taille_min=10, taille_max=249
- "startup" → taille_min=1, taille_max=49, date_creation_apres=date récente

RÈGLE CRITIQUE — mots_cles = CRITÈRES DE RECHERCHE uniquement :
"mots_cles" ne doit contenir QUE les termes utiles pour IDENTIFIER / TROUVER les entreprises cibles.
NE JAMAIS inclure dans mots_cles les mots qui décrivent le MOTIF ou L'INTENTION de l'utilisateur.
Exemples de mots à EXCLURE de mots_cles :
- Motifs business : rachat, acquisition, investissement, revente, cession, reprise, fusion, croissance, diversification, partenariat, collaboration
- Analyse : analyse, potentiel, benchmark, étude, audit, veille, diagnostic, comparaison, évaluation
- Prospection : prospection, démarche, approche, ciblage, qualification, leads
- Général : recherche, cherche, trouve, besoin, intéressé, souhaite
Seuls les termes qui DÉCRIVENT l'activité, le produit, ou le type d'entreprise recherchée sont pertinents.
Exemple : "hôtels 3 étoiles à Marseille pour un rachat" → mots_cles=["hôtel", "3 étoiles"], PAS ["hôtel", "3 étoiles", "rachat"]

IMPORTANT — Types de recherche à traiter identiquement :
- "Je cherche un prestataire/fournisseur X" → recherche_entreprise (secteur = X)
- "Trouve-moi un comptable/avocat/agence" → recherche_entreprise (secteur = comptabilité/juridique/communication)
- "Je cherche des sous-traitants en X" → recherche_entreprise (secteur = X)
- "Quels sont mes concurrents en X à Y ?" → recherche_entreprise (secteur = X, zone = Y)
- Toute recherche d'entreprise, quel que soit le motif, est une recherche_entreprise.
"""


_INTENT_NOISE_WORDS: set[str] = {
    "rachat", "acquisition", "investissement", "revente", "cession",
    "reprise", "fusion", "croissance", "diversification", "partenariat",
    "collaboration", "analyse", "potentiel", "benchmark", "étude",
    "audit", "veille", "diagnostic", "comparaison", "évaluation",
    "prospection", "démarche", "approche", "ciblage", "qualification",
    "leads", "recherche", "cherche", "trouve", "besoin", "intéressé",
    "souhaite", "stratégie", "strategie", "opportunité", "opportunite",
    "marché", "marche", "rentabilité", "rentabilite", "projet",
    "objectif", "but", "ambition", "expansion", "développement",
    "developpement", "implantation", "consolidation",
}


def _clean_mots_cles(raw: list[str]) -> list[str]:
    """Retire les mots décrivant l'intention business de l'utilisateur, pas la cible de recherche."""
    cleaned = [
        w for w in raw
        if w.lower().strip() not in _INTENT_NOISE_WORDS
    ]
    return cleaned if cleaned else raw[:1]


def _parse_bool_llm(value: object, default: bool = False) -> bool:
    """Interprète un booléen renvoyé par le LLM (JSON strict ou chaîne résiduelle)."""
    if value is True:
        return True
    if value is False:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "oui")
    return default


def _parse_sector_confirmed(value: object) -> str | None:
    """Normalise sector_confirmed : null, chaîne vide → None."""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return str(value)


def sanitize_context_hints(raw: object, *, max_items: int = 5, max_len: int = 200) -> list[str]:
    """Indices souples pour le QCM — hors contrat orchestrateur."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw[:max_items]:
        if isinstance(item, str):
            s = " ".join(item.split())
            if s and len(s) <= max_len:
                out.append(s)
    return out


async def run_guard(
    user_message: str,
    conversation_history: list[dict] | None = None,
    *,
    agent_id: str = "prospection",
    block_id: str = "guard",
) -> GuardResult:
    messages: list[dict] = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    from services.agent_config import resolve_llm_for_block
    from utils.llm import llm_json_call

    cfg = await resolve_llm_for_block(
        agent_id,
        block_id,
        default_model=settings.GUARD_MODEL,
        default_system=GUARD_SYSTEM_PROMPT,
        default_max_tokens=1024,
        default_temperature=0.0,
    )
    try:
        result = await llm_json_call(
            model=cfg.model,
            system=cfg.system_prompt,
            messages=messages,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            usage_stage="guard",
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
            context_hints=[],
            original_query=user_message,
        )

    entities_raw = result.get("entities", {}) or {}
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
        mots_cles=_clean_mots_cles(entities_raw.get("mots_cles", [])),
        forme_juridique=entities_raw.get("forme_juridique"),
    )

    sector_ambiguous_core = _parse_bool_llm(result.get("sector_ambiguous"), False)
    sector_confirmed = _parse_sector_confirmed(result.get("sector_confirmed"))

    sector_ambiguous = sector_ambiguous_core
    if settings.GUARD_SECTOR_AMBIGUITY_SECOND_PASS and (
        message_triggers_sector_ambiguity_check(user_message)
    ):
        try:
            sector_ambiguous = await run_guard_sector_ambiguity(
                user_message,
                agent_id=agent_id,
            )
        except Exception:
            sector_ambiguous = sector_ambiguous_core

    # ── Cohérence sector_ambiguous → clarification forcée ──────────────
    # Le LLM peut renvoyer sector_ambiguous=True sans mettre
    # clarification_needed=True. On force la cohérence ici côté code,
    # sans dépendre du modèle pour cette logique critique.
    if sector_ambiguous:
        clarification_needed_final = True
        missing_final = list(result.get("missing_criteria") or [])
        if "secteur_confirmation" not in missing_final:
            missing_final = ["secteur_confirmation"] + [
                m for m in missing_final
                if m not in ("secteur", "secteur_confirmation")
            ]
    else:
        clarification_needed_final = result.get("clarification_needed", False)
        missing_final = [
            m
            for m in (result.get("missing_criteria") or [])
            if m != "secteur_confirmation"
        ]

    intent_val = result.get("intent", "recherche_entreprise")
    if not isinstance(intent_val, str) or intent_val not in GUARD_INTENT_VALUES:
        intent_val = "recherche_entreprise"
    clarification_needed_final = post_process_guard_geography(
        user_message,
        intent_val,
        entities,
        missing_final,
        clarification_needed_final,
    )

    return GuardResult(
        intent=intent_val,
        entities=entities,
        confidence=result.get("confidence", 0.5),
        clarification_needed=clarification_needed_final,
        clarification_question=result.get("clarification_question"),
        missing_criteria=missing_final,
        context_hints=sanitize_context_hints(result.get("context_hints")),
        sector_ambiguous=sector_ambiguous,
        sector_confirmed=sector_confirmed,
        original_query=user_message,
    )
