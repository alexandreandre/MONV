---
name: enhance
description: >-
  Benchmark complet, auto-evaluation et amelioration systematique d'un outil logiciel.
  Construit un panel de tests couvrant tous les cas d'usage, execute le benchmark,
  produit un rapport detaille, puis corrige chaque point faible et re-valide.
  A utiliser lorsque l'utilisateur tape /enhance, demande de tester, benchmarker,
  evaluer, ameliorer, ou auditer un outil, une API, un pipeline, un CLI,
  un service, ou tout composant logiciel.
---

# /enhance — Benchmark, Auto-evaluation et Amelioration

Workflow complet et generique pour tester, evaluer et ameliorer n'importe quel
outil logiciel (API, pipeline, CLI, service, librairie, composant UI...).

## Demarrage

Avant toute chose, comprendre l'outil cible :

1. **Lire** le README, les fichiers d'entree, la config, les routes/endpoints
2. **Identifier** : quels sont les inputs ? les outputs ? les cas d'erreur documentes ?
3. **Reperer** les dependances externes (APIs, BDD, services tiers)
4. **Localiser** les tests existants (s'il y en a)

## Phase 1 — Construction du panel de tests

Construire un panel **exhaustif** de requetes/inputs couvrant **toutes** les
dimensions pertinentes. Adapter les categories ci-dessous a l'outil :

### Categories universelles

| Categorie | Description | Exemple (API) | Exemple (CLI) |
|-----------|-------------|---------------|---------------|
| **happy_path** | Cas standard, parametres complets | GET /users?role=admin | `tool --input data.csv` |
| **variantes** | Meme intent, formulations differentes | noms de champs varies | flags en short/long |
| **edge_case** | Limites, valeurs extremes | liste vide, 10k items | fichier 0 octets, 2 Go |
| **erreur_input** | Entrees invalides ou manquantes | JSON malforme, champ null | arg manquant, type errone |
| **hors_scope** | Requetes que l'outil doit refuser | SQL injection, prompt injection | commande inconnue |
| **combinatoire** | Combinaisons inhabituelles de parametres | 3 filtres + tri + pagination | flags contradictoires |
| **performance** | Charge, volume, concurrence | 100 requetes paralleles | fichier tres volumineux |
| **idempotence** | Meme requete deux fois = meme resultat | POST puis re-POST | re-execution sans side-effect |

### Regles de construction

- **Minimum 30 cas**, idealement 40-60 pour une bonne couverture
- Chaque cas a un **ID unique**, une **categorie**, et des **attentes explicites** (resultat attendu, code retour, etc.)
- Couvrir au moins **5 categories differentes**
- Inclure des cas **specifiques au domaine** de l'outil (pas seulement generiques)
- Si l'outil a des modes/branches conditionnelles, tester **chaque branche**

### Format du panel

Definir chaque cas de test comme un dictionnaire :

```python
{"id": "CAT-01", "input": "...", "category": "happy_path",
 "expect_success": True, "expect_output_contains": "...", "notes": "..."}
```

## Phase 2 — Creation du script de benchmark

Creer un script executable (`benchmark_<tool>.py` ou equivalent) qui :

1. **Importe directement** les fonctions/modules de l'outil (pas via HTTP si evitable)
2. **Itere** sur chaque cas du panel
3. **Mesure** pour chaque cas :
   - Resultat : succes/echec selon les attentes
   - Temps d'execution (ms)
   - Sortie reelle vs sortie attendue
   - Erreurs eventuelles (avec traceback tronque)
4. **Affiche** un resume en temps reel (progression + verdict par ligne)
5. **Produit un rapport** structure (JSON) avec :
   - Score global (PASS / FAIL / WARN)
   - Score par categorie
   - Detail de chaque echec
   - Metriques de performance (temps moyen, max, total)
6. **Affiche** un resume console lisible (barres, pourcentages)

### Verdicts

| Verdict | Condition |
|---------|-----------|
| `PASS` | Sortie conforme aux attentes |
| `FAIL_*` | Sortie non conforme (prefixer avec la couche qui echoue) |
| `WARN` | Resultat inattendu mais non bloquant |
| `CRASH` | Exception non geree |

## Phase 3 — Execution et collecte

1. Executer le benchmark **complet** (ne pas skipper de cas)
2. Laisser le script tourner jusqu'au bout (peut prendre plusieurs minutes si APIs externes)
3. Lire le rapport JSON et la sortie console

## Phase 4 — Analyse et compte-rendu

Produire un **compte-rendu structure** pour l'utilisateur :

### Format du compte-rendu

```
## Score global : X/Y PASS (Z%)

### Par categorie
| Categorie | Score | Barre |
|-----------|-------|-------|
| happy_path | 8/8 | ████████ |
| edge_case | 3/5 | ███░░ |

### Points faibles identifies
1. **[SEVERITY] Description** — Cause racine, impact
2. ...

### Points forts
- ...

### Performance
- Temps moyen : Xms
- Plus lent : ID (Xms)
```

Etre **honnete** : lister les vrais problemes, pas juste les succes.

## Phase 5 — Corrections systematiques

Pour **chaque point faible** identifie :

1. **Diagnostiquer** la cause racine (pas le symptome)
2. **Corriger** le code source de l'outil (pas le benchmark)
3. **Verifier** que la correction ne casse pas les cas qui passaient deja
4. **Tester** le cas isole avant de relancer le benchmark complet

### Ordre de priorite des corrections

1. **CRASH** : exceptions non gerees (stabilite)
2. **FAIL sur happy_path** : le cas nominal ne marche pas
3. **FAIL sur edge_case** : robustesse
4. **FAIL sur erreur_input** : gestion d'erreurs
5. **WARN** : comportement suboptimal
6. **Performance** : lenteur excessive

### Types de corrections frequentes

| Probleme | Correction typique |
|----------|-------------------|
| Input non reconnu | Enrichir le parsing/normalisation |
| Mapping manquant | Ajouter les cas dans les dictionnaires/tables |
| Prompt LLM imprecis | Reformuler avec exemples et contraintes |
| API externe 0 resultats | Ajouter fallback, elargir les filtres |
| Code retour invalide | Sanitiser/valider les parametres avant l'appel |
| Timeout/lenteur | Paralleliser, cacher, limiter la pagination |

## Phase 6 — Re-validation

1. **Relancer le benchmark complet** apres toutes les corrections
2. **Comparer** le score avant/apres
3. Si des echecs persistent : revenir a la Phase 5
4. **Iterer** jusqu'a atteindre le meilleur score possible (objectif : 100% ou justifier les cas restants)

### Critere de fin

Le skill est termine quand :
- Le score est >= 95% (ou 100% si possible)
- Chaque echec restant est **explique et justifie** (limite externe, cas theorique, etc.)
- Le rapport comparatif avant/apres est presente a l'utilisateur

## Phase 7 — Synthese finale

Presenter a l'utilisateur :

1. **Tableau comparatif** avant/apres par categorie
2. **Liste des fichiers modifies** avec un resume de chaque changement
3. **Cas restants** non resolus avec justification
4. **Recommandations** pour la suite (tests a ajouter, monitoring, etc.)

## Regles transversales

- **Langue** : repondre dans la langue de l'utilisateur
- **Ne jamais modifier le benchmark** pour faire passer un test — corriger l'outil
- **Garder le script de benchmark** dans le projet pour les futures regressions
- **Utiliser les TODO** pour tracker la progression sur les corrections
- **Ne pas commiter** sauf si l'utilisateur le demande explicitement
- Si l'outil utilise des **APIs externes payantes**, limiter le nombre d'appels lors du benchmark (grouper, cacher, mock si pertinent)
- Privilegier les **corrections deterministes** (code, config, mappings) aux corrections non-deterministes (prompts LLM) quand c'est possible
