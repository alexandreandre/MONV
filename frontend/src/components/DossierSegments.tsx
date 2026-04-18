"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Briefcase,
  Building,
  Calculator,
  ChevronDown,
  ChevronUp,
  Factory,
  Landmark,
  Megaphone,
  Scale,
  Target,
  Truck,
  Users,
  type LucideIcon,
} from "lucide-react";
import ResultsTable from "./ResultsTable";
import DossierSection from "./DossierSection";
import {
  regenerateAtelierSegment,
  type BusinessDossierPayload,
  type SegmentResult,
} from "@/lib/api";
import { MODE_META, normalizeMode, type Mode } from "@/lib/modes";

const SEGMENT_ICONS: Record<string, LucideIcon> = {
  truck: Truck,
  target: Target,
  users: Users,
  briefcase: Briefcase,
  landmark: Landmark,
  building: Building,
  factory: Factory,
  megaphone: Megaphone,
  scale: Scale,
  calculator: Calculator,
};

export interface DossierSegmentsProps {
  segments: SegmentResult[];
  segmentLabelByKey: Record<string, string>;
  userCredits: number;
  creditsUnlimited: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
  conversationId?: string | null;
  onDossierReplaced?: (dossier: BusinessDossierPayload) => void;
  onNotify?: (kind: "success" | "error", message: string) => void;
  onCreditsRemaining?: (credits: number) => void;
  /** Colonne latérale à côté de la carte des flux (sans en-tête de section lourd). */
  variant?: "default" | "sidebar";
}

function SegmentBlock({
  segment,
  segmentLabelByKey,
  userCredits,
  creditsUnlimited,
  onExport,
  exporting,
  conversationId,
  onDossierReplaced,
  onNotify,
  onCreditsRemaining,
  regenLoading,
  onRegenStart,
  onRegenEnd,
}: {
  segment: SegmentResult;
  segmentLabelByKey: Record<string, string>;
  userCredits: number;
  creditsUnlimited: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
  conversationId?: string | null;
  onDossierReplaced?: (dossier: BusinessDossierPayload) => void;
  onNotify?: (kind: "success" | "error", message: string) => void;
  onCreditsRemaining?: (credits: number) => void;
  regenLoading: boolean;
  onRegenStart: () => void;
  onRegenEnd: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const Icon = SEGMENT_ICONS[segment.icon] || Building;
  const mode: Mode = normalizeMode(segment.mode);
  const modeMeta = MODE_META[mode];

  const isOutOfScope = Boolean(segment.out_of_scope);
  const hasResults = !segment.error && segment.total > 0;

  const canRegen =
    Boolean(conversationId) &&
    !isOutOfScope &&
    typeof onDossierReplaced === "function";

  async function handleRegenerate() {
    if (!conversationId || !onDossierReplaced) return;
    onRegenStart();
    try {
      const res = await regenerateAtelierSegment(segment.key, {
        conversation_id: conversationId,
      });
      onDossierReplaced(res.dossier);
      if (typeof res.credits_remaining === "number") {
        onCreditsRemaining?.(res.credits_remaining);
      }
      onNotify?.("success", "Segment mis à jour.");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Relance impossible.";
      onNotify?.("error", msg);
    } finally {
      onRegenEnd();
    }
  }

  return (
    <div
      id={`atelier-segment-${segment.key}`}
      className="rounded-2xl border border-white/[0.06] bg-surface-1 overflow-hidden scroll-mt-24"
    >
      <div className="flex w-full items-stretch gap-0">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex-1 flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left min-w-0"
        >
          <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-gray-300">
            <Icon size={16} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-sm font-semibold text-white">{segment.label}</h4>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${modeMeta.badgeBg} ${modeMeta.badgeText}`}
              >
                <modeMeta.icon size={10} />
                Mode {modeMeta.label}
              </span>
              {isOutOfScope ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-medium rounded-full px-2 py-0.5 border border-violet-500/30 bg-violet-500/10 text-violet-200">
                  Hors annuaires MONV
                </span>
              ) : hasResults ? (
                <span className="text-[11px] tabular-nums text-gray-500">
                  {segment.total} résultat{segment.total > 1 ? "s" : ""}
                  {typeof segment.total_relevant === "number" &&
                    segment.total_relevant > 0 &&
                    segment.total_relevant !== segment.total && (
                      <span className="text-gray-600">
                        {" "}
                        · {segment.total_relevant} pertinent
                        {segment.total_relevant > 1 ? "s" : ""}
                      </span>
                    )}
                </span>
              ) : segment.error ? (
                <span className="inline-flex items-center gap-1 text-[11px] text-amber-400">
                  <AlertTriangle size={11} />
                  Indisponible
                </span>
              ) : (
                <span className="text-[11px] text-gray-600">Aucun résultat</span>
              )}
            </div>
            {segment.description && (
              <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                {segment.description}
              </p>
            )}
          </div>
          <div className="flex-shrink-0 text-gray-500 self-center">
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </button>
        {canRegen && (
          <div className="flex items-center border-l border-white/[0.06] px-2 shrink-0">
            <button
              type="button"
              disabled={regenLoading}
              onClick={(ev) => {
                ev.stopPropagation();
                void handleRegenerate();
              }}
              className="text-[11px] font-medium text-teal-300 hover:text-teal-200 disabled:opacity-40 px-2 py-2 rounded-lg hover:bg-white/[0.04] transition-colors whitespace-nowrap"
            >
              {regenLoading ? "Relance…" : "Relancer"}
            </button>
          </div>
        )}
      </div>

      {expanded && (
        <div className="border-t border-white/[0.04] px-1 pb-1">
          {isOutOfScope ? (
            <p className="px-3 py-4 text-xs text-gray-400 leading-relaxed">
              {segment.out_of_scope_note?.trim() ||
                "Ce segment n’est pas couvert par les annuaires d’entreprises françaises MONV. Complète par recherche web ou terrain."}
            </p>
          ) : segment.error ? (
            <p className="px-3 py-4 text-xs text-gray-500">
              {segment.error} Recherche associée :{" "}
              <span className="text-gray-400">&laquo; {segment.query} &raquo;</span>
            </p>
          ) : hasResults && segment.search_id ? (
            <ResultsTable
              data={segment.preview}
              columns={segment.columns}
              total={segment.total}
              searchId={segment.search_id}
              creditsRequired={segment.credits_required}
              userCredits={userCredits}
              creditsUnlimited={creditsUnlimited}
              onExport={onExport}
              exporting={exporting}
              mapPoints={segment.map_points}
              segmentLabelByKey={segmentLabelByKey}
            />
          ) : hasResults ? (
            <ResultsTable
              data={segment.preview}
              columns={segment.columns}
              total={segment.total}
              searchId=""
              creditsRequired={segment.credits_required}
              userCredits={0}
              creditsUnlimited={false}
              onExport={() => {}}
              exporting={false}
              mapPoints={segment.map_points}
              segmentLabelByKey={segmentLabelByKey}
            />
          ) : (
            <p className="px-3 py-4 text-xs text-gray-500">
              Aucune entreprise trouvée pour ce segment. Essaie d&rsquo;élargir
              la zone ou le secteur dans une nouvelle session.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function DossierSegments({
  segments,
  segmentLabelByKey,
  userCredits,
  creditsUnlimited,
  onExport,
  exporting,
  conversationId,
  onDossierReplaced,
  onNotify,
  onCreditsRemaining,
  variant = "default",
}: DossierSegmentsProps) {
  const [loadingKey, setLoadingKey] = useState<string | null>(null);

  if (segments.length === 0) return null;

  const blocks = (
    <div className="space-y-3">
      {segments.map((seg) => (
        <SegmentBlock
          key={seg.key}
          segment={seg}
          segmentLabelByKey={segmentLabelByKey}
          userCredits={userCredits}
          creditsUnlimited={creditsUnlimited}
          onExport={onExport}
          exporting={exporting}
          conversationId={conversationId}
          onDossierReplaced={onDossierReplaced}
          onNotify={onNotify}
          onCreditsRemaining={onCreditsRemaining}
          regenLoading={loadingKey === seg.key}
          onRegenStart={() => setLoadingKey(seg.key)}
          onRegenEnd={() => setLoadingKey(null)}
        />
      ))}
    </div>
  );

  if (variant === "sidebar") {
    return blocks;
  }

  return (
    <DossierSection
      icon={Target}
      title="Entreprises réelles à activer"
      subtitle="Tableaux générés via le pipeline MONV — chaque liste est exportable."
    >
      {blocks}
    </DossierSection>
  );
}
