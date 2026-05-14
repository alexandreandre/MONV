---
name: cout-agent
description: >-
  Analyse un agent metier (prospection, rachat, benchmark, sous-traitant,
  creation d'entreprise), cartographie son implementation et liste des
  leviers concrets pour reduire les couts LLM/outils tout en conservant ou
  ameliorant la qualite. A utiliser lorsque l'utilisateur tape /cout-agent,
  demande de limiter les couts d'un agent, d'optimiser le budget tokens,
  ou attache explicitement ce skill.
disable-model-invocation: true
---

# /cout-agent — Limitation des couts par agent (performance maintenue ou meilleure)

## Objectif

Pour **un seul agent** parmi ceux ci-dessous, produire une liste **actionnable**
d’ameliorations orientees **reduction des couts** (tokens, appels API, outils,
recherches, stockage), **sans degradation** de la performance attendue — en
visant au minimum **la meme qualite**, idealement **mieux** (moins de bruit,
moins d’erreurs, moins de rejouer des etapes).

## Agents pris en charge

L’utilisateur designe explicitement l’un des types suivants :

- **prospection**
- **rachat**
- **benchmark**
- **sous-traitant**
- **creation d’entreprise** (agent creation d’entreprise)

Si le type n’est pas dans cette liste, **refuser poliment** et redemander un
choix parmi les cinq.

## Etape 0 — Cadrage

1. Confirmer **quel agent** (un des cinq).
2. Si possible, obtenir **ou se trouve l’agent** dans le depot (fichiers prompts,
   routes, workers, config modele) ; sinon, **chercher** (grep, recherche
   semantique) sur les noms, slugs, dossiers `agents`, `prompts`, `admin_agents`,
   etc.
3. Noter le **contexte d’usage** : synchrone/asynchrone, budget utilisateur,
   latence acceptable, risques (hallucination, conformite).

## Etape 1 — Cartographie cout / performance

Avant de recommander quoi que ce soit, **lire le flux reel** de l’agent :

- **Modele(s)** utilises (nom, variante, raison du choix).
- **System / developer / user prompts** : longueur, redondance, instructions
  contradictoires (sources de reponses longues ou de retries).
- **Outils / MCP / APIs** : frequence, parallelisme, payloads, pagination,
  idempotence, erreurs typiques.
- **Contexte injecte** : RAG, historique de conversation, documents joints —
  taille, filtrage, deduplication.
- **Boucles** : agent qui se rappelle lui-meme, multi-tours imposes, garde-fous
  manquants.
- **Sortie** : JSON structure, markdown long, champs inutiles pour l’aval.

Pour chaque zone, estimer qualitativement : **cout dominant** vs **levier
faible** (ne pas theoriser sans lien avec le code).

## Etape 2 — Leviers a inspecter systematiquement

Verifier chaque levier **dans le code** ; ne lister que ce qui s’applique ou
pourrait s’appliquer sans inventer d’integrations inexistantes.

### A. Prompts et format de sortie

- Raccourcir le prompt en **supprimant la repetition** et en **externalisant**
  les regles stables (versions, references courtes).
- Imposer un **schema de sortie strict** (JSON minimal) pour reduire tokens de
  reponse et les reparse / corrections.
- Separer **raisonnement interne** (si necessaire) et **livraison utilisateur**
  pour eviter d’exposer du texte inutile en production.
- Ajouter des **criteres d’arret** clairs (« si incertain, poser une seule
  question ciblee ») pour limiter les allers-retours.

### B. Choix et routage de modeles

- **Router** : taches simples sur modele economique, taches sensibles sur modele
  plus fort (classification legere en amont si deja present dans le projet).
- **Limiter la temperature** la ou la determinisme reduit les regenerations.
- Eviter les **modeles surdimensionnes** pour des extractions ou du formatage.

### C. Contexte et memoire

- **Resume** l’historique au lieu de le coller en entier (avec points de verite
  cites : IDs, extraits courts).
- **Filtrer** le RAG (top-k, score seuil, dedup) ; preferer des extraits courts
  cites plutot que des pages entieres.
- **Ne pas** renvoyer des documents volumineux au modele si une **cle** ou un
  resume suffit pour la decision suivante.

### D. Outils et integrations

- **Batch** les appels quand l’API le permet ; **cache** les lectures stables
  (TTL, etag, hash du prompt d’outil).
- Reduire la **taille des reponses** outil (champs demandes, projection).
- **Retry avec backoff** et plafond pour eviter les spirales couteuses.
- Desactiver les outils **non utilises** sur ce parcours precis.

### E. Orchestration et fiabilite

- **Paralleliser** les lectures independantes ; **sequencer** seulement ce qui
  depend mutuellement (moins de tours agent).
- **Verifier** avec du code non-LLM (parseur, regex, validateur) avant de
  redemander au modele.
- **Garde-fous** sur tokens max, nombre max d’appels, timeout — fail fast avec
  message utile plutot que boucle.

### F. Observabilite (pour prouver le gain)

- Journaliser **tokens in/out**, **cout estime**, **nombre d’appels** par etape
  (sans secrets).
- Definir **1–3 metriques de qualite** (taux de succes, temps humain corrige,
  precision metier) pour ne pas « economiser » au detriment du resultat.

## Etape 3 — Format de livraison obligatoire

Repondre en **francais**, structure ainsi :

1. **Synthese en 3–5 lignes** : ou part le cout aujourd’hui (hypotheses liees au
   code).
2. **Tableau des ameliorations** (colonnes) :
   - **Amelioration** (titre court)
   - **Zone** (prompt / modele / contexte / outil / orchestration / obs)
   - **Impact cout** (faible / moyen / fort) + explication en une phrase
   - **Risque qualite** (faible / moyen / fort) + mitigation en une phrase
   - **Fichiers ou points d’ancrage** dans le depot (chemins ou symboles)
3. **Quick wins** : 3 actions les plus rentables en premier.
4. **Mesure** : quoi instrumenter pour valider apres changement.

Ne pas proposer de modifications de code **hors perimetre** demande ; si une
idee est pertinente mais hors depot, la marquer clairement comme **piste
externe** (ex. facturation provider).

## Exemples d’invocation

- `/cout-agent prospection` — apres quoi l’agent lit le flux prospection dans
  le repo et applique les etapes ci-dessus.
- « Optimise le cout de l’agent **rachat** sans baisser la qualite » + attacher
  ce skill.

## Anti-patterns

- Recommandations **generiques** non reliees au code (liste LLM 101).
- « Passer tout en petit modele » sans **router** ni critere de risque.
- Sacrifier la **tracabilite** (sources, citations) la ou le metier l’exige,
  sans le signaler comme compromis conscient.
