"use client";

import type { ReactNode } from "react";

export type DossierTabId = "carte" | "tableaux" | "rapport";

const LABELS: Record<DossierTabId, string> = {
  carte: "Carte",
  tableaux: "Tableaux",
  rapport: "Rapport",
};

export interface DossierTabsProps {
  value: DossierTabId;
  onChange: (id: DossierTabId) => void;
  panels: Record<DossierTabId, ReactNode>;
}

export default function DossierTabs({ value, onChange, panels }: DossierTabsProps) {
  const ids = (Object.keys(LABELS) as DossierTabId[]).filter((k) => k in panels);

  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden">
      <div
        role="tablist"
        aria-label="Sections du dossier"
        className="flex border-b border-border bg-muted/50/80"
      >
        {ids.map((id) => {
          const active = value === id;
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={active}
              id={`dossier-tab-${id}`}
              onClick={() => onChange(id)}
              className={`flex-1 min-h-[44px] px-3 py-2.5 text-xs font-medium transition-colors border-b-2 -mb-px ${
                active
                  ? "text-foreground border-teal-600/60 bg-card"
                  : "text-muted-foreground border-transparent hover:text-muted-foreground"
              }`}
            >
              {LABELS[id]}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        aria-labelledby={`dossier-tab-${value}`}
        className="p-4 sm:p-5"
      >
        {panels[value]}
      </div>
    </div>
  );
}
