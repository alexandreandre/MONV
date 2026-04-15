---
name: test
description: Guide l’ajout et l’exécution des tests backend (pytest) pour qu’ils passent en CI GitHub et apparaissent dans l’arbre de la page Super Admin « Tests ». À utiliser lorsque l’utilisateur tape /test, demande d’alimenter les tests, de vérifier la CI, ou de couvrir une fonctionnalité avec des tests découverts par pytest et l’UI super-admin.
---

# Tests backend (/test)

## Objectif

Quand ce skill est actif, l’agent doit **compléter les tests manquants** pour une zone de code ou une fonctionnalité, de façon à ce que :

1. **pytest** les découvre et les exécute depuis `backend/` ;
2. le job **GitHub Actions « Backend (tests + OpenAPI) »** les prenne en compte (même commande que localement, sans fichier de liste à maintenir) ;
3. la page **Super Admin → Tests** affiche les nouvelles cibles dans l’arbre (généré à partir du disque).

---

## Cartographie (ne pas improviser les chemins)

| Besoin | Emplacement | CI | Super Admin |
|--------|----------------|-----|-------------|
| Tests unitaires par module | `backend/tests/unit/<module>/` (dossier = un module, pas de préfixe `_`) | Inclus (`pytest tests/ -m "not e2e"`) | Niveau « Unitaires » → sous-dossier `<module>` |
| Tests d’intégration API / repo / wiring | `backend/tests/integration/<module>/` | Idem | Niveau « Intégration » → `<module>` |
| Smoke / E2E Python | `backend/tests/e2e/` (`test_*.py`, `cross_module/`) | **Exclus** du job CI actuel (`-m "not e2e"`) — à lancer manuellement ou via Super Admin | Niveau « E2E / Smoke » |
| Migrations / régression SQL paie | `backend/tests/migration/` (`test_*.py`) | Inclus si non marqués `e2e` | Niveau « Migration » |
| Garde-fous architecture | `backend/tests/unit/architecture/` (`test_*.py`) | Inclus | Niveau « Architecture » |
| E2E navigateur | Dépôt `e2e/` (Playwright, `specs/*.spec.ts`) | Non lancé par le job pytest CI | Niveau « E2E navigateur (Playwright) » si `e2e/` présent |

- **Racine pytest** : répertoire `backend/` ; les cibles sont des chemins **relatifs à `backend/`** (ex. `tests/unit/payroll`, `tests/integration/super_admin`).
- **Secrets CI** : le backend CI utilise un **vrai Supabase** (`SUPABASE_URL`, `SUPABASE_KEY`, etc.). Les tests ne doivent pas supposer une base fictive ; les tests unitaires restent **hermétiques** (mocks), l’intégration peut mocker ou s’appuyer sur l’env selon les patterns existants.

---

## Workflow obligatoire

1. **Identifier le trou**
   - Relier la fonctionnalité ou le module aux dossiers `app/modules/<nom>/` (ou `app/core/`, etc.).
   - Vérifier si `backend/tests/unit/<nom>/` et/ou `backend/tests/integration/<nom>/` existent et contiennent déjà `test_*.py` pertinents (domain, service, commands, queries, `test_api.py`, …).

2. **Lire les conventions du dépôt**
   - Ouvrir et respecter **`backend/tests/README.md`** (markers, fixtures `client`, `auth_headers`, `dependency_overrides`, nommage, pas de 500 en smoke E2E, nettoyage des overrides).

3. **Ajouter ou compléter les fichiers**
   - Créer le **dossier module** sous `unit/` ou `integration/` si absent (même nom que le module métier quand c’est le cas dans le reste du repo).
   - Fichiers : `test_<sujet>.py` ; en tête de module : `pytestmark = pytest.mark.unit` ou `pytest.mark.integration` (voir `pytest.ini`).
   - **Ne pas** marquer `e2e` les tests destinés à la CI backend courante (sinon ils ne s’exécutent pas dans le job « Pytest (hors e2e) »).

4. **Valider localement**
   - Depuis `backend/` :
     - `python -m pytest tests/ -m "not e2e" -v --tb=short` (aligné CI) ;
     - puis cible fine : `python -m pytest tests/unit/<module>/ -v` ou `tests/integration/<module>/ -v`.

5. **Vérifier la découverte Super Admin (logique)**
   - L’arbre est produit par `get_tests_tree()` : sous `unit/` et `integration/`, **chaque sous-dossier** (hors `_…`) devient une branche. Pas de modification front ou route API nécessaire si seuls de nouveaux fichiers/dossiers sous `backend/tests/` sont ajoutés.

6. **Playwright / e2e navigateur**
   - Si la demande concerne l’UI critique navigateur : ajouter ou mettre à jour `e2e/specs/*.spec.ts` ; exécution via `e2e/` (`npm run test`). Rappeler que ce n’est **pas** dans la commande pytest du workflow CI actuel.

---

## Ce que l’agent ne doit pas faire

- Ne pas ajouter de **liste manuelle** de tests dans la CI : la découverte est **pytest**.
- Ne pas dupliquer la doc longue de `README.md` dans le chat : s’y référer et appliquer.
- Pas de `print` de debug laissé ; pas de refactor hors périmètre tests.

---

## Réponse attendue à l’utilisateur

Après exécution du workflow, résumer : fichiers créés ou modifiés, commandes pytest lancées, résultat ; mentionner explicitement **CI** (marqueur `e2e` vs non) et **visibilité** dans l’arbre Super Admin (niveau + nom de dossier).

Pour le détail des fixtures et patterns (auth, skip, smoke), voir [backend/tests/README.md](../../../backend/tests/README.md).
