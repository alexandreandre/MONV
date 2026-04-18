"use client";

import {
  Coins,
  Gauge,
  Lightbulb,
  ListChecks,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";
import type { BusinessDossierPayload } from "@/lib/api";
import DossierSection from "./DossierSection";

export default function DossierSynthesis({
  synthesis,
}: {
  synthesis: BusinessDossierPayload["synthesis"];
}) {
  const blocks: {
    icon: LucideIcon;
    title: string;
    items: string[];
    accent: string;
    ordered?: boolean;
    anchorId?: string;
  }[] = [
    {
      icon: Lightbulb,
      title: "Forces du projet",
      items: synthesis.forces,
      accent: "border-emerald-500/20 bg-emerald-500/5",
      anchorId: "atelier-synth-forces",
    },
    {
      icon: ShieldAlert,
      title: "Risques à surveiller",
      items: synthesis.risques,
      accent: "border-amber-500/20 bg-amber-500/5",
      anchorId: "atelier-synth-risques",
    },
    {
      icon: ListChecks,
      title: "Prochaines étapes",
      items: synthesis.prochaines_etapes,
      accent: "border-sky-500/20 bg-sky-500/5",
      ordered: true,
    },
    {
      icon: Gauge,
      title: "KPIs à suivre",
      items: synthesis.kpis,
      accent: "border-teal-500/20 bg-teal-500/5",
    },
  ].filter((b) => b.items && b.items.length > 0);

  if (blocks.length === 0 && !synthesis.budget_estimatif) return null;

  return (
    <DossierSection
      icon={ListChecks}
      title="Synthèse & prochaines étapes"
      subtitle="Points d'attention et plan d'action immédiat."
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {blocks.map((b) => {
          const Icon = b.icon;
          return (
            <div
              key={b.title}
              id={b.anchorId}
              className={`rounded-xl border ${b.accent} p-4 scroll-mt-24`}
            >
              <div className="flex items-center gap-2 mb-3">
                <Icon size={13} className="text-gray-300" />
                <h4 className="text-xs font-semibold text-white">{b.title}</h4>
              </div>
              {b.ordered ? (
                <ol className="space-y-2 text-xs text-gray-300 leading-relaxed">
                  {b.items.map((item, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-white/[0.06] text-gray-300 text-[10px] font-semibold flex items-center justify-center tabular-nums">
                        {i + 1}
                      </span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <ul className="space-y-2 text-xs text-gray-300 leading-relaxed">
                  {b.items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="mt-1.5 w-1 h-1 rounded-full bg-gray-400 flex-shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      {synthesis.budget_estimatif && (
        <div className="mt-3 rounded-xl border border-white/[0.06] bg-surface-1 px-4 py-3 flex items-center gap-3">
          <Coins size={14} className="text-amber-300 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-[10px] uppercase tracking-[0.1em] text-gray-500">
              Budget estimatif indicatif
            </p>
            <p className="text-sm text-gray-200 mt-0.5">
              {synthesis.budget_estimatif}
            </p>
          </div>
        </div>
      )}
    </DossierSection>
  );
}
