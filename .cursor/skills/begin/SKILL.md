---
name: begin
description: >-
  Démarre une session Git sur la branche personnelle du dépôt (dev-mathieu,
  dev-jose, dev-alex), vérifie la branche courante, demande une confirmation
  explicite (Oui/Non) avant toute synchro avec main, synchronise cette branche
  avec origin/main sans basculer sur main, et affiche un mini-bilan utile.
  À utiliser lorsque l’utilisateur demande de commencer une session de travail
  sur sa branche dev-* ou attache explicitement ce skill.
---

# Begin — session de travail sur branche dev-*

## Objectif

Aider les développeurs à **démarrer une session** : être sur **la bonne branche**, obtenir une **confirmation explicite (Oui/Non)** avant toute synchro avec `main`, puis **récupérer les derniers changements de `main`** dans **leur** branche, **sans jamais checkout `main`** ni modifier l’état de la branche locale `main` (on ne fait que `fetch` + intégration sur la branche courante).

## Quand utiliser ce skill

- L’utilisateur demande explicitement de **préparer / démarrer une session** (ou équivalent) sur `dev-mathieu`, `dev-jose` ou `dev-alex`, ou attache ce fichier.

## Branches autorisées

Noms **exacts** attendus (adapter si le dépôt ajoute d’autres dev-* en concertation) :

- `dev-mathieu`
- `dev-jose`
- `dev-alex`

Si le projet étend la liste, l’agent peut appliquer la **même procédure** pour toute branche `dev-*` documentée dans le dépôt (ex. `guidebranche.md`).

---

## Workflow (à exécuter dans l’ordre)

### 1. Contexte dépôt

- Vérifier qu’on est à la **racine du dépôt Git** (ou un sous-dossier du même repo) via `git rev-parse --show-toplevel` si besoin.

### 2. Vérifier la branche courante

Exécuter :

```bash
git branch --show-current
```

- Si la branche **n’est pas** une des branches autorisées ci-dessus :
  - **Ne pas** merger/rebaser tant que l’utilisateur n’est pas sur la bonne branche.
  - Indiquer clairement la branche actuelle et la commande à utiliser, par ex. :  
    `git checkout dev-alex`  
  - S’arrêter ici sauf si l’utilisateur demande explicitement une autre branche documentée.

### 3. État du working tree (obligatoire avant toute intégration)

Exécuter :

```bash
git status -sb
```

- S’il y a des modifications non commitées :
  - **Avertir** que `merge` / `rebase` peut créer des conflits ou un état pénible.
  - Proposer **`git stash push -u -m "begin session"`** avant l’étape 5, puis **`git stash pop`** après une intégration réussie (seulement si l’utilisateur accepte ou le contexte le permet sans perte de données).

### 4. Confirmation utilisateur (obligatoire) — **avant** `fetch` / `merge` / `rebase`

**Ne pas** exécuter les commandes de l’étape 5 tant que cette étape n’est pas résolue.

- Demander à l’utilisateur une validation **binaire** : **Oui** ou **Non**.
  - **Préférence** : utiliser une **question structurée avec boutons** (deux choix explicites « Oui » / « Non ») lorsque l’interface le permet.
  - **Sinon** : poser la question en texte clair et **attendre** une réponse explicite « Oui » ou « Non » (ne pas interpréter une absence de réponse comme un accord).

**Texte minimum à communiquer** (adapter légèrement si besoin, sans diluer l’intention) :

> En poursuivant la synchronisation avec `main`, vos **changements actuels** (fichiers modifiés non commités, et travail présent **uniquement** sur votre branche **qui n’est pas encore mergé sur `main`**) peuvent être **perdus, écrasés ou rendus difficiles à récupérer** selon la suite des opérations (conflits, réécriture d’historique, abandon d’une résolution, etc.).  
> **Êtes-vous sûr·e ?**

- Si la réponse est **Non** (ou équivalent refus) : **arrêter** le workflow begin ici ; indiquer ce qui **n’a pas** été fait (`fetch` / `merge` / `rebase` non lancés) et rappeler comment relancer plus tard.
- Si la réponse est **Oui** : enchaîner avec l’étape 5.

### 5. Mettre à jour **sans toucher à `main`**

Principe : **`fetch`** met à jour les **refs distantes** ; la branche locale `main` n’est **pas** checkoutée ni modifiée par défaut. Cette étape n’a lieu **qu’après** validation de l’étape 4 (confirmation Oui de l’utilisateur).

```bash
git fetch origin main
```

Puis, **toujours sur la branche dev-*** courante**, intégrer `origin/main` :

- **Par défaut (simple et sûr pour branches partagées)** :

```bash
git merge origin/main
```

- **Option rebase** (historique linéaire ; à éviter si la branche est déjà poussée et partagée sans convention rebase) :

```bash
git rebase origin/main
```

En cas de conflits : les signaler, lister les fichiers concernés, guider vers résolution (`git status`, édition, `git add`, puis `git merge --continue` ou `git rebase --continue`). Ne pas forcer (`--force`) sans demande explicite.

### 6. Mini-bilan « gadget » (à afficher dans la réponse)

Après intégration réussie, exécuter au besoin et résumer en **quelques lignes** :

```bash
git log -1 --oneline
git rev-list --left-right --count origin/main...HEAD
```

Interprétation rapide du compteur `left	right` : gauche = commits sur `origin/main` pas dans HEAD (normalement faible après merge/rebase) ; droite = commits locaux pas encore sur `main`.

**Bonus utiles** (si pertinent pour le repo) :

- Si `package.json` / `package-lock.json` / `pnpm-lock.yaml` / `requirements.txt` ont changé par rapport à avant le merge : rappeler **`npm install`** ou équivalent.
- Rappeler le lancement dev du projet si documenté (ex. selon `guidebranche.md` : `npm run dev`).

### 7. Synthèse pour l’utilisateur (en français)

Répondre avec :

- Branche vérifiée (OK ou erreur + commande `checkout`).
- Si l’étape 3 a bloqué (modifs locales sans accord) : résumer `git status -sb` et rappeler qu’aucun `fetch`/merge n’a été lancé tant que l’utilisateur n’a pas choisi.
- Actions Git effectuées (`fetch`, `merge` ou `rebase`).
- Dernier commit (`git log -1 --oneline`).
- Éventuellement divergence `origin/main...HEAD` en une phrase.
- Prochaine étape courte (ex. lancer le serveur de dev, ouvrir une tâche).

---

## Anti-patterns à éviter

- Ne pas faire `git checkout main` ni `git pull` **sur** `main` dans ce workflow (hors périmètre « session sur dev-* »).
- Ne pas rebaser une branche **déjà poussée et utilisée par d’autres** sans accord / convention d’équipe.
- Ne pas ignorer un working tree **sale** : au minimum avertir avant merge/rebase.
- Ne pas enchaîner `fetch` / `merge` / `rebase` **sans** la confirmation explicite Oui de l’étape 4.

---

## Exemple d’invocation

> Je démarre ma journée — mets-moi à jour proprement sur ma branche dev (workflow begin du dépôt).

L’agent exécute les commandes, respecte les arrêts si mauvaise branche ou si des modifications locales sont en cours **sans accord explicite**, et renvoie le mini-bilan structuré une fois l’intégration terminée.
