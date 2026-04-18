"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileText, Maximize2, Minimize2, Pencil } from "lucide-react";
import FlowDiagram from "./FlowDiagram";
import BusinessModelCanvas from "./BusinessModelCanvas";
import DossierHeader from "./DossierHeader";
import DossierExecutiveOpening from "./DossierExecutiveOpening";
import DossierChecklist from "./DossierChecklist";
import DossierExportAllBar from "./DossierExportAllBar";
import DossierSegments from "./DossierSegments";
import DossierSynthesis from "./DossierSynthesis";
import BriefDrawer from "./BriefDrawer";
import type { BusinessDossierPayload } from "@/lib/api";
import { AGENT_META } from "@/lib/agents";

export interface AtelierDossierProps {
  dossier: BusinessDossierPayload;
  /** Pour relances API (segment, brief, canvas) — lecture seule si absent. */
  conversationId?: string | null;
  userCredits: number;
  creditsUnlimited?: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  onExportAllAtelier?: (
    items: { search_id: string; credits_required: number }[],
    format: "xlsx" | "csv"
  ) => void;
  exporting: boolean;
  onDossierReplaced?: (dossier: BusinessDossierPayload) => void;
  onNotify?: (kind: "success" | "error", message: string) => void;
  onCreditsRemaining?: (credits: number) => void;
}

export default function AtelierDossier({
  dossier,
  conversationId = null,
  userCredits,
  creditsUnlimited = false,
  onExport,
  onExportAllAtelier,
  exporting,
  onDossierReplaced,
  onNotify,
  onCreditsRemaining,
}: AtelierDossierProps) {
  const meta = AGENT_META.atelier;
  const { brief, canvas, flows, segments, synthesis } = dossier;
  const [briefOpen, setBriefOpen] = useState(false);
  const dossierShellRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const shell = dossierShellRef.current;
    const syncFs = () => setIsFullscreen(document.fullscreenElement === shell);
    document.addEventListener("fullscreenchange", syncFs);
    return () => document.removeEventListener("fullscreenchange", syncFs);
  }, []);

  const toggleDossierFullscreen = useCallback(async () => {
    const el = dossierShellRef.current;
    if (!el) return;
    try {
      if (document.fullscreenElement === el) {
        await document.exitFullscreen();
      } else {
        await el.requestFullscreen();
      }
    } catch {
      onNotify?.(
        "error",
        "Plein écran indisponible (navigateur, iframe ou permissions).",
      );
    }
  }, [onNotify]);

  const scrollToSegmentInTableaux = useCallback((segmentKey: string) => {
    const reducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const run = () => {
      const block = document.getElementById(`atelier-segment-${segmentKey}`);
      block?.scrollIntoView({
        behavior: reducedMotion ? "auto" : "smooth",
        block: "nearest",
      });
      block?.classList.add(
        "ring-2",
        "ring-teal-500/50",
        "transition-shadow",
        "duration-500",
      );
      window.setTimeout(() => {
        block?.classList.remove("ring-2", "ring-teal-500/50");
      }, 1600);
    };
    requestAnimationFrame(() => {
      requestAnimationFrame(run);
    });
  }, []);

  const openSegmentFromFlow = useCallback(
    (segmentKey: string) => {
      scrollToSegmentInTableaux(segmentKey);
    },
    [scrollToSegmentInTableaux],
  );

  const canMutate = Boolean(
    conversationId && onDossierReplaced && onNotify
  );

  const segmentLabelByKey = useMemo(
    () => Object.fromEntries(segments.map((s) => [s.key, s.label])),
    [segments]
  );

  const totals =
    typeof dossier.total_raw === "number"
      ? {
          raw: dossier.total_raw,
          unique: dossier.total_unique ?? 0,
          relevant: dossier.total_relevant ?? 0,
        }
      : null;

  return (
    <div
      ref={dossierShellRef}
      className={`animate-fade-in ${
        isFullscreen
          ? "min-h-full w-full bg-surface-0 overflow-y-auto overflow-x-hidden scrollbar-thin px-3 py-4 sm:px-6 sm:py-5 space-y-5"
          : "space-y-5 mt-4"
      }`}
    >
      <DossierHeader
        nom={brief.nom}
        tagline={brief.tagline}
        totals={totals}
        gradientFrom={meta.gradientFrom}
        gradientTo={meta.gradientTo}
        accentText={meta.accentText}
        version={dossier.version ?? null}
        segmentCount={segments.length}
        actionsSlot={
          <>
            <button
              type="button"
              onClick={toggleDossierFullscreen}
              aria-pressed={isFullscreen}
              title={
                isFullscreen
                  ? "Quitter le plein écran (Échap)"
                  : "Afficher la fiche en plein écran"
              }
              className={`inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium min-h-[44px] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-500/50 ${
                isFullscreen
                  ? "border-teal-500/40 bg-teal-500/10 text-teal-100 hover:bg-teal-500/15"
                  : "border-white/[0.12] bg-surface-2 text-gray-200 hover:bg-white/[0.04]"
              }`}
            >
              {isFullscreen ? (
                <Minimize2 size={15} aria-hidden />
              ) : (
                <Maximize2 size={15} aria-hidden />
              )}
              {isFullscreen ? "Quitter" : "Plein écran"}
            </button>
            {canMutate ? (
              <button
                type="button"
                onClick={() => setBriefOpen(true)}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/[0.12] bg-surface-2 px-4 py-2.5 text-sm font-medium text-gray-200 hover:bg-white/[0.04] min-h-[44px]"
              >
                <Pencil size={15} />
                Affiner le brief
              </button>
            ) : null}
            <DossierExportAllBar
              segments={segments}
              userCredits={userCredits}
              creditsUnlimited={creditsUnlimited}
              onExportAllAtelier={onExportAllAtelier}
              exporting={exporting}
              variant="button"
            />
            <button
              type="button"
              disabled
              title="Bientôt"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/[0.06] px-4 py-2.5 text-sm font-medium text-gray-500 min-h-[44px] cursor-not-allowed"
            >
              <FileText size={15} />
              Rapport PDF
            </button>
          </>
        }
      />

      <DossierExecutiveOpening brief={brief} synthesis={synthesis} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(280px,400px)] lg:items-start">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <h3 className="text-sm font-semibold text-white">Carte des flux</h3>
            <p className="text-[11px] text-gray-500 leading-snug max-w-md">
              Valeur, trésorerie et information — les acteurs reliés à un segment ouvrent le
              tableau correspondant dans la colonne de droite.
            </p>
          </div>
          <FlowDiagram
            flows={flows}
            segments={segments}
            onSegmentActivate={openSegmentFromFlow}
            graphHeightClassName="min-h-[320px] h-[440px] sm:h-[480px] lg:min-h-[380px] lg:h-[min(62vh,580px)]"
          />
        </div>

        {segments.length > 0 ? (
          <aside
            id="atelier-section-segments"
            className="min-w-0 lg:sticky lg:top-4 lg:max-h-[calc(100vh-5rem)] lg:overflow-y-auto lg:pr-1 scrollbar-thin scroll-mt-24"
          >
            <div className="mb-3 border-b border-white/[0.06] pb-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-500">
                Tableaux segmentés
              </p>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                Données pipeline MONV — la carte reste visible à gauche sur grand écran.
              </p>
            </div>
            <DossierSegments
              variant="sidebar"
              segments={segments}
              segmentLabelByKey={segmentLabelByKey}
              userCredits={userCredits}
              creditsUnlimited={creditsUnlimited}
              onExport={onExport}
              exporting={exporting}
              conversationId={canMutate ? conversationId : undefined}
              onDossierReplaced={canMutate ? onDossierReplaced : undefined}
              onNotify={canMutate ? onNotify : undefined}
              onCreditsRemaining={onCreditsRemaining}
            />
          </aside>
        ) : null}
      </div>

      <DossierChecklist synthesis={synthesis} />

      <div className="space-y-8 scroll-mt-24" id="atelier-section-synthesis">
        <div>
          <p className="text-xs text-gray-500 mb-3">
            Business Model Canvas — vue synthétique du projet.
          </p>
          <BusinessModelCanvas canvas={canvas} />
        </div>
        <DossierSynthesis synthesis={synthesis} />
      </div>

      {canMutate && conversationId && onDossierReplaced && onNotify ? (
        <BriefDrawer
          open={briefOpen}
          onClose={() => setBriefOpen(false)}
          conversationId={conversationId}
          brief={brief}
          onDossierReplaced={onDossierReplaced}
          onNotify={onNotify}
          onCreditsRemaining={onCreditsRemaining}
        />
      ) : null}
    </div>
  );
}
