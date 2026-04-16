# /commit — Tout stager, commits détaillés, push sur `main`

Tu suis le même flux que le skill **commit** du dépôt (`.cursor/skills/commit/SKILL.md`) : **jusqu’au push sur `origin/main`**, pas seulement préparer le commit.

## Objectif

Sur la branche **`main`** : enchaîner **jusqu’au bout** — **`git add -A`**, un ou plusieurs **commits** au messages détaillés, puis **`git push origin main`** (ou `git push -u origin main` si besoin de définir l’upstream). Le flux se termine par un **push réussi** ou une **erreur expliquée**.

**Ne pas** appliquer ici les règles « uniquement dev-* » du skill `push` : **`/commit`** = travail **direct sur `main`** quand l’utilisateur l’utilise pour ça.

## Exécution (obligatoire)

- **Exécuter réellement** les commandes Git dans l’ordre, pas seulement les lister.
- **Aller jusqu’au push** sur `origin/main` : après les commits, lancer `git push origin main` (ou `-u` si nécessaire).
- **Ne pas** demander une confirmation Oui/Non avant le push par défaut. Arrêt avant push seulement si : mauvaise branche, secrets, merge/rebase non terminé, ou refus remote (non fast-forward) — expliquer sans `git push --force` sur `main` sauf demande écrite explicite.

## Garde-fous

1. **Branche** : `git branch --show-current` doit être **`main`** (ou **`master`** si pas de `main`). Sinon → arrêter, indiquer **`/push`** (branche `dev-*`) ou **`merge-dev-to-main`**.
2. **Secrets** : avant `git add -A`, revoir `git status` / diff ; ne pas committer `.env` avec clés, certificats, etc. ; exclure du staging si besoin.
3. **Pas** de `git push --force` sur `main` sans demande explicite écrite.
4. Push refusé (non fast-forward) : ne pas forcer ; expliquer (`git pull --rebase origin main` après accord, etc.).

## Workflow (ordre)

1. `git rev-parse --show-toplevel` si besoin.
2. Vérifier la branche → garde-fous.
3. `git status -sb` et `git diff --stat`. Si rien à committer : `git log origin/main..HEAD` ; si commits locaux, passer au push après re-vérification de la branche.
4. `git add -A` à la racine, puis `git status`.
5. Commits au format conventionnel (voir ci-dessous) ; plusieurs intentions distinctes → plusieurs commits (`git reset` puis `git add` par lot si utile).
6. **`git push origin main`** (ou `git push -u origin main` une fois).
7. Synthèse en français : branche, thèmes, `git log -3 --oneline`, push OK ou erreur.

### Format des messages

```text
<type>(<scope>): <résumé à l’impératif, ≤ ~72 caractères>

- Détail vérifiable
```

Types : `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `style`, etc. Le corps reflète le **diff réel**.

## Anti-patterns

- Messages vagues sur un gros diff.
- `git push --force` sur `main` sans accord explicite.
- S’arrêter après le commit sans avoir tenté le push alors que `main` est OK et aucun garde-fou ne bloque.
