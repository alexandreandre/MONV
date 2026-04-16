---
name: frontend-design
description: >-
  Pousse l’UI comme en atelier : intention claire, détails qui tiennent la route,
  zéro esthétique « sortie LLM ». S’appuie sur le thème et le code existants ;
  typographie, rythme, états, responsive, a11y. À utiliser pour peaufiner un
  écran, un flux, ou quand l’utilisateur veut du sérieux sans look template.
---

# Frontend design — atelier, pas moodboard générique

## Ce qu’on cherche

Une interface qui **assume un parti pris** : on devrait pouvoir expliquer *pourquoi* ce rayon, ce gris, ce rythme — comme en soutenance d’école d’art, pas comme une slide « best practices ».

L’agent ne « décore » pas : il **cadre** (hiérarchie, silence, accent), il **ancre** dans le produit et les tokens déjà là, et il évite les tics visuels que tout le monde reconnaît comme sortis d’un prompt.

## Quand sortir ce skill

- Polissage UI, refonte légère, « ça fait cheap / démo ».
- Besoin d’états complets, de mobile qui respire, de focus clavier qui ne fait pas honte.
- Consigne explicite : pas d’air **template IA** / **SaaS clipart**.

## Le « jury » : ce qui te fait recaler

Pas une liste de honte — des **signaux** que le rendu est lazy. Contre-chaque fois par quelque chose de **mesurable** dans le repo (variable, composant voisin, copie réelle).

| Signal | Lecture jury | Plutôt |
|--------|--------------|--------|
| Gradient violet / bleu « tech » hors charte | Tu caches l’absence d’idée | 1 accent documenté, surfaces neutres qui portent le contenu |
| `rounded-3xl` + ombre diffuse partout | Une seule recette pour tout | 2 niveaux max de relief (ex. surface / élévation), rayons **gradués** selon l’importance |
| Grille 3×3 de cartes clones + pictos stock | Tu remplis la page, tu ne la conçois pas | Casser la grille : pleine largeur, listes denses, détails typographiques, **vrais** libellés |
| Inter / système par défaut, tailles au pif | Tu n’as pas construit d’échelle | Échelle modulaire (ex. 12/14/16/20/28), interlignage et tracking cohérents |
| Motion sur chaque hover | Bruit, pas feedback | Mouvement **utile** : transition d’état, apparition de contenu ; `prefers-reduced-motion` si le stack le permet |
| Copy type « Unlock / Empower / Seamless » | Tu parles à personne | Textes du produit ou faits utilisateur ; silence > slogan |
| Dark mode plat gris | Tu as inversé les couleurs, pas conçu le sombre | Nuances de surface, bordures presque invisibles, hiérarchie par luminance |

**Maquette ou charte imposée** → elle gagne sur ce tableau.

## Principes (version studio)

1. **Reconnaissance** — Lire tokens, thème, 2–3 écrans proches. Le style existe déjà : on l’étend, on ne clone pas un second design system.
2. **Une idée par zone** — Foyer unique ; le reste est support (métadonnées plus fines, moins saturées). Pas tout en `font-semibold`.
3. **Rythme** — Grille ou base d’espacement ; aligner les **bords** et les **gouttières** entre blocs frères. Les yeux sentent les 3 px « au hasard ».
4. **Couleur avec parcimonie** — Accent rare = accent qui compte. États sémantiques alignés sur l’existant ; contrastes tenables (WCAG sur texte et contrôles).
5. **États = partie du design** — `:focus-visible`, disabled, loading, vide, erreur : même niveau de soin que le happy path.
6. **Mobile** — Longueur de ligne, zones tactiles, info critique jamais réservée au seul hover.
7. **Texture légère** — Grain, bordure 1px, léger décalage de teinte : OK si ça **sert** la hiérarchie, pas si c’est du bruit.

## Démarche (courte, sérieuse)

1. Cartographier fichiers + parents visuels.
2. Noter contraintes : tokens, lib UI, densité métier (outil vs vitrine).
3. Traduire la demande en **décisions** (ex. « métadonnées en 12px muted, titres en 20 semibold »), pas en « rendre plus joli ».
4. Itérer par petites touches cohérentes ; pas de refactor hors sujet.
5. Passer le filtre : focus clavier, breakpoints, thème clair/sombre si présent.

## Check avant de dire « c’est bon »

- [ ] Tu peux défendre chaque choix fort en une phrase (intention).
- [ ] Aucun cliché IA ajouté sans lien produit.
- [ ] Tokens / primitives du projet d’abord.
- [ ] États + a11y de base traités.
- [ ] Responsive aligné sur le reste de l’app.
- [ ] Aucune punchline marketing collée sans demande.

## Livrable agent

- Diff **ciblé** sur les fichiers UI concernés.
- Si plusieurs directions tiennent la route : **en choisir une**, cohérente avec le code, et l’expliquer en 2–3 phrases (en français si la conversation est en français).

## Sources

Priorité absolue au **dépôt** (composants, tokens, patterns). Éviter les tutos génériques et les galeries « inspiration » vides — elles réinjectent le même look que tu veux fuir.
