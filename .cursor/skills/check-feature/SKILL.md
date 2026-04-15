---
name: check-feature
description: Vérifie qu’une fonctionnalité demandée a bien été implémentée, teste son fonctionnement, et complète ou corrige le code si nécessaire. À utiliser lorsque l’utilisateur tape /check-feature avec le prompt d’origine (ou une description équivalente) de la fonctionnalité ; couvre front, back, tests, CI et synthèse en français.
---

# Check Feature (`/check-feature`)

## Objectif

**Vérifier** qu’une fonctionnalité décrite dans un **prompt d’origine** (ou équivalent) est **implémentée, branchée et utilisable**, puis **compléter ou corriger** le code et les tests si besoin.

Invocation typique : `/check-feature` suivi du texte qui définissait la fonctionnalité (spec initiale, ticket, copie de prompt).

## Quand utiliser ce skill

- L’utilisateur demande explicitement **`/check-feature`** ou une **revue de complétude** d’une fonctionnalité multi-fichiers (souvent front + back).
- Il fournit au minimum une **description exploitable** : prompt d’origine, liste d’acceptance, ou lien vers une spec dans le dépôt.

**Ne pas** l’utiliser pour une question ponctuelle, un renommage isolé ou un débogage ciblé (préférer le skill **debug** ou une demande directe).

### Si le prompt d’origine est absent ou trop flou

1. **D’abord** : utiliser le contexte du fil (fichiers ouverts, diff récent, branche) pour déduire l’intention et une checklist minimale.
2. **Sinon** : poser **une seule** question courte, listant les points bloquants (ex. rôles concernés, parcours utilisateur, endpoints attendus).
3. Ne pas bloquer indéfiniment : traiter ce qui est vérifiable objectivement (routes, tests, erreurs 4xx/5xx) et marquer le reste **MANQUANT / à clarifier**.

---

## Workflow global

Lorsque ce skill est actif, suivre cet ordre (il évite les fausses « complétudes » où du code existe mais n’est pas branché).

### 1. Comprendre et cadrer

- Lire le **prompt d’origine** ou l’équivalent.
- En extraire :
  - **Objectifs métier** (ce que l’utilisateur final peut faire) ;
  - **Comportements attendus** (écrans, actions, états, messages) ;
  - **Contraintes** (auth, rôles, validation, perfs, accessibilité, i18n produit en **français** pour l’UI).
- Produire une **checklist vérifiable** (formulations testables : « un utilisateur X peut… », « en cas d’erreur Y… »).

### 2. Cartographier le code

Repérer dans le dépôt :

| Zone | Où chercher (indicatif EYWAI) |
|------|-------------------------------|
| Frontend | `frontend/src/` — pages, routes, composants, hooks, client API |
| Backend | `backend/app/` — modules métier, routes FastAPI, services |
| Persistance | schémas / migrations selon les conventions du repo ; **ne pas improviser** de migration SQL hors process (voir `AGENTS.md` / règles backend) |
| Tests | `backend/tests/` (unit / integration / e2e / migration) ; Playwright sous `e2e/` si pertinent |

Outils : recherche sémantique, `Grep`, `Glob`, `Read` sur noms de routes, handlers, clés i18n, strings métier.

### 3. Vérifier la couverture fonctionnelle (code + câblage)

Pour chaque point de la checklist :

- Le code **existe** ;
- Il est **connecté** (route enregistrée, menu, navigation, export, injection DI, feature flag si utilisé dans le projet) ;
- Les **cas d’erreur** mentionnés dans le prompt sont gérés (validation, 403/404, messages utilisateur).

Statuts :

- **OK** : implémenté, branché, cohérent avec le reste ;
- **PARTIEL** : présent mais incomplet, fragile ou incohérent UX/API ;
- **MANQUANT** : absent ou non branché.

### 4. Vérifier par l’exécution

Quand c’est possible, **exécuter** plutôt que seulement lire.

**Backend** (depuis `backend/`, aligné sur la CI pytest « hors e2e ») :

```bash
python -m pytest tests/ -m "not e2e" -v --tb=short
```

Ciblage si la zone est connue :

```bash
python -m pytest tests/unit/<module>/ -v --tb=short
python -m pytest tests/integration/<module>/ -v --tb=short
```

**Frontend** (depuis `frontend/`) :

```bash
npm run lint
npm run build
```

**E2E** : les specs Playwright sous `e2e/` ne font pas partie du job pytest CI courant ; les lancer si la fonctionnalité est critique UI (`npm run test` ou équivalent dans `e2e/package.json` selon le dépôt).

**Linter** : `ReadLints` sur les fichiers modifiés après changement.

Si un **agent navigateur** est disponible : parcourir le flux principal (création, édition, droits, messages d’erreur). Sinon : décrire le **scénario manuel** minimal restant à valider humainement.

### 5. Corriger et compléter

- Pour **PARTIEL** / **MANQUANT** : changements **minimaux** et alignés sur l’architecture existante (pas de refactor gratuit).
- Ajouter ou ajuster des **tests** pour la logique critique ; pour la convention des dossiers, marqueurs et visibilité Super Admin → se référer au skill **test** (fichier `.cursor/skills/test/SKILL.md` à la racine du dépôt) et à `backend/tests/README.md`.
- Après modification : **relancer** pytest ciblé ou complet + lint/build si le périmètre le justifie.

### 6. Complétude finale et transparence

- Reparcourir la checklist : mettre à jour chaque statut.
- Tout ce qui reste **non fait** (risque de régression, secret manquant, clarification produit) doit être dit **explicitement** dans la synthèse.

### 7. Synthèse pour l’utilisateur (en français)

Structure recommandée :

1. **Résumé** : fonctionnalité considérée comme complète ou non, en une phrase.
2. **Checklist de conformité** : points importants avec **OK / PARTIEL / MANQUANT** (et une brève justification ou chemin de fichier pour les doutes).
3. **Modifications effectuées** : liste courte des zones touchées (pas de gros blocs de code).
4. **Tests / commandes** : commandes lancées et résultat (succès / échec corrigé).
5. **Limites / TODO** : ce qui manque ou ce qui devrait être validé manuellement.

---

## Priorisation si le contexte est long ou contraint

1. **Sûreté et accès** (auth, permissions, données sensibles) ;
2. **Parcours métier principal** du prompt ;
3. **Régression** sur les flux adjacents ;
4. **Tests** automatisables sans infrastructure exotique ;
5. **Finitions** UX non bloquantes.

---

## Règles d’implémentation pour l’agent

- **Ne pas abandonner** au premier échec de test ou de build : analyser, corriger, relancer.
- **Ne pas demander** une validation utilisateur pour une action raisonnable et réversible (lancer tests, lint, petit correctif).
- **Respecter** les conventions du dépôt (règles `.cursor/rules/`, structure `backend/app/`, stack Vite/React).
- **Code** : pas de commentaires redondants ; commenter seulement les choix non évidents ou contraintes métier.
- **Portée** : ne pas étendre la fonctionnalité au-delà du prompt sauf bug bloquant découvert au passage (le mentionner dans la synthèse).

---

## Exemple d’utilisation

> `/check-feature`  
> Voici le prompt d’origine : […]  
> Vérifie que tout est en place, que ça fonctionne, et complète si besoin.

Comportement attendu :

1. Checklist à partir du prompt.
2. Inspection structurée (front, back, tests, câblage).
3. Exécution pytest / lint / build (et e2e si pertinent).
4. Correctifs ciblés + tests si trou de couverture.
5. Synthèse structurée en français.
