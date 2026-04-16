/**
 * Agents MONV — niveau hiérarchique SUPERIEUR aux 4 modes.
 *
 * Un agent orchestre plusieurs recherches du pipeline MONV et produit un
 * livrable structuré (pas un simple tableau). Pour l'instant, un seul agent
 * est exposé : l'Atelier. Le type reste ouvert pour accueillir de futurs
 * agents (ex: « Audit », « Due diligence »).
 *
 * Synchronisé avec backend/services/agent.py (ATELIER_MODE_LABEL).
 */

import type { LucideIcon } from "lucide-react";
import { Compass } from "lucide-react";

export type Agent = "atelier";

export const AGENTS: Agent[] = ["atelier"];

export interface AgentMeta {
  id: Agent;
  label: string;
  short: string;
  tagline: string;
  description: string;
  placeholder: string;
  icon: LucideIcon;
  /** Accent visuel : teal/cyan (hors palette des 4 modes emerald/sky/amber/violet). */
  gradientFrom: string;
  gradientTo: string;
  accentText: string;
  ringColor: string;
  badgeBg: string;
  badgeText: string;
}

export const AGENT_META: Record<Agent, AgentMeta> = {
  atelier: {
    id: "atelier",
    label: "Atelier",
    short: "Parcours projet",
    tagline: "QCM court, puis dossier structuré et listes d’entreprises.",
    description:
      "Tu décris le projet, tu réponds à 4 questions, tu reçois un business model, une cartographie des flux et des tableaux d’entreprises à contacter (données publiques).",
    placeholder:
      "Secteur, zone, clientèle, offre — ce que tu veux lancer ou structurer.",
    icon: Compass,
    /** Accent discret (évite le duo teal/cyan « slide produit »). */
    gradientFrom: "from-teal-700",
    gradientTo: "to-teal-800",
    accentText: "text-teal-200/90",
    ringColor: "ring-teal-500/35",
    badgeBg: "bg-teal-500/15",
    badgeText: "text-teal-300",
  },
};

/** Étiquette stockée dans `conversations.mode` pour les conversations Atelier. */
export const ATELIER_MODE_LABEL = "atelier";

export function isAgentMode(value: unknown): value is Agent {
  return typeof value === "string" && (AGENTS as string[]).includes(value);
}
