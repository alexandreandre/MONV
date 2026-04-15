---
name: frontend-design
description: >-
  Améliore l’UI/UX du frontend à partir d’une description en langage naturel
  tout en évitant le rendu générique « fait par IA ». Couvre typographie,
  couleurs, espacements, états interactifs, responsive, accessibilité et
  cohérence avec le design system existant. À utiliser lorsque l’utilisateur
  demande de polir le design, de rendre une page plus professionnelle,
  d’éviter l’esthétique cliché IA, ou attache explicitement ce skill.
---

# Frontend design — UI crédible et non générique

## Objectif

Transformer ou affiner une interface **sans** tomber dans les motifs visuels reconnaissables d’outils IA : le résultat doit sembler **délibéré**, **contextuel** et **aligné** sur le produit et le code déjà en place.

## Quand utiliser ce skill

- Demande d’**améliorer le design** d’un écran, d’un composant ou d’un flux (souvent décrit en mots).
- Exigence explicite de **ne pas** ressembler à une démo / template / sortie IA.
- Besoin de **cohérence visuelle**, **états UI** (hover, focus, disabled, chargement, vide, erreur), **responsive** ou **accessibilité** côté frontend.

---

## Signaux « look IA » à éviter absolument

L’agent doit **refuser ces défauts par défaut** et proposer des alternatives ancrées dans le projet :

| À éviter | Pourquoi | Piste de remplacement |
|----------|----------|------------------------|
| Dégradés violets / bleus « tech » sans lien avec la marque | Cliché immédiat | Couleurs du thème existant, surfaces neutres, une seule accentuation |
| Coins ultra-arrondis partout + ombres douces identiques | Uniformisation cheap | Rayons et ombres **hiérarchisés** (1–2 niveaux max utiles) |
| Grilles de 3 cartes identiques + icônes génériques | Pattern « landing » | Variété de mise en page, vrais libellés, hiérarchie typographique |
| Typo système générique sans échelle | Manque de caractère | Échelle de tailles (ex. modulaire), graisses et interlignage cohérents |
| Micro-animations sur tout | Bruit visuel | Motion **fonctionnelle** (feedback, transition d’état) |
| Texte marketing creux (« Empower your workflow ») | Incohérent produit | Copie **concrète** ou textes existants du repo |
| Dark mode « gris uniforme » | Froid et artificiel | Surfaces en **nuances**, bordures subtiles, contraste maîtrisé |

Si l’utilisateur impose une direction forte (charte, maquette), **elle prime** sur ce tableau.

---

## Principes de design frontend (à appliquer)

1. **Lire d’abord** les composants, tokens CSS/Tailwind, thème et pages voisines : réutiliser variables, classes et patterns existants plutôt que d’inventer un second style.
2. **Hiérarchie** : un seul point focal par zone ; titres / corps / métadonnées clairement différenciés (taille, graisse, couleur, espacement — pas tout en gras).
3. **Espacement** : grille ou échelle cohérente (ex. multiples d’une base) ; éviter les marges « au feeling » différentes entre sections sœurs.
4. **Couleur** : peu de couleurs d’accent ; états sémantiques (succès, erreur, avertissement) alignés sur le design system ; contraste **WCAG** pour texte et contrôles.
5. **États** : hover, focus visible (`:focus-visible`), active, disabled, loading, empty — au moins ceux pertinents au composant.
6. **Responsive** : lecture confortable sur mobile (tap targets, line-length, pas de hover-only pour l’info critique).
7. **Motion** : courtes, discrètes ; `prefers-reduced-motion` respecté quand le stack le permet.
8. **Densité** : adapter à l’usage (outil pro vs marketing) plutôt qu’une densité « défaut IA ».

---

## Workflow recommandé

1. **Cartographier** : fichiers concernés (composants, styles globaux, assets).
2. **Extraire les contraintes** : design tokens, composants parent, librairie UI (MUI, shadcn, etc.).
3. **Traduire la description utilisateur** en changements **mesurables** (espacement, tailles, couleurs, structure, copie).
4. **Implémenter** en petites itérations cohérentes ; pas de refactor massif hors périmètre design.
5. **Vérifier** : contrastes, focus clavier, breakpoints, thème clair/sombre si applicable.

---

## Checklist avant de considérer la tâche terminée

- [ ] Aucun motif « template IA » introduit sans justification produit
- [ ] Réutilisation des tokens / classes / primitives du projet quand ils existent
- [ ] États interactifs et accessibilité de base (focus, contrastes) traités
- [ ] Comportement responsive cohérent avec le reste de l’app
- [ ] Copie factuelle ou existante ; pas de slogans génériques ajoutés sans demande

---

## Livrable attendu côté agent

- Modifications **ciblées** dans les fichiers UI concernés.
- Si plusieurs directions sont valides, **choisir une** alignée sur le code existant et la décrire brièvement à l’utilisateur (en français si la conversation est en français).

## Ressources optionnelles

Pour approfondir (lecture seulement si le besoin est spécifique), l’agent peut s’appuyer sur la documentation du design system ou des composants **déjà présents** dans le dépôt plutôt que sur des références externes génériques.
