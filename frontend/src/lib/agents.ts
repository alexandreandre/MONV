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
  /** Classes Tailwind pour l'accent de l'agent — gradient fuchsia/rose afin
   *  de se différencier nettement des 4 modes (emerald/sky/amber/violet). */
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
    short: "Concevoir mon entreprise",
    tagline: "Transforme une idée en dossier de création actionnable.",
    description:
      "Décris ton projet, réponds à 4 questions, et reçois un business model, une cartographie des flux et des tableaux d'entreprises réelles à contacter.",
    placeholder:
      "Décris ton projet : secteur, ville, cible, ce que tu veux proposer…",
    icon: Compass,
    gradientFrom: "from-rose-500",
    gradientTo: "to-fuchsia-500",
    accentText: "text-fuchsia-300",
    ringColor: "ring-fuchsia-500/30",
    badgeBg: "bg-fuchsia-500/15",
    badgeText: "text-fuchsia-300",
  },
};

/** Étiquette stockée dans `conversations.mode` pour les conversations Atelier. */
export const ATELIER_MODE_LABEL = "atelier";

export function isAgentMode(value: unknown): value is Agent {
  return typeof value === "string" && (AGENTS as string[]).includes(value);
}
