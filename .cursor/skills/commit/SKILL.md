---
name: commit
description: >-
  Staging complet (git add -A), commits au format conventionnel détaillé,
  puis push vers origin sur la branche main. À utiliser lorsque l’utilisateur
  demande /commit, un commit tout-en-un poussé sur main, ou attache explicitement
  ce skill (à distinguer de /push sur branche dev-*).
---

# Commit — tout stager, commits détaillés, push sur `main`

## Objectif

Sur la branche **`main`** : **`git add -A`**, créer un ou plusieurs **commits au messages détaillés**, puis **`git push origin main`** (ou `git push -u origin main` si besoin de définir l’upstream).

**Différence avec le skill `push`** : `push` cible **uniquement** une branche personnelle `dev-*` et **interdit** de pousser sur `main`. Ce skill **`commit`** est pour le flux **direct sur `main`** quand l’utilisateur le demande explicitement.

## Quand utiliser ce skill

- L’utilisateur tape **`/commit`**, demande d’**ajouter tout**, de **committer en détail** et de **pousser sur `main`**, ou attache ce fichier.

## Garde-fous (obligatoires)

1. **Branche courante** : `git branch --show-current`
   - Doit être **`main`** (ou **`master`** si c’est la branche par défaut du dépôt et qu’il n’y a pas de `main`).  
   - Si la branche est une **`dev-*`** ou autre → **ne pas** appliquer ce workflow tel quel. Indiquer d’utiliser **`/push`** pour sauvegarder sur la branche perso, ou **`merge-dev-to-main`** pour intégrer dans `main` proprement.
2. **Secrets et fichiers locaux** : avant `git add -A`, parcourir `git status` / le diff. **Ne pas** committer de secrets (`.env` avec clés, certificats, etc.) : respecter `.gitignore` ; si un fichier sensible apparaît, **alerter** et exclure du staging.
3. **Pas de `git push --force`** sur `main` sans **demande explicite** écrite de l’utilisateur.
4. Si le push est refusé (non fast-forward) : **ne pas** forcer ; expliquer (`git pull --rebase origin main` après accord, etc.).

## Workflow (ordre)

### 1. Contexte

- Racine : `git rev-parse --show-toplevel`.

### 2. Vérifier la branche

```bash
git branch --show-current
```

Appliquer les garde-fous. Si arrêt, résumer en **français**.

### 3. État des changements

```bash
git status -sb
git diff --stat
```

- Rien à committer : vérifier commits locaux non poussés (`git log origin/main..HEAD` ou équivalent) ; si oui, `git push origin main` après re-vérification de la branche.

### 4. Staging complet

À la racine du dépôt :

```bash
git add -A
git status
```

### 5. Commits détaillés

**Principe** : cohérent avec l’historique récent (`git log -5 --oneline`) — français ou anglais selon le dépôt.

**Format** (résumé ≤ ~72 caractères + corps si utile) :

```text
<type>(<scope>): <résumé à l’impératif>

- Détail 1 (zone ou fichier)
- Détail 2
```

Types : `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `style`, etc.  
**Découpage** : plusieurs sujets sans lien → plusieurs commits (`git add -p` ou chemins ciblés entre commits). Une seule intention → un commit bien rédigé.

Le corps doit refléter **le diff réel**, pas un texte générique.

### 6. Push vers `main`

```bash
git push origin main
```

Si l’upstream n’existe pas encore sur cette machine : `git push -u origin main` une fois.

### 7. Synthèse (français)

- Branche `main` confirmée.
- Thèmes / fichiers principaux.
- Derniers commits : `git log -3 --oneline`.
- Push vers `origin/main` confirmé ou erreur expliquée.

## Anti-patterns

- Utiliser ce skill depuis une branche **`dev-*`** sans changer d’intention (risque de confusion avec `/push`).
- Messages vagues (« update », « fix ») sur un gros diff.
- `git push --force` sur `main` sans accord explicite.

## Exemple d’invocation

> `/commit` — tout est sur `main`, j’ai fini la correction, add tout, commit détaillé et push.

L’agent vérifie qu’on est bien sur `main`, stager tout (hors alertes secrets), committe, pousse vers `origin/main`, synthèse courte.
