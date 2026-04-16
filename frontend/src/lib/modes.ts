/**
 * 4 modes d'usage MONV — synchronisés avec backend/services/modes.py.
 *
 * Le mode `prospection` est le défaut : un envoi sans `mode` produit
 * exactement le même comportement qu'avant l'introduction des modes.
 */

import type { LucideIcon } from "lucide-react";
import { Target, Truck, Briefcase, Landmark } from "lucide-react";

export type Mode = "prospection" | "sous_traitant" | "client" | "rachat";

export const MODES: Mode[] = ["prospection", "sous_traitant", "client", "rachat"];

export const DEFAULT_MODE: Mode = "prospection";

/** Ancien identifiant API / historique — mappé vers `sous_traitant` côté client et serveur. */
const LEGACY_MODE_ALIASES: Record<string, Mode> = {
  fournisseurs: "sous_traitant",
};

export interface ModeMeta {
  id: Mode;
  label: string;
  short: string;
  description: string;
  placeholder: string;
  /** Tailwind utility used as accent — palette déjà présente (emerald/sky/amber/violet). */
  accent: string;
  badgeBg: string;
  badgeText: string;
  icon: LucideIcon;
}

export const MODE_META: Record<Mode, ModeMeta> = {
  prospection: {
    id: "prospection",
    label: "Prospection",
    short: "Prospecter",
    description: "Trouver des clients à démarcher",
    placeholder: "Décrivez la cible commerciale (secteur, zone, taille)…",
    accent: "border-emerald-500/40 text-emerald-300 bg-emerald-500/10",
    badgeBg: "bg-emerald-500/15",
    badgeText: "text-emerald-300",
    icon: Target,
  },
  sous_traitant: {
    id: "sous_traitant",
    label: "Sous-traitant",
    short: "Trouver un sous-traitant",
    description: "Identifier un fournisseur ou prestataire",
    placeholder: "Quel type de prestation, où, quelle capacité requise ?",
    accent: "border-sky-500/40 text-sky-300 bg-sky-500/10",
    badgeBg: "bg-sky-500/15",
    badgeText: "text-sky-300",
    icon: Truck,
  },
  client: {
    id: "client",
    label: "Client",
    short: "Mon portefeuille",
    description: "Enrichir mes comptes existants (collez des SIREN)",
    placeholder: "Collez vos SIREN ou décrivez vos comptes à analyser…",
    accent: "border-amber-500/40 text-amber-300 bg-amber-500/10",
    badgeBg: "bg-amber-500/15",
    badgeText: "text-amber-300",
    icon: Briefcase,
  },
  rachat: {
    id: "rachat",
    label: "Rachat",
    short: "Cible de rachat",
    description: "Cadre d'analyse pour cibles d'acquisition (factuel, non personnalisé)",
    placeholder: "Type d'activité visée, zone, taille / CA approximatif…",
    accent: "border-violet-500/40 text-violet-300 bg-violet-500/10",
    badgeBg: "bg-violet-500/15",
    badgeText: "text-violet-300",
    icon: Landmark,
  },
};

export function isMode(value: unknown): value is Mode {
  return typeof value === "string" && (MODES as string[]).includes(value);
}

export function normalizeMode(value: unknown): Mode {
  if (typeof value !== "string" || value === "") return DEFAULT_MODE;
  const legacy = LEGACY_MODE_ALIASES[value];
  if (legacy) return legacy;
  if ((MODES as string[]).includes(value)) return value as Mode;
  return DEFAULT_MODE;
}
