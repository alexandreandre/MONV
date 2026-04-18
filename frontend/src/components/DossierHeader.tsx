"use client";

import { Compass } from "lucide-react";
import type { ReactNode } from "react";

export interface DossierHeaderProps {
  nom: string;
  tagline: string;
  totals?: { raw: number; unique: number; relevant: number } | null;
  gradientFrom: string;
  gradientTo: string;
  accentText: string;
  /** Affiché à côté du badge Atelier (dossiers récents). */
  version?: number | null;
  segmentCount?: number | null;
  /** Boutons CTA (brief, export, etc.). */
  actionsSlot?: ReactNode;
}

export default function DossierHeader({
  nom,
  tagline,
  totals,
  gradientFrom,
  gradientTo,
  accentText,
  version,
  segmentCount,
  actionsSlot,
}: DossierHeaderProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-surface-1">
      <div
        className={`h-1 w-full bg-gradient-to-r ${gradientFrom} ${gradientTo} opacity-50`}
      />
      <div className="p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-2">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.1em] border border-white/[0.06] ${accentText}`}
            >
              <Compass size={10} />
              Dossier Atelier
            </span>
            {version != null && version > 0 && (
              <span className="text-[11px] tabular-nums text-gray-500 border border-white/[0.08] rounded-full px-2 py-0.5">
                v{version}
              </span>
            )}
            {segmentCount != null && segmentCount >= 0 && (
              <span className="text-[11px] text-gray-500">
                {segmentCount} segment{segmentCount > 1 ? "s" : ""}
              </span>
            )}
          </div>
          {actionsSlot ? (
            <div className="flex flex-col sm:flex-row flex-wrap gap-2 shrink-0">{actionsSlot}</div>
          ) : null}
        </div>
        <h2 className="text-xl sm:text-2xl font-bold text-white leading-tight">
          {nom}
        </h2>
        {tagline && (
          <p className="text-sm text-gray-400 mt-1 leading-relaxed">{tagline}</p>
        )}

        {totals && (
          <div className="mt-4 rounded-xl border border-white/[0.06] bg-surface-2 px-3 py-2.5">
            <p className="text-[11px] uppercase tracking-[0.1em] text-gray-500 mb-1">
              Vue agrégée (dossier)
            </p>
            <p className="text-xs text-gray-300 tabular-nums">
              <span className="text-white font-medium">{totals.raw}</span> lignes brutes (somme
              segments) ·{" "}
              <span className="text-white font-medium">{totals.unique}</span> uniques (SIREN) ·{" "}
              <span className="text-white font-medium">{totals.relevant}</span> pertinentes (aperçu)
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
