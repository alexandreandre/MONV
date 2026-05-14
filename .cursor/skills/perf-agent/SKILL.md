---
name: perf-agent
description: >-
  Brainstorme et priorise des idees d'amelioration des performances (latence,
  cout, qualite des sorties, fiabilite, scalabilite) pour un agent metier donne
  parmi prospection, rachat, benchmark, sous-traitant, creation d'entreprise.
  Couvre architecture, APIs, prompts, donnees, observabilite et tout levier
  pertinent. A utiliser lorsque l'utilisateur tape /perf-agent, demande des
  idees de performance pour un agent, ou attache explicitement ce skill.
disable-model-invocation: true
---

# /perf-agent — Idees de performance pour un agent metier

Objectif : pour **un agent que l'utilisateur designe** parmi la liste ci-dessous,
proposer **le plus large eventail possible** d'idees pour **ameliorer les
performances** (vitesse, cout, qualite utile, taux de reussite, robustesse sous
charge), sans se limiter a un seul domaine technique.

## Agents concernes (choix explicite)

L'utilisateur doit indiquer **lequel** :

- **prospection**
- **rachat**
- **benchmark**
- **sous-traitant**
- **creation d'entreprise** (agent creation d'entreprise)

Si l'agent n'est pas dans cette liste, traiter la demande comme un agent
metier **equivalent** en conservant la meme methode d'analyse.

## Etape 0 — Cadrer la performance

Avant de proposer des idees, clarifier (ou inferer depuis le depot / le
contexte) **quels indicateurs** comptent le plus pour cet agent :

- Temps de reponse (TTFT, latence totale)
- Cout par tache (tokens, appels externes)
- Qualite / precision des livrables
- Taux d'echec, retries, besoin d'intervention humaine
- Debit (taches par minute), files d'attente, concurrence

Si l'utilisateur n'a rien precise, **enumerer les metriques plausibles** pour
cet agent et couvrir chacune dans les idees.

## Etape 1 — Cartographier l'agent dans le produit

Explorer le code et la config **lies a cet agent** (routes, services, prompts,
schemas, files, integrations tierces, regles metier). Identifier :

- Pipeline complet (entrees, etapes intermediaires, sorties)
- Dependances synchrones (LLM, DB, recherche web, scraping, email, etc.)
- Points de serialisation et de duplication de travail
- Donnees figees vs donnees temps reel

Si le perimetre est flou, delimiter ce qui appartient a l'agent vs au reste de
l'app, puis se concentrer sur le chemin critique.

## Etape 2 — Generer des idees (large spectre)

Generer **au minimum 15 idees**, viser **25–40** si le contexte le permet.
Balayer **systematiquement** les familles suivantes (pas seulement « optimiser
le prompt ») :

| Famille | Exemples de leviers (non exhaustif) |
|---------|-------------------------------------|
| **Architecture** | decoupage en micro-etapes, orchestrateur leger, workers asynchrones, files, idempotence, circuit breaker |
| **APIs et integrations** | nouveaux endpoints dedies, batching, webhooks, contrats de donnees plus stricts, versions d'API |
| **Donnees et cache** | cache applicatif, memoire de session, embeddings / index, pre-calculs, materiel vue lecture seule |
| **Modele et prompts** | routage par sous-tache, modeles moins chers pour les etapes triviales, sortie structuree, contraintes de longueur |
| **Parallelisme** | appels LLM ou IO en parallele quand independants, map-reduce sur lots |
| **Qualite / fiabilite** | validation automatique des sorties, garde-fous, self-check, schemas JSON stricts |
| **Observabilite** | traces par etape, metriques par agent, budgets de tokens, alertes sur regressions |
| **Securite / conformite** (si impact perf indirect) | reduction de surface, filtrage en amont pour eviter re-traitements couteux |
| **UX produit** | streaming, etats partiels, taches en arriere-plan, estimation de progression |

Chaque idee doit etre **concrete** (verbe d'action + objet + effet attendu),
pas du generique (« ameliorer l'architecture »).

### Regles de priorisation

- Taguer chaque idee : **impact** (haut / moyen / bas) et **effort** (petit /
  moyen / gros).
- Mettre en avant les **quick wins** (haut impact, petit effort).
- Indiquer quand une idee suppose un **trade-off** (ex. moins de cout vs moins
  de nuance).

## Etape 3 — Livrable utilisateur

Presenter en francais :

1. **Resume** : 3–5 leviers majeurs pour cet agent.
2. **Tableau** des idees (colonnes : #, idee, famille, impact, effort, risque
   ou trade-off eventuel).
3. **Quick wins** numerotes.
4. **Investissements structurants** (gros effort, fort effet durable).
5. **Pistes d'API / contrats** : si pertinent, lister des endpoints ou formats
   de payload qui reduiraient les allers-retours ou le bruit.
6. **Mesure** : quelle metrique suivre pour valider le gain (avant / apres).

Ne pas implementer de code **sauf** demande explicite de l'utilisateur apres la
liste ; ce skill vise d'abord l'**inventaire et la priorisation**.

## Etape 4 — Optionnel : alignment metier par type d'agent

Quand ca aide sans inventer de faux besoins, relier les idees au **job-to-be-
done** typique :

- **Prospection** : volume de leads, personnalisation vs genericite, fraicheur
  des donnees.
- **Rachat** : profondeur d'analyse financiere / legale, sources fiables,
  coherence multi-documents.
- **Benchmark** : comparabilite, fraicheur des comparables, granularite.
- **Sous-traitant** : conformite cahier des charges, delais, reutilisation de
  livrables.
- **Creation d'entreprise** : exhaustivite administrative, erreurs bloquantes,
  parcours guide.

Ces rappels servent a **orienter** les idees, pas a remplacer l'analyse du code
reel du projet.
