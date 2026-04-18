"use client";

import { Download } from "lucide-react";
import type { SegmentResult } from "@/lib/api";

export interface DossierExportAllBarProps {
  segments: SegmentResult[];
  userCredits: number;
  creditsUnlimited: boolean;
  onExportAllAtelier?: (
    items: { search_id: string; credits_required: number }[],
    format: "xlsx" | "csv"
  ) => void;
  exporting: boolean;
  /** `panel` : carte complète ; `button` : bouton seul (barre d’actions). */
  variant?: "panel" | "button";
}

export default function DossierExportAllBar({
  segments,
  userCredits,
  creditsUnlimited,
  onExportAllAtelier,
  exporting,
  variant = "panel",
}: DossierExportAllBarProps) {
  const exportable = segments.filter(
    (s) =>
      s.search_id &&
      !s.error &&
      s.total > 0 &&
      !s.out_of_scope
  );
  const totalCredits = exportable.reduce((a, s) => a + (s.credits_required || 0), 0);
  const canExportAll = creditsUnlimited || userCredits >= totalCredits;

  if (!onExportAllAtelier || exportable.length === 0) return null;

  const button = (
    <button
      type="button"
      disabled={exporting || !canExportAll}
      onClick={() =>
        onExportAllAtelier(
          exportable.map((s) => ({
            search_id: s.search_id as string,
            credits_required: s.credits_required,
          })),
          "xlsx"
        )
      }
      className="inline-flex items-center justify-center gap-2 rounded-xl bg-white text-gray-950 px-4 py-2.5 text-sm font-medium hover:bg-gray-200 active:bg-gray-300 disabled:opacity-45 disabled:cursor-not-allowed transition-colors shrink-0 min-h-[44px]"
    >
      <Download size={15} />
      {exporting ? "Exports…" : "Exporter tout (Excel)"}
    </button>
  );

  if (variant === "button") {
    return button;
  }

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-surface-1 px-4 py-3 sm:px-5 sm:py-3.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-[0.1em] text-gray-500">
          Export dossier
        </p>
        <p className="text-sm text-gray-300 mt-0.5">
          <span className="tabular-nums text-white font-medium">{exportable.length}</span>{" "}
          {exportable.length === 1 ? "segment exportable" : "segments exportables"} — coût cumulé{" "}
          <span className="tabular-nums text-white font-medium">{totalCredits}</span> crédit
          {totalCredits > 1 ? "s" : ""} (Excel).
        </p>
        {!creditsUnlimited && userCredits < totalCredits && (
          <p className="text-xs text-amber-400/90 mt-1">
            Solde insuffisant ({userCredits} cr.) pour tout exporter.
          </p>
        )}
      </div>
      {button}
    </div>
  );
}
