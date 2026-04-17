"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Briefcase,
  Building,
  Calculator,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Coins,
  Compass,
  Download,
  Factory,
  Flag,
  Gauge,
  Landmark,
  Lightbulb,
  ListChecks,
  MapPin,
  Megaphone,
  Route,
  Scale,
  ShieldAlert,
  Target,
  Truck,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import ResultsTable from "./ResultsTable";
import BusinessModelCanvas from "./BusinessModelCanvas";
import FlowDiagram from "./FlowDiagram";
import type {
  BusinessDossierPayload,
  SegmentResult,
} from "@/lib/api";
import { AGENT_META } from "@/lib/agents";
import { MODE_META, normalizeMode, type Mode } from "@/lib/modes";

interface Props {
  dossier: BusinessDossierPayload;
  userCredits: number;
  creditsUnlimited?: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  onExportAllAtelier?: (
    items: { search_id: string; credits_required: number }[],
    format: "xlsx" | "csv"
  ) => void;
  exporting: boolean;
}

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

function DossierTldr({
  synthesis,
}: {
  synthesis: BusinessDossierPayload["synthesis"];
}) {
  const n =
    (synthesis.forces?.length ?? 0) +
    (synthesis.risques?.length ?? 0) +
    (synthesis.prochaines_etapes?.length ?? 0);
  if (n === 0) return null;

  const force =
    synthesis.forces?.[0]?.trim() ||
    "À documenter après validation terrain.";
  const risk = synthesis.risques?.[0]?.trim() || "—";
  const action =
    synthesis.prochaines_etapes?.[0]?.trim() ||
    synthesis.kpis?.[0]?.trim() ||
    "Parcourir les segments entreprises ci-dessous.";

  const cards: {
    href: string;
    title: string;
    text: string;
    Icon: LucideIcon;
    ring: string;
  }[] = [
    {
      href: "#atelier-synth-forces",
      title: "Force",
      text: force,
      Icon: Lightbulb,
      ring: "border-emerald-500/25 bg-emerald-500/[0.06]",
    },
    {
      href: "#atelier-synth-risques",
      title: "Risque",
      text: risk,
      Icon: ShieldAlert,
      ring: "border-amber-500/25 bg-amber-500/[0.06]",
    },
    {
      href: "#atelier-section-segments",
      title: "Action",
      text: action,
      Icon: ListChecks,
      ring: "border-sky-500/25 bg-sky-500/[0.06]",
    },
  ];

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-surface-1 p-4 sm:p-5">
      <p className="text-[11px] uppercase tracking-[0.1em] text-gray-500 mb-3">
        Synthèse express
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {cards.map((c) => {
          const Icon = c.Icon;
          return (
            <a
              key={c.title}
              href={c.href}
              className={`rounded-xl border ${c.ring} p-3 block hover:border-white/20 transition-colors group`}
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-gray-300">
                  <Icon size={13} className="text-gray-400" />
                  {c.title}
                </span>
                <ChevronRight
                  size={14}
                  className="text-gray-600 group-hover:text-gray-400 flex-shrink-0"
                  aria-hidden
                />
              </div>
              <p className="text-xs text-gray-400 leading-relaxed line-clamp-4">{c.text}</p>
            </a>
          );
        })}
      </div>
    </div>
  );
}

function DossierRollupExport({
  segments,
  userCredits,
  creditsUnlimited,
  onExportAllAtelier,
  exporting,
}: {
  segments: SegmentResult[];
  userCredits: number;
  creditsUnlimited: boolean;
  onExportAllAtelier?: (
    items: { search_id: string; credits_required: number }[],
    format: "xlsx" | "csv"
  ) => void;
  exporting: boolean;
}) {
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
        {exporting ? "Exports…" : "Exporter tout le dossier (Excel)"}
      </button>
    </div>
  );
}

/**
 * Livrable complet de l'Atelier. Rendu "premium" avec sections expandables,
 * entièrement cohérent avec le design system MONV (dark, arrondis 2xl,
 * accents colorés). Le cœur est la section "Segments" qui réutilise
 * `ResultsTable` — l'utilisateur peut donc exporter chaque tableau comme
 * une recherche classique.
 */
export default function BusinessDossier({
  dossier,
  userCredits,
  creditsUnlimited = false,
  onExport,
  onExportAllAtelier,
  exporting,
}: Props) {
  const meta = AGENT_META.atelier;
  const { brief, canvas, flows, segments, synthesis } = dossier;

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
    <div className="space-y-5 mt-4 animate-fade-in">
      <DossierHeader
        nom={brief.nom}
        tagline={brief.tagline}
        secteur={brief.secteur}
        localisation={brief.localisation}
        cible={brief.cible}
        budget={brief.budget}
        modeleRevenus={brief.modele_revenus}
        ambition={brief.ambition}
        budgetHypotheses={brief.budget_hypotheses}
        budgetMinEur={brief.budget_min_eur ?? null}
        budgetMaxEur={brief.budget_max_eur ?? null}
        totals={totals}
        gradientFrom={meta.gradientFrom}
        gradientTo={meta.gradientTo}
        accentText={meta.accentText}
      />

      <DossierRollupExport
        segments={segments}
        userCredits={userCredits}
        creditsUnlimited={creditsUnlimited}
        onExportAllAtelier={onExportAllAtelier}
        exporting={exporting}
      />

      <DossierTldr synthesis={synthesis} />

      <Section
        icon={Workflow}
        title="Business Model Canvas"
        subtitle="9 blocs stratégiques pour valider la cohérence du projet."
      >
        <BusinessModelCanvas canvas={canvas} />
      </Section>

      <div id="atelier-section-flows">
        <Section
          icon={Route}
          title="Cartographie des flux"
          subtitle="Valeur, cash, information — graphe interactif, acteurs cliquables vers les segments."
        >
          <FlowDiagram flows={flows} segments={segments} />
        </Section>
      </div>

      <div id="atelier-section-segments">
        <SegmentsSection
          segments={segments}
          segmentLabelByKey={segmentLabelByKey}
          userCredits={userCredits}
          creditsUnlimited={creditsUnlimited}
          onExport={onExport}
          exporting={exporting}
        />
      </div>

      <div id="atelier-section-synthesis">
        <SynthesisSection synthesis={synthesis} />
      </div>
    </div>
  );
}

// ── Header du dossier ─────────────────────────────────────────────────────────

function DossierHeader({
  nom,
  tagline,
  secteur,
  localisation,
  cible,
  budget,
  modeleRevenus,
  ambition,
  budgetHypotheses = [],
  budgetMinEur,
  budgetMaxEur,
  totals,
  gradientFrom,
  gradientTo,
  accentText,
}: {
  nom: string;
  tagline: string;
  secteur: string;
  localisation: string;
  cible: string;
  budget: string;
  modeleRevenus: string;
  ambition: string;
  budgetHypotheses?: string[];
  budgetMinEur?: number | null;
  budgetMaxEur?: number | null;
  totals?: { raw: number; unique: number; relevant: number } | null;
  gradientFrom: string;
  gradientTo: string;
  accentText: string;
}) {
  const fmtK = (n: number) =>
    `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(Math.round(n / 1000))}\u202fk€`;

  let budgetValue = budget.trim();
  if (budgetMinEur != null && budgetMaxEur != null && budgetMinEur >= 0 && budgetMaxEur >= 0) {
    budgetValue = `${budgetValue} (${fmtK(budgetMinEur)} – ${fmtK(budgetMaxEur)})`;
  }

  const facts: { icon: LucideIcon; label: string; value: string }[] = [
    { icon: Flag, label: "Secteur", value: secteur },
    { icon: MapPin, label: "Localisation", value: localisation },
    { icon: Users, label: "Cible", value: cible },
    { icon: Coins, label: "Budget lancement", value: budgetValue },
    { icon: Gauge, label: "Modèle de revenus", value: modeleRevenus },
    { icon: Lightbulb, label: "Ambition 2-3 ans", value: ambition },
  ].filter((f) => f.value && f.value.trim().length > 0);

  if (budgetHypotheses.length > 0) {
    facts.push({
      icon: Calculator,
      label: "Hypothèses budget",
      value: budgetHypotheses.join(" · "),
    });
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-surface-1">
      <div
        className={`h-1 w-full bg-gradient-to-r ${gradientFrom} ${gradientTo} opacity-50`}
      />
      <div className="p-5 sm:p-6">
        <div className="flex items-center gap-2 mb-2">
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.1em] border border-white/[0.06] ${accentText}`}
          >
            <Compass size={10} />
            Dossier Atelier
          </span>
        </div>
        <h2 className="text-xl sm:text-2xl font-bold text-white leading-tight">
          {nom}
        </h2>
        {tagline && (
          <p className="text-sm text-gray-400 mt-1 leading-relaxed">{tagline}</p>
        )}

        {facts.length > 0 && (
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {facts.map((f) => {
              const Icon = f.icon;
              return (
                <div
                  key={f.label}
                  className="flex items-start gap-2.5 rounded-lg border border-white/[0.05] bg-surface-2 px-3 py-2.5"
                >
                  <Icon size={13} className="text-gray-500 mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[11px] uppercase tracking-[0.1em] text-gray-500">
                      {f.label}
                    </p>
                    <p className="text-xs text-gray-200 leading-snug mt-0.5">
                      {f.value}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
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

// ── Section générique avec icône / titre / contenu ──────────────────────────

function Section({
  icon: Icon,
  title,
  subtitle,
  children,
}: {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-start gap-3 mb-3 px-1">
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-gray-300">
          <Icon size={15} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          {subtitle && (
            <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      {children}
    </section>
  );
}

// ── Segments — chaque segment = un tableau d'entreprises MONV ────────────────

function SegmentsSection({
  segments,
  segmentLabelByKey,
  userCredits,
  creditsUnlimited,
  onExport,
  exporting,
}: {
  segments: SegmentResult[];
  segmentLabelByKey: Record<string, string>;
  userCredits: number;
  creditsUnlimited: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
}) {
  if (segments.length === 0) return null;

  return (
    <Section
      icon={Target}
      title="Entreprises réelles à activer"
      subtitle="Tableaux générés via le pipeline MONV — chaque liste est exportable."
    >
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
          />
        ))}
      </div>
    </Section>
  );
}

function SegmentBlock({
  segment,
  segmentLabelByKey,
  userCredits,
  creditsUnlimited,
  onExport,
  exporting,
}: {
  segment: SegmentResult;
  segmentLabelByKey: Record<string, string>;
  userCredits: number;
  creditsUnlimited: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  const Icon = SEGMENT_ICONS[segment.icon] || Building;
  const mode: Mode = normalizeMode(segment.mode);
  const modeMeta = MODE_META[mode];

  const isOutOfScope = Boolean(segment.out_of_scope);
  const hasResults = !segment.error && segment.total > 0;

  return (
    <div
      id={`atelier-segment-${segment.key}`}
      className="rounded-2xl border border-white/[0.06] bg-surface-1 overflow-hidden scroll-mt-24"
    >
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors text-left"
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
        <div className="flex-shrink-0 text-gray-500">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

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
            // Preview disponible mais pas d'ID d'export (échec search_history_insert)
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

// ── Synthèse : forces / risques / étapes / KPIs ─────────────────────────────

function SynthesisSection({ synthesis }: { synthesis: BusinessDossierPayload["synthesis"] }) {
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
    <Section
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
    </Section>
  );
}
