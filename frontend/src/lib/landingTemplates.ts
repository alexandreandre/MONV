import type { Template } from "./api";

/** Exemples affichés sur la landing — source unique côté client (sans attente réseau). */
export const LANDING_TEMPLATES: Template[] = [
  {
    id: "boutique-padel-site-web",
    title: "Boutiques de padel",
    description:
      "Clubs et magasins de padel à contacter pour une offre de site web",
    query:
      "Je cherche des boutiques de padel et clubs de padel pour leur proposer la création ou la refonte d'un site web",
    icon: "activity",
  },
  {
    id: "hotel-3-etoiles-marseille-rachat",
    title: "Hôtels 3 étoiles",
    description:
      "Établissements hôteliers 3★ pour étude de potentiel rachat",
    query:
      "Je cherche des hôtels 3 étoiles pour une analyse de potentiel rachat ou d'acquisition",
    icon: "hotel",
  },
  {
    id: "startup-saas-paris",
    title: "Startups SaaS à Paris",
    description:
      "Startups SaaS de 10 à 50 salariés basées à Paris, créées depuis 2020",
    query:
      "Je cherche des startups SaaS à Paris, entre 10 et 50 salariés, créées depuis 2020",
    icon: "rocket",
  },
  {
    id: "prestataire-informatique",
    title: "Prestataire informatique",
    description: "ESN et agences de développement en Île-de-France",
    query:
      "Je cherche un prestataire informatique en Île-de-France, ESN ou agence de développement",
    icon: "monitor",
  },
  {
    id: "fournisseur-btp",
    title: "Fournisseurs BTP",
    description: "Fournisseurs de matériaux de construction en France",
    query:
      "Trouve-moi des fournisseurs de matériaux de construction, PME avec plus de 10 salariés",
    icon: "truck",
  },
  {
    id: "cabinet-comptable",
    title: "Cabinets comptables à Lyon",
    description: "Experts-comptables et cabinets d'audit à Lyon et alentours",
    query: "Je cherche un cabinet comptable ou expert-comptable à Lyon",
    icon: "calculator",
  },
  {
    id: "pme-industrielles-rhone-alpes",
    title: "PME industrielles Rhône-Alpes",
    description:
      "PME industrielles en Auvergne-Rhône-Alpes avec CA > 1M\u202f€",
    query:
      "Trouve-moi des PME industrielles en Rhône-Alpes avec un chiffre d'affaires supérieur à 1 million d'euros",
    icon: "factory",
  },
  {
    id: "agence-communication",
    title: "Agences de communication",
    description: "Agences de pub, marketing et communication à Bordeaux",
    query:
      "Je cherche des agences de communication et marketing à Bordeaux",
    icon: "megaphone",
  },
  {
    id: "btp-marseille",
    title: "Entreprises BTP à Marseille",
    description: "Entreprises du BTP à Marseille, 20 à 200 salariés",
    query:
      "Je cherche des entreprises du BTP à Marseille entre 20 et 200 salariés",
    icon: "building",
  },
  {
    id: "cabinet-avocats",
    title: "Cabinets d'avocats à Paris",
    description:
      "Cabinets d'avocats spécialisés en droit des affaires à Paris",
    query:
      "Trouve-moi des cabinets d'avocats en droit des affaires à Paris",
    icon: "scale",
  },
];
