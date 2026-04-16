"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Briefcase,
  Building,
  Calculator,
  ChevronDown,
  ChevronUp,
  Coins,
  Compass,
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
  exporting,
}: Props) {
  const meta = AGENT_META.atelier;
  const { brief, canvas, flows, segments, synthesis } = dossier;

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
        gradientFrom={meta.gradientFrom}
        gradientTo={meta.gradientTo}
        accentText={meta.accentText}
      />

      <Section
        icon={Workflow}
        title="Business Model Canvas"
        subtitle="9 blocs stratégiques pour valider la cohérence du projet."
      >
        <BusinessModelCanvas canvas={canvas} />
      </Section>

      <Section
        icon={Route}
        title="Cartographie des flux"
        subtitle="Flux de valeur, financiers et d'information entre les acteurs."
      >
        <FlowDiagram flows={flows} />
      </Section>

      <SegmentsSection
        segments={segments}
        userCredits={userCredits}
        creditsUnlimited={creditsUnlimited}
        onExport={onExport}
        exporting={exporting}
      />

      <SynthesisSection synthesis={synthesis} />
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
  gradientFrom: string;
  gradientTo: string;
  accentText: string;
}) {
  const facts: { icon: LucideIcon; label: string; value: string }[] = [
    { icon: Flag, label: "Secteur", value: secteur },
    { icon: MapPin, label: "Localisation", value: localisation },
    { icon: Users, label: "Cible", value: cible },
    { icon: Coins, label: "Budget lancement", value: budget },
    { icon: Gauge, label: "Modèle de revenus", value: modeleRevenus },
    { icon: Lightbulb, label: "Ambition 2-3 ans", value: ambition },
  ].filter((f) => f.value && f.value.trim().length > 0);

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
  userCredits,
  creditsUnlimited,
  onExport,
  exporting,
}: {
  segments: SegmentResult[];
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
  userCredits,
  creditsUnlimited,
  onExport,
  exporting,
}: {
  segment: SegmentResult;
  userCredits: number;
  creditsUnlimited: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  const Icon = SEGMENT_ICONS[segment.icon] || Building;
  const mode: Mode = normalizeMode(segment.mode);
  const modeMeta = MODE_META[mode];

  const hasResults = !segment.error && segment.total > 0;

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-surface-1 overflow-hidden">
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
            {hasResults ? (
              <span className="text-[11px] tabular-nums text-gray-500">
                {segment.total} résultat{segment.total > 1 ? "s" : ""}
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
          {segment.error ? (
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
  }[] = [
    {
      icon: Lightbulb,
      title: "Forces du projet",
      items: synthesis.forces,
      accent: "border-emerald-500/20 bg-emerald-500/5",
    },
    {
      icon: ShieldAlert,
      title: "Risques à surveiller",
      items: synthesis.risques,
      accent: "border-amber-500/20 bg-amber-500/5",
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
      accent: "border-fuchsia-500/20 bg-fuchsia-500/5",
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
            <div key={b.title} className={`rounded-xl border ${b.accent} p-4`}>
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
