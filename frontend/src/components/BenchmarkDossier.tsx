"use client";

import { useState, useMemo, useCallback } from "react";
import { apiPost } from "@/lib/api";
import {
  BarChart3, RefreshCw, Share2, Download, X,
  MapPin, Building2, TrendingUp, Database,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  CartesianGrid,
} from "recharts";

interface GuardEntities {
  secteur?: string | null;
  code_naf?: string | null;
  localisation?: string | null;
  departement?: string | null;
  region?: string | null;
}

interface BenchmarkDossierProps {
  data: Record<string, any>[];
  columns: string[];
  total: number;
  searchId: string;
  creditsRequired: number;
  userCredits: number;
  creditsUnlimited?: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
  mapPoints?: Record<string, any>[];
  query?: string;
  guardEntities?: GuardEntities;
}

const TABS = [
  { id: "panorama", label: "Panorama" },
  { id: "finance", label: "Finance" },
  { id: "dynamique", label: "Dynamique" },
  { id: "carto", label: "Cartographie" },
  { id: "classements", label: "Classements" },
  { id: "tableau", label: "Tableau détaillé" },
  { id: "insights", label: "Insights IA" },
] as const;

// ── Helpers ────────────────────────────────────────────────────

function buildTitle(guardEntities?: GuardEntities, query?: string): string {
  const secteur = guardEntities?.secteur;
  const zone =
    guardEntities?.localisation ||
    guardEntities?.departement ||
    guardEntities?.region ||
    null;
  const zoneLabel = zone
    ? zone.charAt(0).toUpperCase() + zone.slice(1).toLowerCase()
    : null;
  if (secteur && zoneLabel)
    return `${secteur.charAt(0).toUpperCase() + secteur.slice(1)} — panorama ${zoneLabel}`;
  if (secteur)
    return `Panorama — ${secteur.charAt(0).toUpperCase() + secteur.slice(1)}`;
  if (query) return query.charAt(0).toUpperCase() + query.slice(1);
  return "Panorama sectoriel";
}

function buildBadges(guardEntities?: GuardEntities, total?: number): string[] {
  const badges: string[] = [];
  if (guardEntities?.code_naf) badges.push(`NAF ${guardEntities.code_naf}`);
  const zone =
    guardEntities?.localisation ||
    guardEntities?.departement ||
    guardEntities?.region;
  if (zone) badges.push(zone.toUpperCase());
  else badges.push("FRANCE ENTIÈRE");
  if (total) badges.push(`PANEL ${total}`);
  return badges;
}

// Sources détectées selon les colonnes disponibles
function detectSources(columns: string[]): string[] {
  const sources: string[] = [];
  sources.push("SIRENE"); // toujours présent
  const pappersFields = [
    "chiffre_affaires", "resultat_net", "ebe",
    "capitaux_propres", "variation_ca_pct",
  ];
  if (columns.some((c) => pappersFields.includes(c))) sources.push("Pappers");
  if (columns.some((c) => c === "google_maps_url" || c === "latitude"))
    sources.push("Google Places");
  return sources;
}

// Médiane d'un tableau de nombres
function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

// Formatage compact des montants
function fmtEur(val: number | null): string {
  if (val === null) return "—";
  if (Math.abs(val) >= 1_000_000_000)
    return `${(val / 1_000_000_000).toFixed(1)} Md€`;
  if (Math.abs(val) >= 1_000_000)
    return `${(val / 1_000_000).toFixed(1)} M€`;
  if (Math.abs(val) >= 1_000)
    return `${(val / 1_000).toFixed(0)} k€`;
  return `${val} €`;
}

function fmtPct(val: number | null): string {
  if (val === null) return "—";
  return `${val >= 0 ? "+" : ""}${val.toFixed(1)} %`;
}

// Calcul des 6 KPI depuis la liste filtrée
function computeKpis(rows: Record<string, any>[]) {
  const n = rows.length;

  // CA cumulé + variation médiane
  const caValues = rows
    .map((r) => Number(r.chiffre_affaires))
    .filter((v) => !isNaN(v) && v > 0);
  const caCumul = caValues.reduce((s, v) => s + v, 0);

  const caMedianVal = median(caValues);

  const varValues = rows
    .map((r) => Number(r.variation_ca_pct))
    .filter((v) => !isNaN(v));
  const croissanceMediane = median(varValues);

  // Effectif cumulé
  const effValues = rows
    .map((r) => {
      // Préfère effectif_financier si dispo, sinon tente la tranche médiane
      if (r.effectif_financier != null) return Number(r.effectif_financier);
      return null;
    })
    .filter((v): v is number => v !== null && !isNaN(v));
  const effCumul = effValues.length
    ? effValues.reduce((s, v) => s + v, 0)
    : null;

  // Signal transmission : dirigeants sans date connue ou société ancienne
  // On approxime : entreprises créées avant 1990 (âge > ~35 ans)
  const transmissionCount = rows.filter((r) => {
    if (!r.date_creation) return false;
    const year = new Date(r.date_creation).getFullYear();
    return year <= 1990;
  }).length;
  const transmissionPct = n > 0
    ? Math.round((transmissionCount / n) * 100)
    : null;

  return {
    panelCount: n,
    caCumul: caValues.length ? caCumul : null,
    caMedian: caMedianVal,
    effCumul,
    croissanceMediane,
    transmissionPct,
    // Couverture données
    coverageCa: n > 0 ? Math.round((caValues.length / n) * 100) : 0,
    coverageVar: n > 0 ? Math.round((varValues.length / n) * 100) : 0,
  };
}

// Histogramme CA — découpe en tranches
function buildCaHistogram(rows: Record<string, any>[]) {
  const tranches = [
    { label: "< 100k€", min: 0, max: 100_000 },
    { label: "100–300k€", min: 100_000, max: 300_000 },
    { label: "300k–1M€", min: 300_000, max: 1_000_000 },
    { label: "1–5M€", min: 1_000_000, max: 5_000_000 },
    { label: "5–20M€", min: 5_000_000, max: 20_000_000 },
    { label: "> 20M€", min: 20_000_000, max: Infinity },
  ];
  return tranches.map((t) => ({
    label: t.label,
    count: rows.filter((r) => {
      const ca = Number(r.chiffre_affaires);
      return !isNaN(ca) && ca >= t.min && ca < t.max;
    }).length,
  }));
}

// Donut répartition taille
function buildSizeDonut(rows: Record<string, any>[]) {
  const tpe = rows.filter((r) => {
    const e = Number(r.effectif_financier);
    return !isNaN(e) && e >= 0 && e <= 9;
  }).length;
  const pme = rows.filter((r) => {
    const e = Number(r.effectif_financier);
    return !isNaN(e) && e >= 10 && e <= 249;
  }).length;
  const eti = rows.filter((r) => {
    const e = Number(r.effectif_financier);
    return !isNaN(e) && e >= 250;
  }).length;
  return [
    { name: "TPE (0–9)", value: tpe, color: "#f59e0b" },
    { name: "PME (10–249)", value: pme, color: "#d97706" },
    { name: "ETI/GE (250+)", value: eti, color: "#92400e" },
  ].filter((d) => d.value > 0);
}

// Histogramme créations par décennie
function buildCreationHistogram(rows: Record<string, any>[]) {
  const byDecade: Record<string, number> = {};
  rows.forEach((r) => {
    if (!r.date_creation) return;
    const year = new Date(r.date_creation).getFullYear();
    const decade = `${Math.floor(year / 10) * 10}`;
    byDecade[decade] = (byDecade[decade] || 0) + 1;
  });
  return Object.entries(byDecade)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([decade, count]) => ({ label: `${decade}s`, count }));
}

// Radar KPI panel (normalisé sur 100)
function buildRadarData(kpis: ReturnType<typeof computeKpis>, total: number) {
  return [
    {
      subject: "CA",
      value: kpis.coverageCa,
      fullMark: 100,
    },
    {
      subject: "Variation",
      value: kpis.coverageVar,
      fullMark: 100,
    },
    {
      subject: "Transmission",
      value: kpis.transmissionPct ?? 0,
      fullMark: 100,
    },
    {
      subject: "Panel",
      value:
        total > 0
          ? Math.min(100, Math.round((kpis.panelCount / total) * 100 * 10))
          : 0,
      fullMark: 100,
    },
  ];
}

interface TooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{
    name?: string;
    value?: number | string;
    color?: string;
    fill?: string;
    dataKey?: string | number;
  }>;
  label?: string | number;
  formatter?: (value: number, name: string) => string;
}

function ChartTooltip({ active, payload, label, formatter }: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-lg border border-white/[0.08] bg-[#0f0f14] px-3 py-2 shadow-xl">
      {label != null && String(label) !== "" && (
        <p className="text-[11px] text-gray-500 mb-1.5 font-medium">{String(label)}</p>
      )}
      {payload.map((entry, i) => {
        const num =
          typeof entry.value === "number"
            ? entry.value
            : Number(entry.value);
        const name = String(entry.name ?? entry.dataKey ?? "");
        const color = entry.color ?? entry.fill ?? "#fbbf24";
        return (
          <div key={i} className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ background: color }}
            />
            <span className="text-[12px] font-semibold text-white">
              {formatter && Number.isFinite(num)
                ? formatter(num, name)
                : String(entry.value ?? "")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Composant principal ────────────────────────────────────────

export default function BenchmarkDossier({
  data,
  columns,
  total,
  searchId,
  creditsRequired,
  userCredits,
  creditsUnlimited = false,
  onExport,
  exporting,
  mapPoints,
  query,
  guardEntities,
}: BenchmarkDossierProps) {
  const [dismissed, setDismissed] = useState(false);
  const [filterEffectif, setFilterEffectif] = useState<string>("tous");
  const [filterCa, setFilterCa] = useState<string>("tous");
  const [filterRegion, setFilterRegion] = useState<string>("tous");
  const [activeTab, setActiveTab] = useState<string>("panorama");
  const [insights, setInsights] = useState<
    Array<{ n: number; text: string; source: string }>
  >([]);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [insightsGenerated, setInsightsGenerated] = useState(false);

  const [bodaccStats, setBodaccStats] = useState<{
    total_immatriculations: number;
    total_radiations: number;
    total_procol: number;
    total_ventes: number;
    timeline: Array<{
      month: string;
      immatriculations: number;
      radiations: number;
      procol: number;
      ventes: number;
    }>;
    region?: string | null;
  } | null>(null);
  const [bodaccLoading, setBodaccLoading] = useState(false);

  const filteredData = useMemo(() => {
    let rows = data;

    if (filterEffectif !== "tous") {
      const ranges: Record<string, [number, number]> = {
        tpe: [0, 9],
        pme: [10, 249],
        eti: [250, 4999],
        ge: [5000, Infinity],
      };
      const [min, max] = ranges[filterEffectif] || [0, Infinity];
      rows = rows.filter((r) => {
        const eff = Number(r.effectif_financier);
        if (isNaN(eff)) return false;
        return eff >= min && eff <= max;
      });
    }

    if (filterCa !== "tous") {
      const ranges: Record<string, [number, number]> = {
        petit: [0, 300_000],
        moyen: [300_001, 2_000_000],
        grand: [2_000_001, 50_000_000],
        tresGrand: [50_000_001, Infinity],
      };
      const [min, max] = ranges[filterCa] || [0, Infinity];
      rows = rows.filter((r) => {
        const ca = Number(r.chiffre_affaires);
        if (isNaN(ca)) return false;
        return ca >= min && ca <= max;
      });
    }

    if (filterRegion !== "tous") {
      rows = rows.filter(
        (r) =>
          (r.region || "").toLowerCase() ===
          filterRegion.toLowerCase()
      );
    }

    return rows;
  }, [data, filterEffectif, filterCa, filterRegion]);

  const availableRegions = useMemo(() => {
    const regions = new Set<string>();
    data.forEach((r) => { if (r.region) regions.add(r.region); });
    return Array.from(regions).sort();
  }, [data]);

  const kpis = useMemo(() => computeKpis(filteredData), [filteredData]);

  const generateInsights = useCallback(async () => {
    if (insightsGenerated || insightsLoading) return;
    setInsightsLoading(true);
    setInsightsError(null);

    try {
      const panelSummary = {
        total: kpis.panelCount,
        secteur: guardEntities?.secteur || query || "secteur inconnu",
        zone:
          guardEntities?.localisation ||
          guardEntities?.region ||
          "France",
        ca_median: kpis.caMedian,
        croissance_mediane: kpis.croissanceMediane,
        coverage_ca: kpis.coverageCa,
        transmission_pct: kpis.transmissionPct,
        top3_regions: (() => {
          const counts: Record<string, number> = {};
          filteredData.forEach((r) => {
            if (r.region) counts[r.region] = (counts[r.region] || 0) + 1;
          });
          return Object.entries(counts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
            .map(([r, n]) => `${r} (${n})`);
        })(),
        repartition_taille: (() => {
          const tpe = filteredData.filter(
            (r) => Number(r.effectif_financier) <= 9,
          ).length;
          const pme = filteredData.filter((r) => {
            const e = Number(r.effectif_financier);
            return e >= 10 && e <= 249;
          }).length;
          return { tpe, pme };
        })(),
      };

      const data = await apiPost<{ insights: Array<{ n: number; text: string; source: string }> }>(
        "/chat/benchmark-insights",
        { panel_summary: panelSummary },
      );
      setInsights(data.insights || []);
      setInsightsGenerated(true);
    } catch {
      setInsightsError("Impossible de générer les insights. Réessaie.");
    } finally {
      setInsightsLoading(false);
    }
  }, [
    filteredData,
    guardEntities?.localisation,
    guardEntities?.region,
    guardEntities?.secteur,
    insightsGenerated,
    insightsLoading,
    kpis.caMedian,
    kpis.coverageCa,
    kpis.croissanceMediane,
    kpis.panelCount,
    kpis.transmissionPct,
    query,
  ]);

  const loadBodaccStats = useCallback(async () => {
    if (bodaccStats || bodaccLoading) return;
    setBodaccLoading(true);
    try {
      const data = await apiPost<{
        total_immatriculations: number;
        total_radiations: number;
        total_procol: number;
        total_ventes: number;
        timeline: Array<{
          month: string;
          immatriculations: number;
          radiations: number;
          procol: number;
          ventes: number;
        }>;
        region?: string | null;
      }>("/chat/benchmark-bodacc-stats", {
        region: guardEntities?.region || null,
        departement: null,
        days_back: 365,
      });
      setBodaccStats(data);
    } catch {
      /* silencieux */
    } finally {
      setBodaccLoading(false);
    }
  }, [bodaccStats, bodaccLoading, guardEntities?.region]);

  const canExport = creditsUnlimited || userCredits >= creditsRequired;

  if (dismissed) return null;

  const title = buildTitle(guardEntities, query);
  const sources = detectSources(columns);
  const now = new Date().toLocaleDateString("fr-FR", {
    day: "numeric", month: "short", year: "numeric",
  });

  return (
    <div className="dark mt-3 rounded-xl border border-amber-500/20 bg-surface-1 overflow-hidden animate-fade-in">

      {/* ── Zone 1 : Barre actions ── */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/[0.04]">
        <div className="flex items-center gap-1.5 text-[11px] text-gray-600">
          <span>MONV</span>
          <span>/</span>
          <span>Études sectorielles</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            title="Rafraîchir"
            className="p-1.5 rounded-md text-gray-600 hover:text-gray-300 hover:bg-white/[0.04] transition-colors"
          >
            <RefreshCw size={12} />
          </button>
          <button
            type="button"
            title="Partager"
            className="p-1.5 rounded-md text-gray-600 hover:text-gray-300 hover:bg-white/[0.04] transition-colors"
          >
            <Share2 size={12} />
          </button>
          <button
            type="button"
            onClick={() => onExport(searchId, "xlsx")}
            disabled={exporting || !canExport}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-white/[0.08] text-gray-300 text-[11px] font-medium hover:bg-white/[0.12] disabled:opacity-40 transition-colors"
          >
            <Download size={11} />
            XLSX
          </button>
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className="p-1.5 rounded-md text-gray-600 hover:text-gray-300 hover:bg-white/[0.04] transition-colors ml-1"
          >
            <X size={12} />
          </button>
        </div>
      </div>

      {/* ── Zone 2 : Hero ── */}
      <div className="px-5 pt-5 pb-4 border-b border-white/[0.04]">
        <div className="flex items-start gap-3 mb-3">
          <div className="p-2 rounded-lg bg-amber-500/15 flex-shrink-0 mt-0.5">
            <BarChart3 size={16} className="text-amber-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white leading-tight">
              {title}
            </h2>
            <div className="flex flex-wrap items-center gap-2 mt-1">
              {guardEntities?.code_naf && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded border border-amber-500/25 bg-amber-500/10 text-[10px] font-medium text-amber-400">
                  NAF {guardEntities.code_naf}
                </span>
              )}
              {(guardEntities?.localisation || guardEntities?.region) && (
                <span className="text-sm text-gray-400">
                  {guardEntities.localisation || guardEntities.region}
                </span>
              )}
              <span className="text-gray-700">·</span>
              <span className="text-sm text-gray-400">
                {total.toLocaleString("fr-FR")} entreprises
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {sources.map((s) => (
            <span key={s} className="inline-flex items-center gap-1 text-[11px] text-gray-600">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
              {s}
            </span>
          ))}
          <span className="text-gray-700">·</span>
          <span className="text-[11px] text-gray-600">{now}</span>
        </div>
      </div>

      {/* ── Zone 3 : Filtres ── */}
      <div className="flex flex-wrap items-center gap-2 px-5 py-3 border-b border-white/[0.04] bg-white/[0.01]">
        <span className="text-[11px] text-gray-600 mr-1">Filtrer :</span>

        <select
          value={filterEffectif}
          onChange={(e) => setFilterEffectif(e.target.value)}
          className={`rounded-lg px-2.5 py-1.5 text-[12px] border transition-colors cursor-pointer focus:outline-none ${
            filterEffectif !== "tous"
              ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
              : "bg-white/[0.04] border-white/[0.08] text-gray-400 hover:border-white/[0.16] hover:text-gray-300"
          }`}
        >
          <option value="tous">Effectif · tous</option>
          <option value="tpe">TPE (0–9)</option>
          <option value="pme">PME (10–249)</option>
          <option value="eti">ETI (250+)</option>
        </select>

        <select
          value={filterCa}
          onChange={(e) => setFilterCa(e.target.value)}
          className={`rounded-lg px-2.5 py-1.5 text-[12px] border transition-colors cursor-pointer focus:outline-none ${
            filterCa !== "tous"
              ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
              : "bg-white/[0.04] border-white/[0.08] text-gray-400 hover:border-white/[0.16] hover:text-gray-300"
          }`}
        >
          <option value="tous">CA · tous</option>
          <option value="petit">{"< 300 k€"}</option>
          <option value="moyen">300 k€ – 2 M€</option>
          <option value="grand">2 M€ – 50 M€</option>
          <option value="tresGrand">{"> 50 M€"}</option>
        </select>

        {availableRegions.length > 1 && (
          <select
            value={filterRegion}
            onChange={(e) => setFilterRegion(e.target.value)}
            className={`rounded-lg px-2.5 py-1.5 text-[12px] border transition-colors cursor-pointer focus:outline-none ${
              filterRegion !== "tous"
                ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                : "bg-white/[0.04] border-white/[0.08] text-gray-400 hover:border-white/[0.16] hover:text-gray-300"
            }`}
          >
            <option value="tous">Région · toutes</option>
            {availableRegions.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        )}

        {(filterEffectif !== "tous" || filterCa !== "tous" || filterRegion !== "tous") && (
          <button
            type="button"
            onClick={() => {
              setFilterEffectif("tous");
              setFilterCa("tous");
              setFilterRegion("tous");
            }}
            className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg text-[11px] text-amber-400 hover:text-amber-300 transition-colors"
          >
            <X size={10} />
            Réinitialiser
          </button>
        )}

        <span className="ml-auto text-[11px] text-gray-600">
          {filteredData.length !== total && (
            <>{filteredData.length} / </>
          )}
          {total.toLocaleString("fr-FR")} entreprises
        </span>
      </div>

      {/* ── Zone 4 : KPI bande horizontale ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-white/[0.04] border-b border-white/[0.04]">
        {[
          {
            label: "Panel",
            value: total.toLocaleString("fr-FR"),
            sub: "entreprises trouvées",
          },
          {
            label: "CA cumulé",
            value: fmtEur(kpis.caCumul),
            sub: kpis.coverageCa > 0
              ? `${kpis.coverageCa} % avec CA connu`
              : "données non disponibles",
          },
          {
            label: "CA médian",
            value: fmtEur(kpis.caMedian),
            sub: "médiane du panel",
          },
          {
            label: "Transmission",
            value: kpis.transmissionPct !== null
              ? `${kpis.transmissionPct} %`
              : "—",
            sub: "créées avant 1990",
            highlight: kpis.transmissionPct !== null && kpis.transmissionPct > 25,
          },
        ].map((kpi) => (
          <div key={kpi.label} className="px-5 py-3 flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-wider text-gray-600 font-medium">
              {kpi.label}
            </span>
            <span className={`text-2xl font-bold tabular-nums leading-tight ${
              "highlight" in kpi && kpi.highlight ? "text-amber-300" : "text-white"
            }`}>
              {kpi.value}
            </span>
            <span className="text-[11px] text-gray-600 leading-tight">
              {kpi.sub}
            </span>
          </div>
        ))}
      </div>

      {/* ── Barre d'onglets ──────────────────────────────── */}
      <div className="border-b border-white/[0.04] overflow-x-auto scrollbar-thin">
        <div className="flex min-w-max px-4">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-amber-400 text-amber-300"
                  : "border-transparent text-gray-500 hover:text-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Contenu onglets ──────────────────────────────── */}
      <div className="min-h-[320px]">

        {/* PANORAMA */}
        {activeTab === "panorama" && (
          <div className="p-4 space-y-4">
            {/* Synthèse exécutive — inchangée */}
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-white">Synthèse exécutive</h3>
                <span className="text-[10px] text-gray-600 uppercase tracking-wider">· générée MONV</span>
              </div>
              <p className="text-sm text-gray-400 leading-relaxed">
                Panel de <strong className="text-white">{kpis.panelCount}</strong> entreprises.
                {kpis.caMedian !== null && (<> CA médian estimé à <strong className="text-white">{fmtEur(kpis.caMedian)}</strong>.</>)}
                {kpis.croissanceMediane !== null && (<> Croissance médiane <strong className={kpis.croissanceMediane >= 0 ? "text-emerald-400" : "text-amber-400"}>{fmtPct(kpis.croissanceMediane)}</strong>.</>)}
                {kpis.transmissionPct !== null && kpis.transmissionPct > 20 && (<> Signal transmission notable : <strong className="text-amber-300">{kpis.transmissionPct} %</strong> des sociétés créées avant 1990.</>)}
              </p>
            </div>

            {/* Ligne 1 : Histogramme CA + Donut taille */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

              {/* Histogramme CA */}
              <div className="rounded-lg bg-white/[0.02] p-4">
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                  Distribution CA
                </h3>
                {(() => {
                  const hist = buildCaHistogram(filteredData);
                  const hasData = hist.some((h) => h.count > 0);
                  if (!hasData) return (
                    <p className="text-xs text-gray-600 py-4 text-center">
                      Données CA non disponibles pour ce panel.
                    </p>
                  );
                  return (
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart
                        data={hist}
                        margin={{ top: 8, right: 8, left: -16, bottom: 8 }}
                        barCategoryGap="20%"
                      >
                        <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                        <XAxis
                          dataKey="label"
                          tick={{ fill: "#4b5563", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: "#4b5563", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                          allowDecimals={false}
                        />
                        <Tooltip
                          content={(props) => (
                            <ChartTooltip
                              active={props.active}
                              payload={props.payload as TooltipProps["payload"]}
                              label={props.label}
                              formatter={(v) =>
                                `${v} entreprise${v > 1 ? "s" : ""}`
                              }
                            />
                          )}
                          cursor={{ fill: "rgba(255,255,255,0.03)" }}
                        />
                        <Bar dataKey="count" fill="#fbbf24" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  );
                })()}
              </div>

              {/* Donut répartition taille */}
              <div className="rounded-lg bg-white/[0.02] p-4">
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                  Répartition par taille
                </h3>
                {(() => {
                  const donutData = buildSizeDonut(filteredData);
                  if (donutData.length === 0) return (
                    <p className="text-xs text-gray-600 py-4 text-center">
                      Données d&apos;effectif non disponibles.
                    </p>
                  );
                  return (
                    <div className="flex flex-col items-center">
                      <ResponsiveContainer width="100%" height={140}>
                        <PieChart>
                          <Pie
                            data={donutData}
                            cx="50%"
                            cy="50%"
                            innerRadius={38}
                            outerRadius={56}
                            paddingAngle={3}
                            dataKey="value"
                            strokeWidth={0}
                          >
                            {donutData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip
                            content={(props) => (
                              <ChartTooltip
                                active={props.active}
                                payload={props.payload as TooltipProps["payload"]}
                                label={props.label}
                                formatter={(v, name) => `${v} (${name})`}
                              />
                            )}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="flex w-full flex-wrap items-center justify-center gap-x-4 gap-y-1 mt-2 text-center">
                        {donutData.map((d) => (
                          <div key={d.name} className="flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                            <span className="text-[11px] text-gray-500">{d.name}</span>
                            <span className="text-[11px] font-medium text-gray-300 tabular-nums">{d.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Ligne 2 : Radar qualité panel + Histogramme créations */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

              {/* Radar qualité du dossier */}
              <div className="rounded-lg bg-white/[0.02] p-4">
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                  Qualité du dossier
                </h3>
                {(() => {
                  const radarData = buildRadarData(kpis, total);
                  const radarHasData = radarData.some((d) => d.value > 10);
                  if (!radarHasData) {
                    return (
                      <div className="flex flex-col items-center justify-center h-[200px] gap-2">
                        <p className="text-xs text-gray-600 text-center">
                          Données insuffisantes pour le radar.
                        </p>
                        <div className="space-y-2 w-full max-w-[200px]">
                          {radarData.map((d) => (
                            <div key={d.subject} className="flex items-center justify-between gap-2">
                              <span className="text-[11px] text-gray-500">{d.subject}</span>
                              <span className="text-[11px] font-medium text-white tabular-nums">
                                {d.value} %
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  }
                  return (
                    <ResponsiveContainer width="100%" height={240}>
                      <RadarChart
                        data={radarData}
                        margin={{ top: 24, right: 40, left: 40, bottom: 24 }}
                      >
                        <PolarGrid
                          stroke="rgba(255,255,255,0.06)"
                          gridType="polygon"
                        />
                        <PolarAngleAxis
                          dataKey="subject"
                          tick={{ fill: "#6b7280", fontSize: 11 }}
                          tickLine={false}
                        />
                        <Radar
                          name="Panel"
                          dataKey="value"
                          stroke="#fbbf24"
                          strokeWidth={1.5}
                          fill="#fbbf24"
                          fillOpacity={0.12}
                        />
                        <Tooltip
                          content={(props) => (
                            <ChartTooltip
                              active={props.active}
                              payload={props.payload as TooltipProps["payload"]}
                              label={props.label}
                              formatter={(v) => `${v} %`}
                            />
                          )}
                        />
                      </RadarChart>
                    </ResponsiveContainer>
                  );
                })()}
              </div>

              {/* Histogramme créations par décennie */}
              <div className="rounded-lg bg-white/[0.02] p-4">
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                  Créations par décennie
                </h3>
                {(() => {
                  const hist = buildCreationHistogram(filteredData);
                  if (hist.length === 0) return (
                    <p className="text-xs text-gray-600 py-4 text-center">
                      Dates de création non disponibles.
                    </p>
                  );
                  return (
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart
                        data={hist}
                        margin={{ top: 8, right: 8, left: -16, bottom: 8 }}
                        barCategoryGap="25%"
                      >
                        <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                        <XAxis
                          dataKey="label"
                          tick={{ fill: "#4b5563", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: "#4b5563", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                          allowDecimals={false}
                        />
                        <Tooltip
                          content={(props) => (
                            <ChartTooltip
                              active={props.active}
                              payload={props.payload as TooltipProps["payload"]}
                              label={props.label}
                              formatter={(v) =>
                                `${v} entreprise${v > 1 ? "s" : ""}`
                              }
                            />
                          )}
                          cursor={{ fill: "rgba(255,255,255,0.03)" }}
                        />
                        <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                          {hist.map((entry, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={entry.label >= "2010s" ? "#fbbf24" : "#78350f"}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  );
                })()}
              </div>
            </div>
          </div>
        )}

        {/* FINANCE */}
        {activeTab === "finance" && (
          <div className="p-4">
            <div className="space-y-4">
              {/* Indicateurs financiers — inchangés */}
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
                <h3 className="text-sm font-medium text-white mb-3">
                  Indicateurs financiers du panel
                </h3>
                {(() => {
                  const caVals = filteredData
                    .map((r) => Number(r.chiffre_affaires))
                    .filter((v) => !isNaN(v) && v > 0)
                    .sort((a, b) => a - b);
                  const rnVals = filteredData
                    .map((r) => Number(r.resultat_net))
                    .filter((v) => !isNaN(v));
                  const ebeVals = filteredData
                    .map((r) => Number(r.ebe))
                    .filter((v) => !isNaN(v) && v > 0);
                  if (caVals.length === 0) return (
                    <p className="text-sm text-gray-600">
                      Aucune donnée financière disponible. Activez l&apos;enrichissement Pappers.
                    </p>
                  );
                  const q1 = caVals[Math.floor(caVals.length * 0.25)] ?? null;
                  const q3 = caVals[Math.floor(caVals.length * 0.75)] ?? null;
                  return (
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { label: "CA médian", value: fmtEur(median(caVals)) },
                        { label: "CA Q1", value: fmtEur(q1) },
                        { label: "CA Q3", value: fmtEur(q3) },
                        { label: "Résultat net médian", value: fmtEur(median(rnVals)) },
                        { label: "EBE médian", value: fmtEur(median(ebeVals)) },
                        { label: "Entreprises avec CA", value: `${caVals.length} / ${filteredData.length}` },
                      ].map(({ label, value }) => (
                        <div key={label} className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-3">
                          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{label}</p>
                          <p className="text-lg font-bold text-white tabular-nums">{value}</p>
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>

              {/* Scatter CA / Variation */}
              {(() => {
                const scatterData = filteredData
                  .filter((r) => r.chiffre_affaires != null && r.variation_ca_pct != null)
                  .map((r) => ({
                    name: r.nom,
                    ca: Math.round(Number(r.chiffre_affaires) / 1000),
                    variation: Number(r.variation_ca_pct),
                  }));
                if (scatterData.length < 3) return null;
                const financeSlice = scatterData.slice(0, 15);
                return (
                  <div className="rounded-lg bg-white/[0.02] p-4">
                    <h3 className="text-sm font-medium text-white mb-1">CA vs Croissance</h3>
                    <p className="text-[10px] text-gray-600 mb-3">CA en k€ / Variation CA en %</p>
                    <ResponsiveContainer width="100%" height={240}>
                      <BarChart
                        data={financeSlice}
                        margin={{ top: 8, right: 8, left: -16, bottom: 60 }}
                        barCategoryGap="20%"
                      >
                        <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                        <XAxis
                          dataKey="name"
                          tick={{ fill: "#4b5563", fontSize: 10 }}
                          angle={-40}
                          textAnchor="end"
                          axisLine={false}
                          tickLine={false}
                          interval={0}
                        />
                        <YAxis
                          tick={{ fill: "#4b5563", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          content={(props) => (
                            <ChartTooltip
                              active={props.active}
                              payload={props.payload as TooltipProps["payload"]}
                              label={props.label}
                              formatter={(v, name) =>
                                name === "ca"
                                  ? `${v} k€`
                                  : `${v > 0 ? "+" : ""}${v} %`
                              }
                            />
                          )}
                          cursor={{ fill: "rgba(255,255,255,0.03)" }}
                        />
                        <Bar dataKey="ca" name="ca" fill="#fbbf24" radius={[3, 3, 0, 0]} />
                        <Bar
                          dataKey="variation"
                          name="variation"
                          radius={[3, 3, 0, 0]}
                        >
                          {financeSlice.map((entry, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={entry.variation >= 0 ? "#34d399" : "#f87171"}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                    <div className="flex flex-wrap items-center gap-4 mt-2">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-amber-400" />
                        <span className="text-[11px] text-gray-500">CA (k€)</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-400" />
                        <span className="text-[11px] text-gray-500">Croissance positive</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-red-400" />
                        <span className="text-[11px] text-gray-500">Croissance négative</span>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        )}

        {/* DYNAMIQUE */}
        {activeTab === "dynamique" && (
          <div className="p-4 space-y-4">
            {/* Chargement auto des stats BODACC */}
            {!bodaccStats && !bodaccLoading && (
              <div className="rounded-lg bg-white/[0.02] p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Dynamique du marché
                  </h3>
                  <button
                    type="button"
                    onClick={loadBodaccStats}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-300 text-xs font-medium hover:bg-amber-500/25 transition-colors"
                  >
                    ✦ Charger les données BODACC
                  </button>
                </div>
                <p className="text-xs text-gray-600">
                  Créations, cessations et procédures collectives
                  sur les 12 derniers mois — source officielle BODACC.
                </p>
              </div>
            )}

            {bodaccLoading && (
              <div className="rounded-lg bg-white/[0.02] p-4">
                <p className="text-sm text-gray-500 animate-pulse">
                  Chargement des données BODACC...
                </p>
              </div>
            )}

            {bodaccStats && (
              <>
                {/* KPI BODACC */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: "Immatriculations", value: bodaccStats.total_immatriculations, color: "text-emerald-400" },
                    { label: "Radiations", value: bodaccStats.total_radiations, color: "text-red-400" },
                    { label: "Procédures", value: bodaccStats.total_procol, color: "text-amber-400" },
                    { label: "Cessions", value: bodaccStats.total_ventes, color: "text-sky-400" },
                  ].map((kpi) => (
                    <div key={kpi.label} className="rounded-lg bg-white/[0.02] p-3">
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                        {kpi.label}
                      </p>
                      <p className={`text-2xl font-bold tabular-nums ${kpi.color}`}>
                        {kpi.value}
                      </p>
                      <p className="text-[11px] text-gray-600">12 derniers mois</p>
                    </div>
                  ))}
                </div>

                {/* Timeline créations vs radiations */}
                {bodaccStats.timeline.length > 0 && (
                  <div className="rounded-lg bg-white/[0.02] p-4">
                    <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                      Évolution mensuelle
                    </h3>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart
                        data={bodaccStats.timeline}
                        margin={{ top: 8, right: 8, left: -16, bottom: 8 }}
                        barCategoryGap="20%"
                      >
                        <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                        <XAxis
                          dataKey="month"
                          tick={{ fill: "#4b5563", fontSize: 10 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: "#4b5563", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                          allowDecimals={false}
                        />
                        <Tooltip
                          content={(props) => (
                            <ChartTooltip
                              active={props.active}
                              payload={props.payload as TooltipProps["payload"]}
                              label={props.label}
                              formatter={(v, name) => `${v} ${name}`}
                            />
                          )}
                          cursor={{ fill: "rgba(255,255,255,0.03)" }}
                        />
                        <Bar dataKey="immatriculations" name="Immatriculations"
                          fill="#34d399" radius={[3, 3, 0, 0]} />
                        <Bar dataKey="radiations" name="Radiations"
                          fill="#f87171" radius={[3, 3, 0, 0]} />
                        <Bar dataKey="procol" name="Procédures"
                          fill="#fbbf24" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                    {/* Légende manuelle */}
                    <div className="flex items-center gap-4 mt-2">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-400" />
                        <span className="text-[11px] text-gray-500">Immatriculations</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-red-400" />
                        <span className="text-[11px] text-gray-500">Radiations</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-amber-400" />
                        <span className="text-[11px] text-gray-500">Procédures</span>
                      </div>
                    </div>
                  </div>
                )}

                <p className="text-[10px] text-gray-600">
                  Source : BODACC — données officielles, périmètre
                  {bodaccStats.region ? ` ${bodaccStats.region}` : " France entière"},
                  12 derniers mois.
                </p>
              </>
            )}
          </div>
        )}

        {/* CARTOGRAPHIE */}
        {activeTab === "carto" && (
          <div className="p-4">
            <div className="rounded-lg border border-white/[0.06] overflow-hidden" style={{ height: 380 }}>
              {mapPoints && mapPoints.length > 0 ? (
                (() => {
                  // eslint-disable-next-line @typescript-eslint/no-require-imports
                  const ResultsMap = require("./ResultsMap").default;
                  return <ResultsMap data={mapPoints} className="w-full h-full" />;
                })()
              ) : (
                <div className="flex items-center justify-center h-full text-gray-600 text-sm">
                  Aucune donnée géographique disponible pour ce panel.
                </div>
              )}
            </div>
          </div>
        )}

        {/* CLASSEMENTS */}
        {activeTab === "classements" && (
          <div className="p-4 space-y-4">
            {/* Top 10 CA */}
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-sm font-medium text-white mb-3">Top 10 — CA</h3>
              {(() => {
                const ranked = [...filteredData]
                  .filter((r) => r.chiffre_affaires != null)
                  .sort((a, b) => Number(b.chiffre_affaires) - Number(a.chiffre_affaires))
                  .slice(0, 10);
                if (ranked.length === 0) return (
                  <p className="text-sm text-gray-600">Données CA non disponibles.</p>
                );
                return (
                  <div className="space-y-2">
                    {ranked.map((r, i) => (
                      <div key={r.siren || String(i)} className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-[11px] text-gray-600 w-5 flex-shrink-0 tabular-nums">
                            {i + 1}.
                          </span>
                          <span className="text-sm text-gray-300 truncate">{r.nom}</span>
                        </div>
                        <span className="text-sm font-medium text-white tabular-nums flex-shrink-0">
                          {fmtEur(Number(r.chiffre_affaires))}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>

            {/* Top 10 Croissance */}
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <h3 className="text-sm font-medium text-white mb-3">Top 10 — Croissance CA</h3>
              {(() => {
                const ranked = [...filteredData]
                  .filter((r) => r.variation_ca_pct != null)
                  .sort((a, b) => Number(b.variation_ca_pct) - Number(a.variation_ca_pct))
                  .slice(0, 10);
                if (ranked.length === 0) return (
                  <p className="text-sm text-gray-600">Données de variation CA non disponibles.</p>
                );
                return (
                  <div className="space-y-2">
                    {ranked.map((r, i) => (
                      <div key={r.siren || String(i)} className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-[11px] text-gray-600 w-5 flex-shrink-0 tabular-nums">
                            {i + 1}.
                          </span>
                          <span className="text-sm text-gray-300 truncate">{r.nom}</span>
                        </div>
                        <span className={`text-sm font-medium tabular-nums flex-shrink-0 ${
                          Number(r.variation_ca_pct) >= 0 ? "text-emerald-400" : "text-amber-400"
                        }`}>
                          {fmtPct(Number(r.variation_ca_pct))}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          </div>
        )}

        {/* TABLEAU */}
        {activeTab === "tableau" && (
          <div className="p-4">
            {(() => {
              // eslint-disable-next-line @typescript-eslint/no-require-imports
              const ResultsTable = require("./ResultsTable").default;
              return (
                <ResultsTable
                  data={filteredData}
                  columns={columns}
                  total={filteredData.length}
                  searchId={searchId}
                  creditsRequired={creditsRequired}
                  userCredits={userCredits}
                  creditsUnlimited={creditsUnlimited}
                  onExport={onExport}
                  exporting={exporting}
                  mapPoints={mapPoints || []}
                />
              );
            })()}
          </div>
        )}

        {/* INSIGHTS IA */}
        {activeTab === "insights" && (
          <div className="p-4">
            <div className="rounded-lg bg-white/[0.02] p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Insights IA
                  </h3>
                  <p className="text-[11px] text-gray-600 mt-0.5">
                    Analyse factuelle du panel — non prescriptif, données publiques.
                  </p>
                </div>
                {!insightsGenerated && (
                  <button
                    type="button"
                    onClick={generateInsights}
                    disabled={insightsLoading}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-300 text-xs font-medium hover:bg-amber-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[36px]"
                  >
                    {insightsLoading ? (
                      <>
                        <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                        </svg>
                        Génération…
                      </>
                    ) : (
                      <>✦ Générer les insights</>
                    )}
                  </button>
                )}
                {insightsGenerated && (
                  <button
                    type="button"
                    onClick={() => {
                      setInsightsGenerated(false);
                      setInsights([]);
                      setInsightsError(null);
                    }}
                    className="text-[11px] text-gray-600 hover:text-gray-400 transition-colors"
                  >
                    Regénérer
                  </button>
                )}
              </div>

              {!insightsGenerated && !insightsLoading && !insightsError && (
                <div className="flex flex-col items-center justify-center py-8 gap-2">
                  <p className="text-sm text-gray-600 text-center">
                    Clique sur « Générer les insights » pour obtenir une analyse
                    automatique du panel basée sur les données disponibles.
                  </p>
                </div>
              )}

              {insightsError && (
                <p className="text-sm text-red-400 py-4">{insightsError}</p>
              )}

              {insightsLoading && (
                <div className="space-y-3 mt-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex gap-3">
                      <div className="w-6 h-6 rounded-full bg-white/[0.04] flex-shrink-0 animate-pulse" />
                      <div className="flex-1 space-y-1.5">
                        <div className="h-3 bg-white/[0.04] rounded animate-pulse w-full" />
                        <div className="h-3 bg-white/[0.04] rounded animate-pulse w-3/4" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {insightsGenerated && insights.length > 0 && (
                <div className="space-y-4 mt-2">
                  {insights.map((insight) => (
                    <div key={insight.n} className="flex gap-3">
                      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-500/15 text-amber-300 text-[11px] font-bold flex items-center justify-center">
                        {insight.n}
                      </span>
                      <div className="flex-1">
                        <p className="text-sm text-gray-300 leading-relaxed">
                          {insight.text}
                        </p>
                        <span className="inline-flex mt-1.5 items-center px-1.5 py-0.5 rounded border border-white/[0.06] bg-white/[0.03] text-[10px] text-gray-500">
                          {insight.source}
                        </span>
                      </div>
                    </div>
                  ))}
                  <p className="text-[10px] text-gray-600 pt-2 border-t border-white/[0.04]">
                    Ces insights sont générés automatiquement à partir des données
                    publiques du panel. Ils ne constituent pas un conseil en
                    investissement ni une recommandation personnalisée.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

      </div>

    </div>
  );
}
