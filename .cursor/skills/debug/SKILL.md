---
name: debug
description: >-
  Diagnostique une erreur à partir des journaux du terminal Cursor, des sorties
  de serveurs de développement, de la console ou du réseau du navigateur, ou
  d’une description en langage naturel, puis corrige le code ou la configuration
  jusqu’à ce que la vérification (build, tests, ou scénario minimal) réussisse.
  À utiliser lorsque l’utilisateur tape /debug, signale une erreur, un écran blanc,
  un 500, une stack trace, ou un échec après npm/pytest ou équivalent.
---

# Debug — corriger une erreur de bout en bout

## Objectif

À partir d’**indices concrets** (sortie terminal, console navigateur, onglet réseau, message d’erreur collé) ou d’une **description précise**, l’agent doit :

1. **Identifier la cause** (fichier, ligne, configuration, dépendance, donnée).
2. **Appliquer une correction minimale** dans le dépôt (pas de refactor gratuit).
3. **Vérifier** que la correction tient (commande adaptée au projet : tests, lint, build, redémarrage du service concerné).
4. **Itérer** tant que l’échec est reproductible et corrigeable dans le périmètre du code.

Ne pas se contenter d’expliquer l’erreur sans changement ni sans tentative de validation.

## Quand utiliser ce skill

- Commande ou intention **`/debug`**.
- Erreur visible dans le **terminal** (Cursor, CI locale, script).
- Erreur dans la **console** ou le **réseau** du navigateur.
- **Échec** après `npm`, `pnpm`, `pytest`, migration, démarrage backend/frontend, etc.
- **Description orale** de l’erreur **si elle contient** le symptôme, l’action menant au bug, et l’environnement (URL, commande, OS si pertinent).

## Entrées attendues (ordre de préférence)

1. **Bloc de log / stack trace** (copié depuis le terminal ou la console).
2. **Capture textuelle** des requêtes réseau en échec (URL, statut, extrait du corps).
3. **Description structurée** : ce que l’utilisateur faisait → résultat observé → ce qu’il attendait.

Si l’information est insuffisante pour reproduire ou cibler un fichier, **poser une seule salve de questions ciblées** (données manquantes minimales), puis continuer avec ce qui est disponible (recherche dans le code, exécution de la commande qui échoue).

## Workflow

### 1. Ancrer le contexte

- Ouvrir ou demander le **chemin du dépôt** et le **composant** concerné (frontend, backend, racine).
- Repérer les **fichiers de terminaux Cursor** (`terminals/*.txt`) si l’erreur y figure et qu’ils sont accessibles.
- Noter la **commande exacte** qui a échoué et le **code de sortie** si présents.

### 2. Cartographier la panne

- Relier le message d’erreur à une **zone du code** (recherche sémantique ou grep sur un fragment stable du message).
- Vérifier les causes fréquentes : variable d’environnement manquante, mauvais port, CORS, schéma BDD, import cassé, typage, dépendance non installée, cache.

### 3. Corriger

- Proposer le **plus petit changement** cohérent avec le style du projet.
- Ne pas modifier des fichiers sans lien avec l’erreur.

### 4. Vérifier (obligatoire si possible)

- Relancer la **même commande** ou le **même scénario** qui échouait.
- Si le projet expose des scripts standards (`pytest`, `npm test`, `npm run build`, etc.), utiliser ceux qui couvrent la zone touchée.
- Si la correction est côté serveur, s’assurer que le **redémarrage** ou le **hot reload** a bien pris en compte le changement.

### 5. Synthèse pour l’utilisateur

En français, bref compte rendu :

- **Cause**.
- **Fichiers modifiés**.
- **Commande(s) de vérification** exécutées et résultat.
- **Limites** éventuelles (ex. bug externe, secret manquant non fourni).

## Cas où une correction complète n’est pas possible dans le dépôt

Si le blocage vient d’un **service tiers**, de **secrets absents**, ou d’un **environnement inaccessible** :

- Expliquer clairement pourquoi.
- Fournir tout de même les **modifications locales possibles** (meilleure erreur, doc, garde-fou) et les **étapes** pour que l’utilisateur débloque l’environnement.

## Anti-patterns

- Arrêter après une hypothèse sans **patch** ni **relance** de commande.
- Refactor large « en passant ».
- Demander à l’utilisateur d’exécuter à sa place ce que l’agent peut lancer dans l’environnement de session.

## Rappel conformité dépôt

Respecter les règles utilisateur et projet : changements ciblés, messages et commentaires utiles seulement si nécessaires, pas de fichiers markdown non demandés en dehors de ce skill.
