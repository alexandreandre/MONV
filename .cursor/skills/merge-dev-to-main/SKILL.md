---
name: merge-dev-to-main
description: >-
  Intègre une branche personnelle dev-* dans main sur GitHub : met main à jour
  en base, rejoue les commits propres à dev-* (rebase sur origin/main), résout
  les conflits en priorisant main par défaut, pousse dev-* puis met à jour
  origin/main (fast-forward si possible). À utiliser quand l’utilisateur veut
  fusionner dev-alex / dev-jose / dev-mathieu dans main, rattraper main en
  retard, ou attache explicitement ce skill.
---

# Merge dev-* → main

## Objectif

Quand **`main` sur GitHub a avancé** et qu’une branche **`dev-*`** a des **commits en avance** qui ne sont pas encore dans `main`, livrer **uniquement ces commits** dans `main` en :

1. **Rebasant** `dev-*` sur **`origin/main`** (historique linéaire : les commits de `main` restent la base).
2. En cas de conflit : **par défaut, privilégier `main`** pour le code déjà présent sur `main` ; **réintégrer** ce qui est spécifique à `dev-*` (nouvelles routes, nouveaux imports, nouveaux fichiers) sans écraser à l’aveugle une évolution récente de `main`.
3. **`git push --force-with-lease`** sur `origin/<dev-*>` après rebase.
4. **Mettre à jour `main`** : en général **`git merge --ff-only dev-*`** puis **`git push origin main`** (évite un merge commit inutile si l’historique le permet).

---

## Quand utiliser ce skill

- L’utilisateur veut **merger une branche `dev-*` dans `main`** (ou « mettre mes commits sur main »).
- La branche est **en retard** sur `main` / « il manque des commits de main ».
- L’utilisateur demande **`/merge-dev-to-main`**, **sync avec main avant merge**, ou attache ce fichier.

**Ne pas** utiliser ce skill pour un simple `push` de travail quotidien sur `dev-*` sans toucher à `main` → skill **push**.

---

## Vérifications à demander ou confirmer avec l’utilisateur (avant d’agir)

Exécuter le **diagnostic** (section suivante), puis si tout est cohérent, **demander une confirmation explicite** si une des lignes ci-dessous n’est pas claire à 100 %.

Checklist (à valider mentalement ou en posant des questions courtes) :

- [ ] **Quelle branche `dev-*`** doit être intégrée ? (ex. `dev-mathieu`, pas une autre par erreur.)
- [ ] **Dépôt / remote** : bien `origin` du projet attendu (pas un fork ou un miroir par erreur).
- [ ] **Objectif** : mise à jour de **`origin/main`** sur GitHub (pas seulement un rebase local sans push).
- [ ] S’il existe des **commits sur `main` absents de `dev-*`** : l’utilisateur accepte un **rebase** (réécrit l’historique de `dev-*` ; push avec **`--force-with-lease`**).
- [ ] Personne d’autre ne pousse des commits sur cette **`dev-*`** en parallèle sans coordination (le force-push peut les surprendre).

Si l’utilisateur ne sait pas : afficher le résultat de `git log --oneline <merge-base>..origin/dev-*` et `git log --oneline <merge-base>..origin/main` pour qu’il **voie** ce qui sera rejoué / ce qui vient de `main`.

---

## Diagnostic (à faire en premier)

```bash
git fetch origin
git branch --show-current
git merge-base origin/main origin/<dev-*>
```

Puis :

```bash
# Commits uniquement sur dev-* (ce qu’on veut ajouter à main à terme)
git log --oneline origin/main..origin/<dev-*>

# Commits sur main pas encore dans dev-* (à intégrer en base avant merge)
git log --oneline origin/<dev-*>..origin/main
```

Interprétation :

- **Deuxième liste vide** : `dev-*` contient déjà `main` → merger ou ouvrir une PR sans rebase.
- **Première liste vide** : **rien à livrer** depuis `dev-*` → arrêter et l’indiquer.
- **Les deux non vides** : workflow **rebase** ci-dessous.

---

## Garde-fous

1. **Ne pas** pousser sur `main` sans avoir **vérifié** branche courante après `checkout main` et sans **`git pull origin main`** à jour.
2. **Ne jamais** `git push --force` sur `main` (seulement fast-forward ou merge explicite selon politique d’équipe).
3. Après rebase : **`git push --force-with-lease origin <dev-*>`** (pas `--force` nu).
4. Si la politique d’équipe impose **Pull Request + CI** : faire le rebase + push `dev-*`, puis **PR vers `main`** au lieu de `push origin main` direct ; adapter les dernières étapes en conséquence.

---

## Workflow rebase (stratégie par défaut)

1. `git checkout <dev-*>`
2. `git pull origin <dev-*>` (optionnel si déjà aligné)
3. `git rebase origin/main`
4. À chaque conflit :
   - **Fichiers purement mécaniques** (imports, renommages, format) : fusionner en gardant **à la fois** la structure issue de `main` et les **symboles / routes / composants** ajoutés par `dev-*` (comme un merge manuel classique).
   - **Pendant un rebase**, pour un fichier où la version de **`main` doit gagner entièrement** :  
     `git checkout --ours -- <fichier>` puis `git add` (car **ours** = branche sur laquelle on rebase = **`main`**).
   - Pour garder entièrement le patch **dev-*** sur un fichier : **`--theirs`** (à n’utiliser que si c’est voulu).
5. `GIT_EDITOR=true git rebase --continue` (ou éditeur normal) jusqu’à la fin.
6. `git push --force-with-lease origin <dev-*>`

---

## Conflits ambigus — poser des questions à l’utilisateur

Si le conflit mélange **deux intentions produit** (ex. même zone de sidebar, même endpoint, même règle métier), **ne pas deviner**. S’arrêter, résumer en 2–4 lignes, et poser une question **binaire ou structurée**, par exemple :

- « Sur ce fichier, **`main` a refondu la navigation RH** et **`dev-*` ajoute une entrée Support**. On garde **la structure de `main`** et on **réinsère** l’entrée Support de `dev-*` — tu confirmes ? »
- « Les deux côtés modifient **la validation de X**. Faut-il appliquer **strictement le comportement de `main`** ou **celui de `dev-*`** ? »
- « Faut-il **conserver les deux** comportements (exposer deux chemins) ou **n’en garder qu’un** ? Lequel ? »

Après réponse : appliquer la résolution, `git add`, `git rebase --continue`.

---

## Intégration dans `main`

Après rebase + push `dev-*` :

```bash
git checkout main
git pull origin main
git merge --ff-only <dev-*>
git push origin main
```

- Si **`--ff-only` échoue** : `main` a bougé entre-temps → `git pull origin main`, **rebase à nouveau** `dev-*` sur `origin/main`, push `--force-with-lease` `dev-*`, puis retenter le fast-forward ; ou ouvrir une **PR** si c’est le flux imposé.

---

## Après coup

- Indiquer les **SHAs** ou les **titres de commits** effectivement sur `main`.
- Rappeler sur quelle branche l’utilisateur veut reprendre le travail (souvent `git checkout dev-*` ou une autre branche perso).

---

## Résumé

| Étape | Action |
|--------|--------|
| 1 | `fetch` + `merge-base` + logs asymétriques |
| 2 | Confirmer branche + intention (checklist) |
| 3 | `rebase origin/main` sur `dev-*` |
| 4 | Conflits : défaut **respecter `main`** + intégrer l’apport `dev-*` ; si ambigu → **question utilisateur** |
| 5 | `push --force-with-lease` `dev-*` |
| 6 | `main` à jour + `merge --ff-only` + `push origin main` (ou PR) |
