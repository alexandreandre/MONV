---
name: enhance-fonctionnality
description: >-
  Ameliore une fonctionnalite existante en generant des idees d'amelioration
  de maniere autonome, puis en les implementant. Couvre UX, robustesse,
  performance, completude, accessibilite et coherence. A utiliser lorsque
  l'utilisateur tape /enhance-fonctionnality, demande d'ameliorer une
  fonctionnalite, de rendre une feature plus complete, plus robuste, ou
  plus professionnelle, ou attache explicitement ce skill.
---

# /enhance-fonctionnality — Amelioration autonome de fonctionnalite

Recoit le nom ou la description d'une fonctionnalite, l'explore en profondeur,
genere des idees d'amelioration, puis les implemente apres validation.

## Etape 0 — Identifier la cible

L'utilisateur doit preciser **quelle fonctionnalite** ameliorer.
Si ce n'est pas clair, demander :

> Quelle fonctionnalite veux-tu que j'ameliore ?

Accepter aussi bien un nom precis (`le systeme d'export CSV`) qu'une
description vague (`la page de resultats`). Dans le second cas, explorer
le code pour delimiter le perimetre.

## Etape 1 — Exploration en profondeur

Avant de proposer quoi que ce soit, **comprendre** la fonctionnalite :

1. **Lire tout le code** implique (backend, frontend, schemas, tests)
2. **Identifier les entrees/sorties** : qu'est-ce qui rentre, qu'est-ce qui sort
3. **Cartographier les cas d'usage** : qui utilise cette feature, comment, pourquoi
4. **Reperer les limitations** actuelles, les TODO, les commentaires, les fallbacks
5. **Verifier les tests existants** : que couvrent-ils, que manque-t-il
6. **Tester mentalement** des scenarios limites

## Etape 2 — Generation d'idees (autonome)

Generer des idees d'amelioration en balayant **systematiquement** ces 10 axes :

| # | Axe | Question a se poser |
|---|-----|---------------------|
| 1 | **Completude** | Manque-t-il des cas ? Des options ? Des formats ? |
| 2 | **Robustesse** | Que se passe-t-il si l'input est vide, enorme, malformé ? |
| 3 | **UX / Ergonomie** | L'utilisateur comprend-il ce qui se passe ? Les messages sont-ils clairs ? |
| 4 | **Performance** | Peut-on aller plus vite ? Paralleliser ? Cacher ? |
| 5 | **Gestion d'erreurs** | Les erreurs sont-elles attrapees, loguees, et communiquees ? |
| 6 | **Coherence** | Le comportement est-il coherent avec le reste de l'application ? |
| 7 | **Accessibilite** | Fonctionne-t-il sur mobile, en mode sombre, avec un lecteur d'ecran ? |
| 8 | **Securite** | Y a-t-il des injections, des fuites de donnees, des acces non controles ? |
| 9 | **Maintenabilite** | Le code est-il lisible, decoupe, testable, documente ? |
| 10 | **Valeur ajoutee** | Quelle feature adjacente simple apporterait beaucoup a l'utilisateur ? |

### Regles de generation

- Generer **au moins 8 idees**, idealement 12-20
- Chaque idee doit etre **concrete et actionnable** (pas "ameliorer le code")
- Classer chaque idee par **impact** (haut/moyen/bas) et **effort** (petit/moyen/gros)
- Privilegier les idees a **haut impact + petit effort** (quick wins)

## Etape 3 — Presentation a l'utilisateur

Presenter les idees dans un tableau structure :

```
## Idees d'amelioration pour [nom de la feature]

| # | Idee | Axe | Impact | Effort |
|---|------|-----|--------|--------|
| 1 | ... | Robustesse | Haut | Petit |
| 2 | ... | UX | Haut | Moyen |
| ... |

### Quick wins recommandes (a faire en premier)
1. ...
2. ...

### Ameliorations majeures (plus d'effort, gros impact)
1. ...

Veux-tu que j'implemente tout, seulement les quick wins, ou une selection ?
```

Attendre la **validation explicite** de l'utilisateur avant d'implementer.
Si l'utilisateur dit "vas-y" / "tout" / "fais" sans preciser, implementer
**tous les quick wins + les ameliorations a haut impact**.

## Etape 4 — Implementation

Pour chaque amelioration validee :

1. **Creer un TODO** avec toutes les idees a implementer
2. **Implementer une par une**, en mettant a jour le TODO au fur et a mesure
3. Apres chaque modification, **verifier les lints**
4. **Ne pas casser l'existant** : si une amelioration risque de casser autre chose,
   tester le cas de base avant et apres
5. **Grouper les modifications** par fichier quand c'est possible

### Ordre d'implementation

1. Quick wins (petit effort, haut impact)
2. Corrections de robustesse / erreurs
3. Ameliorations UX
4. Performance
5. Valeur ajoutee / features adjacentes

## Etape 5 — Validation

Apres toutes les implementations :

1. **Verifier les lints** sur tous les fichiers modifies
2. **Tester manuellement** si un serveur tourne (ou demander a l'utilisateur)
3. Si des tests existent, les **lancer**
4. Presenter un **resume** :

```
## Resume des ameliorations

### Implemente
- [x] Idee 1 — description courte du changement
- [x] Idee 2 — ...

### Fichiers modifies
- `path/to/file.py` — description
- ...

### Non implemente (et pourquoi)
- Idee X — raison (trop risque, hors scope, besoin de decision produit)
```

## Regles

- **Langue** : repondre dans la langue de l'utilisateur
- **Ne pas modifier** ce qui n'est pas lie a la fonctionnalite cible
- **Aucun refactor drive-by** : ne pas "ameliorer" du code hors perimetre
- **Pas de commit** sauf demande explicite
- Si une idee necessite une **decision produit** (ex: changer le comportement
  visible), la signaler et demander plutot que d'implementer d'office
- Privilegier les **corrections deterministes** (code, config) aux modifications
  de prompts/LLM quand c'est possible
