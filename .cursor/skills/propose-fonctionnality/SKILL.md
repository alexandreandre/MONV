---
name: propose-fonctionnality
description: >-
  Analyse le projet actuel en profondeur (architecture, stack, fonctionnalites
  existantes, donnees disponibles, cible utilisateur) et propose de nouvelles
  fonctionnalites a implementer — pas des ameliorations de l'existant, mais des
  features enticement nouvelles. Priorise par valeur produit, effort et
  coherence avec la vision du projet. A utiliser lorsque l'utilisateur tape
  /propose-fonctionnality, demande des idees de features, veut savoir quoi
  construire ensuite, cherche de l'inspiration produit, ou attache explicitement
  ce skill.
---

# /propose-fonctionnality — Proposition de nouvelles fonctionnalites

Analyse le projet en profondeur, identifie les opportunites, et propose des
**fonctionnalites enticement nouvelles** a implementer — distinctes de
l'existant. Ne couvre pas l'amelioration de features deja presentes (utiliser
`/propose-enhancement` ou `/enhance-fonctionnality` pour ca).

> Ce skill **propose** mais **n'implemente pas**. L'utilisateur decide ensuite
> quoi implementer.

## Etape 0 — Cadrage

Si l'utilisateur precise un **axe** (ex: "cote admin", "monetisation",
"integrations"), se concentrer dessus. Sinon, proposer sur l'ensemble du
projet.

Si le perimetre est flou, demander :

> Tu veux des idees sur un axe precis (admin, UX, data, monetisation,
> integrations…) ou un brainstorm global ?

## Etape 1 — Comprehension du projet

### 1a. Cartographie

1. Lire le README, la config, les fichiers d'entree
2. Identifier la stack, les APIs externes, la base de donnees
3. Lister les fonctionnalites **deja implementees** (routes, composants, services)
4. Identifier le **public cible** et le **probleme resolu**
5. Reperer les **donnees disponibles** mais non exploitees

### 1b. Inventaire de l'existant

Produire un inventaire compact :

```
## Fonctionnalites existantes

| # | Feature | Couche | Statut |
|---|---------|--------|--------|
| 1 | Auth JWT | full-stack | stable |
| 2 | Chat prospection | full-stack | stable |
| ... |
```

Cet inventaire sert de base pour s'assurer que les propositions sont bien
**nouvelles** et pas des doublons deguises.

## Etape 2 — Generation d'idees

Explorer **systematiquement** ces 10 axes d'opportunite :

| # | Axe | Question directrice |
|---|-----|---------------------|
| 1 | **Valeur utilisateur** | Quelle nouvelle action l'utilisateur voudrait faire mais ne peut pas encore ? |
| 2 | **Donnees inexploitees** | Quelles donnees sont collectees/accessibles mais pas encore valorisees ? |
| 3 | **Automatisation** | Quel flux manuel pourrait etre automatise ou programme ? |
| 4 | **Collaboration** | Comment plusieurs utilisateurs pourraient-ils travailler ensemble ? |
| 5 | **Intelligence** | Ou un modele de langage ou de l'analyse de donnees apporterait-il de la valeur supplementaire ? |
| 6 | **Integrations** | Quels outils/services tiers rendraient le produit plus complet ? |
| 7 | **Monetisation** | Quel mecanisme de revenus ou de conversion manque ? |
| 8 | **Admin / Ops** | De quels outils l'equipe a-t-elle besoin pour operer le produit ? |
| 9 | **Retention** | Qu'est-ce qui ferait revenir l'utilisateur regulierement ? |
| 10 | **Differenciation** | Quelle feature unique distinguerait le produit de la concurrence ? |

### Regles de generation

- Generer **au moins 10 idees**, idealement 15-25
- Chaque idee doit etre une **feature nouvelle** (pas une amelioration d'existant)
- Etre **concret** : decrire ce que l'utilisateur peut faire, pas un concept abstrait
- Evaluer chaque idee sur : **valeur produit** (haute/moyenne/basse), **effort** (XS/S/M/L/XL), **coherence** avec le projet (haute/moyenne/basse)
- Privilegier les idees a **haute valeur + haute coherence + effort raisonnable**

## Etape 3 — Structuration des propositions

### Format d'une proposition

```
### [F-XX] Titre court et evocateur

- **Axe** : Valeur utilisateur / Automatisation / Intelligence / ...
- **Valeur produit** : Haute / Moyenne / Basse
- **Effort** : XS (< 1h) / S (1-4h) / M (4h-1j) / L (1-3j) / XL (> 3j)
- **Coherence** : Haute / Moyenne / Basse
- **Description** : Ce que l'utilisateur peut faire (2-3 phrases)
- **Pourquoi maintenant** : Pourquoi cette feature a du sens a ce stade du projet
- **Donnees/APIs** : Sources de donnees ou APIs necessaires
- **Grandes lignes techniques** : Composants/services/tables a creer (pas de code, juste l'architecture)
- **Dependances** : Prerequis existants ou autres propositions prealables (F-XX)
```

## Etape 4 — Synthese et priorisation

### 4a. Vue d'ensemble

```
## Propositions de nouvelles fonctionnalites

| # | Feature | Axe | Valeur | Effort | Coherence |
|---|---------|-----|--------|--------|-----------|
| F-01 | ... | Intelligence | Haute | M | Haute |
| F-02 | ... | Monetisation | Haute | L | Haute |
| ... |
```

### 4b. Top picks (recommandations)

Mettre en avant les **3-5 meilleures idees** en expliquant pourquoi :

```
## Top picks

### 1. [F-XX] Titre
Pourquoi : [justification produit en 1-2 phrases]

### 2. [F-XX] Titre
Pourquoi : ...
```

### 4c. Quick wins

Features a **haute valeur + petit effort** implementables rapidement :

```
## Quick wins
| # | Feature | Effort | Valeur |
|---|---------|--------|--------|
| F-XX | ... | XS | Haute |
| F-XX | ... | S | Haute |
```

### 4d. Vision long terme

Regrouper les propositions en phases logiques :

```
## Roadmap suggeree

Phase 1 (quick wins)     : F-XX, F-XX
Phase 2 (valeur coeur)   : F-XX, F-XX
Phase 3 (differenciation): F-XX, F-XX
Phase 4 (scalabilite)    : F-XX, F-XX
```

## Etape 5 — Livraison

Presenter le document complet, puis proposer :

> Veux-tu que j'implemente une de ces fonctionnalites ? Tu peux me donner :
> - Un numero (ex: F-03)
> - Un groupe (ex: "les quick wins")
> - Une phase (ex: "phase 1")

## Regles

- **Langue** : repondre dans la langue de l'utilisateur
- **Pas d'implementation** sauf demande explicite — ce skill produit un document
- **Honnetete** : ne pas proposer de features gadgets ; chaque proposition doit avoir une vraie justification produit
- **Pas de doublons** : verifier que chaque proposition n'existe pas deja dans le projet (meme partiellement)
- **Concret > abstrait** : "l'utilisateur peut programmer un export hebdomadaire par email" > "ajouter des automatisations"
- **Pas de commit** sauf demande explicite
- **Utiliser des subagents** (Task tool) pour explorer le code en parallele si le projet est gros
- Si l'utilisateur veut implementer une proposition, guider vers une demande directe ou `/enhance-fonctionnality` selon la complexite
