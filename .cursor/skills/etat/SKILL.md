---
name: etat
description: >-
  Résume pour les dev l’écart entre le dépôt local et la branche dev distante
  (origin), l’écart entre cette branche dev et origin/main, indique quand
  lancer /begin (skill begin) et ce qu’il se passe si on le fait. À utiliser
  lorsque l’utilisateur demande /etat, un état Git, un bilan de synchronisation,
  ou attache explicitement ce skill.
---

# État Git — `/etat`

## Objectif

Donner aux développeurs un **résumé lisible** de :

1. **Local vs GitHub (branche `dev-*`)** : ce qui diffère entre le dépôt **local** et **`origin/<même branche>`** (commits en avance / en retard, éventuelle divergence, working tree).
2. **`dev-*` sur GitHub vs `main`** : ce qui est **uniquement sur `origin/<dev-*>`**, ce qui est **uniquement sur `origin/main`**, et si la livraison vers `main` est « évidente » ou bloquée par du retard sur `main`.
3. **Faut-il lancer `/begin` (skill begin) ?** Dans quels cas oui/non, et **que se passe-t-il** si on le fait (sans remplacer la lecture du skill begin).
4. **Option `merge-dev-to-main`** : si le diagnostic montre qu’une intégration **`dev-*` → `main`** serait logique, **le skill peut le mentionner** — mais **jamais** lancer ni encourager fermement ce workflow **sans avoir demandé à Alex avant** (voir section dédiée).

---

## Quand utiliser ce skill

- L’utilisateur tape **`/etat`**, demande un **état Git**, un **bilan de synchro**, « où j’en suis par rapport à GitHub et à main », ou attache ce fichier.

---

## Branches concernées

Même convention que **begin** / **push** / **merge-dev-to-main** :

- `dev-mathieu`, `dev-jose`, `dev-alex` (étendre si le dépôt documente d’autres `dev-*`).

Si la branche courante **n’est pas** une `dev-*` documentée : **ne pas inventer** la branche distante ; indiquer la branche actuelle et dire qu’il faut **`git checkout dev-<prénom>`** pour un état « perso » cohérent, ou demander quelle `dev-*` analyser.

---

## Workflow (ordre recommandé)

### 1. Mettre les refs distantes à jour

```bash
git fetch origin
```

Sans `fetch`, les comparaisons avec GitHub peuvent être **fausses**.

### 2. Branche courante et working tree

```bash
git branch --show-current
git status -sb
```

À communiquer clairement :

- **Branche** : nom exact.
- **Working tree** : propre / modifs non commitées / fichiers non suivis — et si des opérations `merge` / `rebase` / `pull` seraient **risquées** sans `stash` ou commit (rappel court, pas de moraline).

### 3. Local ↔ `origin/<dev-*>` (même nom que la branche locale)

Soit `DEV` la branche courante (une des `dev-*` autorisées).

```bash
git rev-list --left-right --count origin/$DEV...HEAD
```

Interprétation du couple **`A	B`** (souvent affiché `A	B`) :

- **`A` (gauche)** : commits sur **`origin/$DEV`** absents du **HEAD local** → le dépôt distant a avancé : tu es **en retard** sur ta branche GitHub (il manque des commits distants localement).
- **`B` (droite)** : commits sur **HEAD** absents de **`origin/$DEV`** → travail **local non poussé** (en avance sur GitHub).

Si **A > 0 et B > 0** : **divergence** (rebase ou merge nécessaire pour réaligner ; ne pas deviner la stratégie sans contexte — signaler les deux compteurs).

**Aperçu utile (quelques lignes max)** :

```bash
git log --oneline -10 HEAD..origin/$DEV
git log --oneline -10 origin/$DEV..HEAD
```

- Première commande : ce que **tu n’as pas encore tiré** depuis GitHub.
- Seconde : ce que **tu n’as pas encore poussé**.

### 4. `origin/$DEV` ↔ `origin/main` (vue « équipe / prod de référence »)

```bash
git merge-base origin/main origin/$DEV
git rev-list --left-right --count origin/main...origin/$DEV
```

Puis listes courtes (même logique que **merge-dev-to-main**, diagnostic) :

```bash
git log --oneline -10 origin/main..origin/$DEV
git log --oneline -10 origin/$DEV..origin/main
```

Interprétation :

- **`origin/main..origin/$DEV` non vide** : il y a du travail **sur ta branche GitHub** qui **n’est pas encore sur `main`** (candidats à PR / merge vers `main` selon le flux d’équipe).
- **`origin/$DEV..origin/main` non vide** : **`main` a avancé** par rapport à ta branche **telle qu’elle est sur GitHub** — ta `dev-*` distante est **en retard sur `main`** (avant livraison, il faudra en général **rebase / merge depuis `main`**, voir skill **merge-dev-to-main**).

---

## Faut-il lancer **`/begin`** (skill **begin**) ?

### Cas où **oui** (souvent pertinent)

- Tu es sur une **`dev-*`** documentée **et** il existe des commits sur **`origin/main`** qui ne sont **pas** encore dans ton **HEAD** local :

```bash
git rev-list --left-right --count origin/main...HEAD
```

Si le nombre à **gauche** (commits dans `origin/main` pas dans `HEAD`) est **> 0**, tu es **en retard sur `main` en local** : c’est le cas typique où **begin** sert à **récupérer `main` dans ta branche** avant de coder.

### Cas où **non** ou « pas urgent »

- Tu n’es **pas** sur une `dev-*` : begin ne cible pas cette branche — **checkout** d’abord.
- Working tree **très sale** : begin **peut** continuer mais l’agent doit **avertir** (conflits pénibles) ; parfois mieux de **commit** ou **stash** avant — ce n’est pas une interdiction automatique, c’est un **signal rouge orange**.
- Tu es **déjà aligné** avec `origin/main` au niveau local (`left == 0` ci-dessus) : begin n’apporte **rien** de synchro `main` (tu peux quand même le relancer si tu veux refaire un `fetch`, mais ce n’est pas « nécessaire »).

### Que se passe-t-il **si** on lance **begin** (rappel pour les devs)

Résumé **fidèle** au skill **begin** (détail dans `.cursor/skills/begin/SKILL.md`) :

1. Vérification **branche `dev-*`**.
2. **`git status`** : alerte si modifications non commitées.
3. **Confirmation explicite Oui / Non** de l’utilisateur **avant** toute synchro dangereuse (message d’avertissement sur pertes / conflits possibles).
4. **`git fetch origin main`** puis, **sur la branche `dev-*` courante**, intégration de **`origin/main`** via **`git merge origin/main`** (défaut) ou **`git rebase origin/main`** (si convention d’équipe).
5. **Pas de `checkout main`** pour mettre à jour : on reste sur **`dev-*`** ; la branche locale **`main`** n’est pas l’objet du workflow.
6. Mini-bilan (`git log -1`, compteur `origin/main...HEAD`, rappels install si lockfiles ont bougé).

**Ne pas** exécuter begin « à la place de l’utilisateur » sans qu’il ait demandé **begin** ou **/begin** : **etat** = **diagnostic** ; **begin** = **action** avec confirmation.

---

## `merge-dev-to-main` — **demander à Alex d’abord**

Si le diagnostic montre par exemple :

- des commits sur **`origin/$DEV`** pas dans **`origin/main`**, **et**
- **`main` a aussi avancé** par rapport à **`origin/$DEV`** (les deux listes asymétriques non vides),

alors une **intégration vers `main`** peut être **pertinente** (skill **merge-dev-to-main**), **mais** :

- **Ne pas** lancer ce workflow ni dire « vas-y merge » sans validation **Alex**.
- Formulation type : « Le dépôt est dans un état où **merge-dev-to-main** pourrait être adapté ; **il faut en parler à Alex avant** de lancer ce skill ou toute fusion vers `main`. »
- Si l’utilisateur **est** Alex ou a déjà l’accord : renvoyer vers le skill **merge-dev-to-main** et ses garde-fous (rebase, `--force-with-lease` sur `dev-*`, pas de force sur `main`, PR/CI si politique d’équipe).

---

## Synthèse à fournir à l’utilisateur (structure de réponse)

En **français**, sections courtes :

| Section | Contenu |
|--------|---------|
| Branche | Nom + OK / pas une `dev-*` |
| Working tree | Propre ou résumé `git status -sb` |
| Local vs `origin/dev-*` | Compteur A B + 1 phrase (retard / avance / divergence) + extraits `git log` si utile |
| `origin/dev-*` vs `origin/main` | Ce qui manque à `main` depuis la dev ; ce que la dev n’a pas encore de `main` |
| `/begin` ? | Oui / Non / Optionnel + **pourquoi** (lié au compteur `origin/main...HEAD`) |
| Si `/begin` | Rappel en 3–5 puces (confirmation, fetch, merge/rebase sur `dev-*`, pas checkout `main`) |
| Livraison `main` | Si pertinent : état + **« demander à Alex avant merge-dev-to-main »** si le cas s’y prête |

---

## Anti-patterns

- Ne pas **skip** `git fetch` avant de comparer à **origin**.
- Ne pas confondre **« local vs origin/dev »** et **« dev GitHub vs main »** — ce sont **deux** questions distinctes.
- Ne pas pousser ou merger vers **`main`** depuis ce skill ; **etat** est **lecture + conseil**.
- Ne pas recommander **merge-dev-to-main** sans mention **explicite** de **validation par Alex** quand le contexte l’appelle.

---

## Exemple d’invocation

> `/etat` — je veux savoir si je suis aligné avec ma branche GitHub et avec main, et si je dois faire begin ce matin.

L’agent exécute le workflow, affiche les compteurs et une synthèse actionnable, sans lancer begin ni merge sans demande explicite.
