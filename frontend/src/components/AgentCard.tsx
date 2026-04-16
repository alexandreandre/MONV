"use client";

import { ArrowRight, Sparkles } from "lucide-react";
import { AGENT_META, type Agent } from "@/lib/agents";

interface Props {
  agent?: Agent;
  onOpen: () => void;
  disabled?: boolean;
}

/**
 * Carte hero affichée au-dessus du ModeSelector sur le landing.
 * Son rôle est d'établir une hiérarchie claire : l'Atelier vient *avant*
 * le choix d'un mode de recherche, c'est une expérience produit distincte.
 */
export default function AgentCard({
  agent = "atelier",
  onOpen,
  disabled = false,
}: Props) {
  const meta = AGENT_META[agent];
  const Icon = meta.icon;

  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={disabled}
      className={`group relative w-full text-left rounded-2xl border-l-2 border border-white/[0.06] bg-surface-1 p-4 sm:p-5 transition-colors hover:border-white/[0.12] hover:bg-surface-2 ${
        disabled ? "opacity-60 cursor-not-allowed" : ""
      }`}
      style={{ borderLeftColor: "rgb(232 121 249 / 0.45)" }}
    >
      <div className="flex items-start gap-4">
        <div
          className={`flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br ${meta.gradientFrom} ${meta.gradientTo} flex items-center justify-center text-white`}
        >
          <Icon size={18} />
        </div>

        <div className="flex-1 min-w-0">
          <span
            className={`inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.1em] ${meta.accentText} mb-1`}
          >
            <Sparkles size={10} />
            Agent
          </span>
          <h3 className="text-sm sm:text-base font-semibold text-white leading-tight">
            {meta.label} —{" "}
            <span className="text-gray-400 font-normal">{meta.short}</span>
          </h3>
          <p className="text-xs text-gray-500 mt-1 leading-relaxed">
            {meta.tagline}
          </p>
        </div>

        <div className="hidden sm:flex flex-shrink-0 items-center gap-1.5 text-xs font-medium text-gray-500 group-hover:text-gray-300 transition-colors pt-1">
          Lancer
          <ArrowRight size={14} />
        </div>
      </div>
    </button>
  );
}
