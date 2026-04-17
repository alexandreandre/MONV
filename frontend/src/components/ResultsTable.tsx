"use client";

import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  Download,
  ExternalLink,
  ChevronUp,
  ChevronDown,
  Search,
  ChevronLeft,
  ChevronRight,
  MapPin,
  Building,
  TrendingUp,
  TrendingDown,
  Sparkles,
  UserPlus,
  CircleDollarSign,
  AlertTriangle,
  List,
} from "lucide-react";

const ResultsMap = dynamic(() => import("./ResultsMap"), { ssr: false });

interface Signal {
  type: string;
  label: string;
  detail?: string | null;
  severity: string;
}

interface Props {
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
  /** Libellés des segments pour les tags `segments[]` (Atelier). */
  segmentLabelByKey?: Record<string, string>;
}

const COL_LABELS: Record<string, string> = {
  nom: "Dénomination",
  siren: "SIREN",
  siret: "SIRET",
  activite_principale: "NAF / APE",
  libelle_activite: "Activité (libellé)",
  adresse: "Adresse",
  code_postal: "CP",
  ville: "Commune",
  region: "Région",
  departement: "Département",
  tranche_effectif: "Tranche INSEE",
  effectif_label: "Effectif (tranche)",
  date_creation: "Création (INSEE)",
  forme_juridique: "Forme juridique",
  dirigeant_nom: "Dirigeant — nom",
  dirigeant_prenom: "Dirigeant — prénom",
  dirigeant_fonction: "Dirigeant — fonction",
  chiffre_affaires: "CA (€)",
  resultat_net: "Résultat net (€)",
  email: "Email",
  telephone: "Téléphone",
  site_web: "Site web",
  lien_annuaire: "Fiche entreprise",
  google_maps_url: "Google Maps",
  categorie_entreprise: "Catégorie (PME / ETI…)",
  annee_dernier_ca: "Année (dernier CA)",
  date_cloture_exercice: "Clôture d'exercice",
  marge_brute: "Marge brute (€)",
  ebe: "EBE (€)",
  capitaux_propres: "Capitaux propres (€)",
  effectif_financier: "Effectif (comptes)",
  capital_social: "Capital social (€)",
  numero_tva: "N° TVA",
  ca_n_minus_1: "CA N-1 (€)",
  resultat_n_minus_1: "Résultat N-1 (€)",
  annee_n_minus_1: "Année N-1",
  variation_ca_pct: "Variation CA",
  dirigeant_2_nom: "Dirigeant 2 — nom",
  dirigeant_2_fonction: "Dirigeant 2 — fonction",
  signaux: "Signaux",
};

const CURRENCY_COLS = new Set([
  "chiffre_affaires",
  "resultat_net",
  "marge_brute",
  "ebe",
  "capitaux_propres",
  "capital_social",
  "ca_n_minus_1",
  "resultat_n_minus_1",
]);

const SIGNAL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  positive: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20" },
  warning: { bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/20" },
  info: { bg: "bg-sky-500/10", text: "text-sky-400", border: "border-sky-500/20" },
};

const SIGNAL_ICONS: Record<string, typeof TrendingUp> = {
  forte_croissance: TrendingUp,
  ca_en_baisse: TrendingDown,
  entreprise_recente: Sparkles,
  nouveau_dirigeant: UserPlus,
  augmentation_capital: CircleDollarSign,
  resultat_negatif: AlertTriangle,
};

function SignalBadge({ signal }: { signal: Signal }) {
  const style = SIGNAL_STYLES[signal.severity] || SIGNAL_STYLES.info;
  const Icon = SIGNAL_ICONS[signal.type];
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium border whitespace-nowrap ${style.bg} ${style.text} ${style.border}`}
      title={signal.detail || signal.label}
    >
      {Icon && <Icon size={10} />}
      {signal.label}
    </span>
  );
}

function SignalBadges({ signals }: { signals: Signal[] }) {
  if (!signals || signals.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {signals.map((s) => (
        <SignalBadge key={s.type} signal={s} />
      ))}
    </div>
  );
}

const PRIMARY_COLS = new Set(["nom", "ville", "libelle_activite", "effectif_label", "chiffre_affaires"]);

const META_COLS_HIDE = new Set([
  "relevance_score",
  "relevance_flag",
  "reason_excluded",
  "segments",
  "_dedup_key",
]);

type RelevanceFlag = "ok" | "warning" | "excluded" | string;

function RelevanceBadge({
  flag,
  title,
}: {
  flag: RelevanceFlag | null | undefined;
  title?: string | null;
}) {
  if (!flag) return <span className="text-gray-600">—</span>;
  const styles: Record<string, string> = {
    ok: "bg-emerald-500/15 text-emerald-300 border-emerald-500/25",
    warning: "bg-amber-500/15 text-amber-300 border-amber-500/25",
    excluded: "bg-red-500/15 text-red-300 border-red-500/25",
  };
  const labels: Record<string, string> = {
    ok: "Pertinent",
    warning: "Limite",
    excluded: "Écarté",
  };
  const cls = styles[flag] || "bg-white/[0.06] text-gray-400 border-white/[0.08]";
  return (
    <span
      className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${cls}`}
      title={title || undefined}
    >
      {labels[flag] || flag}
    </span>
  );
}

function SegmentTags({
  keys,
  labelByKey,
}: {
  keys: string[] | null | undefined;
  labelByKey?: Record<string, string>;
}) {
  if (!keys || keys.length === 0) return <span className="text-gray-600">—</span>;
  return (
    <div className="flex flex-wrap gap-1 max-w-[200px]">
      {keys.map((k) => (
        <span
          key={k}
          className="inline-flex rounded border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-gray-300"
          title={k}
        >
          {labelByKey?.[k] || k}
        </span>
      ))}
    </div>
  );
}

/** Aligné sur l’aperçu API (10 lignes) : une seule page dans le fil de discussion. */
const ROWS_PER_PAGE = 10;

/** Même hauteur que la carte : évite un saut de scroll du fil au basculement tableau/carte. */
const RESULTS_BODY_H = "h-[420px] sm:h-[480px]";

function formatValue(col: string, val: any) {
  if (val === null || val === undefined || val === "") return "—";
  if (CURRENCY_COLS.has(col)) {
    const num = Number(val);
    if (isNaN(num)) return String(val);
    if (Math.abs(num) >= 1_000_000)
      return `${(num / 1_000_000).toFixed(1)}\u202fM\u202f\u20ac`;
    if (Math.abs(num) >= 1_000)
      return `${(num / 1_000).toFixed(0)}\u202fk\u202f\u20ac`;
    return `${num}\u202f\u20ac`;
  }
  if (col === "effectif_financier") {
    const num = Number(val);
    if (isNaN(num)) return String(val);
    return num === Math.floor(num) ? String(Math.floor(num)) : String(num);
  }
  if (col === "annee_dernier_ca" || col === "annee_n_minus_1") {
    const n = Number(val);
    if (!isNaN(n)) return String(Math.floor(n));
    return String(val);
  }
  if (col === "variation_ca_pct") {
    const num = Number(val);
    if (isNaN(num)) return String(val);
    const sign = num >= 0 ? "+" : "";
    return `${sign}${num.toFixed(1)}\u202f%`;
  }
  if (col === "date_creation" || col === "date_cloture_exercice") {
    if (typeof val === "string" && val.length >= 10) {
      const d = new Date(val);
      if (!isNaN(d.getTime())) {
        return d.toLocaleDateString("fr-FR", {
          day: "numeric",
          month: "short",
          year: "numeric",
        });
      }
    }
  }
  return String(val);
}

function MobileCard({
  row,
  visibleCols,
  segmentLabelByKey,
  showRelevance,
}: {
  row: Record<string, any>;
  visibleCols: string[];
  segmentLabelByKey?: Record<string, string>;
  showRelevance: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const primaryCols = visibleCols.filter((c) => PRIMARY_COLS.has(c));
  const secondaryCols = visibleCols.filter((c) => !PRIMARY_COLS.has(c));
  const hasSecondary = secondaryCols.length > 0;

  return (
    <div className="rounded-xl border border-white/[0.06] bg-surface-1 p-4 hover:border-white/[0.12] transition-colors">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/[0.06] flex items-center justify-center">
          <Building size={14} className="text-gray-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate">
            {row.nom || "—"}
          </p>
          {row.ville && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">
              {row.ville}
              {row.code_postal ? ` (${row.code_postal})` : ""}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {row.lien_annuaire && (
            <a
              href={row.lien_annuaire}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-lg text-gray-500 hover:text-white active:bg-white/[0.06] transition-colors"
              aria-label="Fiche annuaire"
            >
              <ExternalLink size={14} />
            </a>
          )}
          {row.google_maps_url && (
            <a
              href={row.google_maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-lg text-gray-500 hover:text-blue-400 active:bg-white/[0.06] transition-colors"
              aria-label="Google Maps"
            >
              <MapPin size={14} />
            </a>
          )}
        </div>
      </div>

      {(showRelevance || (Array.isArray(row.segments) && row.segments.length > 0)) && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {showRelevance && (
            <RelevanceBadge
              flag={row.relevance_flag as string}
              title={row.reason_excluded ? String(row.reason_excluded) : undefined}
            />
          )}
          {Array.isArray(row.segments) && row.segments.length > 0 && (
            <SegmentTags keys={row.segments as string[]} labelByKey={segmentLabelByKey} />
          )}
        </div>
      )}

      {row.signaux && row.signaux.length > 0 && (
        <div className="mt-2">
          <SignalBadges signals={row.signaux} />
        </div>
      )}

      {primaryCols.filter((c) => c !== "nom" && c !== "ville" && c !== "signaux").length > 0 && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
          {primaryCols
            .filter((c) => c !== "nom" && c !== "ville" && c !== "signaux")
            .map((col) => (
              <div key={col} className="flex items-baseline gap-1.5">
                <span className="text-[10px] text-gray-600 uppercase tracking-wider">
                  {COL_LABELS[col] || col}
                </span>
                <span className="text-xs text-gray-300">
                  {formatValue(col, row[col])}
                </span>
              </div>
            ))}
        </div>
      )}

      {hasSecondary && (
        <>
          {expanded && (
            <div className="mt-3 pt-3 border-t border-white/[0.04] space-y-2">
              {secondaryCols.map((col) => {
                const val = formatValue(col, row[col]);
                if (val === "—") return null;
                return (
                  <div key={col} className="flex justify-between items-baseline gap-2">
                    <span className="text-[10px] text-gray-600 uppercase tracking-wider flex-shrink-0">
                      {COL_LABELS[col] || col}
                    </span>
                    <span className="text-xs text-gray-400 text-right truncate">
                      {col === "site_web" && row[col] ? (
                        <a
                          href={
                            String(row[col]).startsWith("http")
                              ? row[col]
                              : `https://${row[col]}`
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-400 active:text-blue-300"
                        >
                          {String(row[col]).replace(/^https?:\/\//, "").replace(/\/$/, "")}
                        </a>
                      ) : col === "telephone" && row[col] ? (
                        <a href={`tel:${row[col]}`} className="text-gray-400 active:text-white">
                          {row[col]}
                        </a>
                      ) : (
                        val
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 text-[11px] text-gray-500 hover:text-gray-300 active:text-white transition-colors flex items-center gap-1"
          >
            {expanded ? (
              <>
                <ChevronUp size={12} /> Moins
              </>
            ) : (
              <>
                <ChevronDown size={12} /> Plus de détails
              </>
            )}
          </button>
        </>
      )}
    </div>
  );
}

export default function ResultsTable({
  data,
  columns,
  total,
  searchId,
  creditsRequired,
  userCredits,
  creditsUnlimited = false,
  onExport,
  exporting,
  mapPoints = [],
  segmentLabelByKey,
}: Props) {
  const canExport = creditsUnlimited || userCredits >= creditsRequired;
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [filterText, setFilterText] = useState("");
  const [currentPage, setCurrentPage] = useState(0);
  const [signalFilter, setSignalFilter] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "map">("table");
  const [showExcluded, setShowExcluded] = useState(false);

  const hasRelevanceData = useMemo(
    () => data.some((r) => r.relevance_flag != null && String(r.relevance_flag).length > 0),
    [data]
  );
  const hasSegmentTags = useMemo(
    () => data.some((r) => Array.isArray(r.segments) && r.segments.length > 0),
    [data]
  );
  const excludedCount = useMemo(
    () => data.filter((r) => r.relevance_flag === "excluded").length,
    [data]
  );

  const dataEffective = useMemo(() => {
    if (showExcluded || !hasRelevanceData) return data;
    return data.filter((r) => r.relevance_flag !== "excluded");
  }, [data, hasRelevanceData, showExcluded]);

  const hasGeoData = mapPoints.length > 0;

  const filteredMapPoints = useMemo(() => {
    let pts = mapPoints;
    if (filterText.trim()) {
      const q = filterText.toLowerCase();
      pts = pts.filter((r) => {
        const fields = [
          r.nom,
          r.ville,
          r.adresse,
          r.code_postal,
          r.libelle_activite,
          r.telephone,
        ];
        return fields.some((v) => v != null && String(v).toLowerCase().includes(q));
      });
    }
    if (signalFilter) {
      pts = pts.filter((r) =>
        (r.signaux || []).some((s: Signal) => s.type === signalFilter)
      );
    }
    return pts;
  }, [mapPoints, signalFilter, filterText]);

  const visibleCols = columns.filter(
    (c) =>
      c !== "lien_annuaire" &&
      c !== "google_maps_url" &&
      !META_COLS_HIDE.has(c)
  );

  const allSignalTypes = useMemo(() => {
    const types = new Map<string, string>();
    dataEffective.forEach((row) => {
      (row.signaux || []).forEach((s: Signal) => {
        if (!types.has(s.type)) types.set(s.type, s.label);
      });
    });
    return types;
  }, [dataEffective]);

  const hasSignals = allSignalTypes.size > 0;

  const filtered = useMemo(() => {
    let result = dataEffective;
    if (filterText.trim()) {
      const q = filterText.toLowerCase();
      result = result.filter((row) =>
        visibleCols.some((col) => {
          if (col === "signaux") return false;
          const val = row[col];
          return val != null && String(val).toLowerCase().includes(q);
        })
      );
    }
    if (signalFilter) {
      result = result.filter((row) =>
        (row.signaux || []).some((s: Signal) => s.type === signalFilter)
      );
    }
    return result;
  }, [dataEffective, filterText, visibleCols, signalFilter]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    if (!sortCol) return arr;
    return arr.sort((a, b) => {
      const va = a[sortCol] ?? "";
      const vb = b[sortCol] ?? "";
      if (typeof va === "number" && typeof vb === "number")
        return sortAsc ? va - vb : vb - va;
      return sortAsc
        ? String(va).localeCompare(String(vb))
        : String(vb).localeCompare(String(va));
    });
  }, [filtered, sortCol, sortAsc]);

  const totalPages = Math.ceil(sorted.length / ROWS_PER_PAGE);
  const pageData = sorted.slice(
    currentPage * ROWS_PER_PAGE,
    (currentPage + 1) * ROWS_PER_PAGE
  );

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortAsc(!sortAsc);
    else {
      setSortCol(col);
      setSortAsc(true);
    }
    setCurrentPage(0);
  };

  const signalChips = hasSignals && (
    <div className="px-3 pt-2 pb-1 flex flex-wrap gap-1.5">
      <button
        onClick={() => { setSignalFilter(null); setCurrentPage(0); }}
        className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
          signalFilter === null
            ? "bg-white/[0.1] text-white border-white/[0.2]"
            : "bg-transparent text-gray-500 border-white/[0.06] hover:text-gray-300 hover:border-white/[0.12]"
        }`}
      >
        Tous
      </button>
      {Array.from(allSignalTypes.entries()).map(([type, label]) => {
        const Icon = SIGNAL_ICONS[type];
        const active = signalFilter === type;
        return (
          <button
            key={type}
            onClick={() => { setSignalFilter(active ? null : type); setCurrentPage(0); }}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
              active
                ? "bg-white/[0.1] text-white border-white/[0.2]"
                : "bg-transparent text-gray-500 border-white/[0.06] hover:text-gray-300 hover:border-white/[0.12]"
            }`}
          >
            {Icon && <Icon size={10} />}
            {label}
          </button>
        );
      })}
    </div>
  );

  const relevanceBar =
    hasRelevanceData && excludedCount > 0 ? (
      <div className="px-3 pt-2 pb-1 flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.04]">
        <p className="text-[11px] text-gray-500">
          {showExcluded
            ? `Toutes les lignes affichées (${data.length}), dont ${excludedCount} écartée(s) par pertinence.`
            : `${excludedCount} ligne(s) écartée(s) masquée(s).`}
        </p>
        <button
          type="button"
          onClick={() => {
            setShowExcluded(!showExcluded);
            setCurrentPage(0);
          }}
          className="text-[11px] font-medium text-sky-400 hover:text-sky-300"
        >
          {showExcluded
            ? "Masquer les écartées"
            : `Voir les ${excludedCount} résultat(s) écarté(s)`}
        </button>
      </div>
    ) : null;

  const filterBar = dataEffective.length > 3 && (
    <div className="px-3 py-2 border-b border-white/[0.04]">
      <div className="relative">
        <Search
          size={13}
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600"
        />
        <input
          type="text"
          value={filterText}
          onChange={(e) => {
            setFilterText(e.target.value);
            setCurrentPage(0);
          }}
          placeholder="Filtrer les résultats..."
          className="w-full bg-surface-2 border border-white/[0.06] rounded-lg pl-8 pr-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-white/[0.16] transition-colors min-h-[44px]"
        />
      </div>
    </div>
  );

  const pagination = totalPages > 1 && (
    <div className="border-t border-white/[0.04] px-4 py-2 flex items-center justify-between">
      <p className="text-xs text-gray-600">
        {filtered.length === dataEffective.length
          ? `${dataEffective.length} résultats (aperçu)`
          : `${filtered.length} sur ${dataEffective.length} (filtré)`}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
          disabled={currentPage === 0}
          className="p-2 rounded-lg text-gray-500 hover:text-white active:bg-white/[0.06] disabled:opacity-30 disabled:cursor-not-allowed min-w-[44px] min-h-[44px] flex items-center justify-center"
        >
          <ChevronLeft size={15} />
        </button>
        <span className="text-xs tabular-nums text-gray-500 px-2">
          {currentPage + 1}/{totalPages}
        </span>
        <button
          onClick={() =>
            setCurrentPage(Math.min(totalPages - 1, currentPage + 1))
          }
          disabled={currentPage >= totalPages - 1}
          className="p-2 rounded-lg text-gray-500 hover:text-white active:bg-white/[0.06] disabled:opacity-30 disabled:cursor-not-allowed min-w-[44px] min-h-[44px] flex items-center justify-center"
        >
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  );

  const exportBar = total > dataEffective.length && (
    <div className="border-t border-white/[0.04] px-4 py-3">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <p className="text-sm text-gray-500">
          <span className="text-white font-medium tabular-nums">{dataEffective.length}</span> sur{" "}
          <span className="text-white font-medium tabular-nums">{total}</span> résultats
        </p>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          {hasGeoData && (
            <button
              type="button"
              onClick={() => setViewMode(viewMode === "map" ? "table" : "map")}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white/[0.06] px-3 py-2 text-sm font-medium text-gray-300 hover:bg-white/[0.1] active:bg-white/[0.15] transition-colors min-h-[44px]"
            >
              {viewMode === "map" ? (
                <>
                  <List size={13} />
                  Tableau
                </>
              ) : (
                <>
                  <MapPin size={13} />
                  Carte
                </>
              )}
            </button>
          )}
          <button
            onClick={() => onExport(searchId, "xlsx")}
            disabled={exporting || !canExport}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white text-gray-950 px-3 py-2 text-sm font-medium hover:bg-gray-200 active:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-1 sm:flex-initial min-h-[44px]"
          >
            <Download size={13} />
            {exporting ? "Export..." : `Excel (${creditsRequired} cr.)`}
          </button>
          <button
            onClick={() => onExport(searchId, "csv")}
            disabled={exporting || !canExport}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white/[0.06] px-3 py-2 text-sm font-medium text-gray-300 hover:bg-white/[0.1] active:bg-white/[0.15] disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
          >
            CSV
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="mt-3 rounded-xl border border-white/[0.06] bg-surface-1 overflow-hidden animate-fade-in">
      {signalChips}
      {relevanceBar}
      {filterBar}

      <div className="px-3 pt-3 pb-3">
        <div
          className={`${RESULTS_BODY_H} flex min-h-0 flex-col overflow-hidden rounded-lg border border-white/[0.04]`}
        >
          {viewMode === "map" ? (
            <ResultsMap data={filteredMapPoints} className="min-h-0 w-full flex-1" />
          ) : (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              {/* Desktop: table */}
              <div className="hidden min-h-0 flex-1 flex-col overflow-hidden sm:flex">
                <div className="min-h-0 flex-1 overflow-x-auto overflow-y-auto scrollbar-thin">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 z-[1] bg-surface-1 shadow-[0_1px_0_0_rgba(255,255,255,0.04)]">
                      <tr className="bg-white/[0.03]">
                  {hasRelevanceData && (
                    <th className="px-3 py-2 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Pertinence
                    </th>
                  )}
                  {hasSegmentTags && (
                    <th className="px-3 py-2 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Segments
                    </th>
                  )}
                  {visibleCols.map((col) => (
                    <th
                      key={col}
                      onClick={() => toggleSort(col)}
                      className="px-3 py-2 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-300 whitespace-nowrap select-none"
                    >
                      <span className="inline-flex items-center gap-1">
                        {COL_LABELS[col] || col}
                        {sortCol === col &&
                          (sortAsc ? (
                            <ChevronUp size={11} />
                          ) : (
                            <ChevronDown size={11} />
                          ))}
                      </span>
                    </th>
                  ))}
                  <th className="px-3 py-2 text-[11px] font-medium text-gray-500 uppercase tracking-wider">
                    Liens
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {pageData.length === 0 ? (
                  <tr>
                    <td
                      colSpan={
                        visibleCols.length +
                        1 +
                        (hasRelevanceData ? 1 : 0) +
                        (hasSegmentTags ? 1 : 0)
                      }
                      className="px-3 py-6 text-center text-gray-600 text-sm"
                    >
                      Aucun résultat ne correspond au filtre.
                    </td>
                  </tr>
                ) : (
                  pageData.map((row, i) => (
                    <tr
                      key={i}
                      className="hover:bg-white/[0.02] transition-colors"
                    >
                      {hasRelevanceData && (
                        <td className="px-3 py-2 whitespace-nowrap align-middle">
                          <RelevanceBadge
                            flag={row.relevance_flag as string}
                            title={
                              row.reason_excluded ? String(row.reason_excluded) : undefined
                            }
                          />
                        </td>
                      )}
                      {hasSegmentTags && (
                        <td className="px-3 py-2 align-middle">
                          <SegmentTags
                            keys={row.segments as string[]}
                            labelByKey={segmentLabelByKey}
                          />
                        </td>
                      )}
                      {visibleCols.map((col) => (
                        <td
                          key={col}
                          className={`px-3 py-2 text-gray-400 ${
                            col === "signaux" ? "whitespace-normal" : "whitespace-nowrap max-w-[220px] truncate"
                          } ${col === "nom" ? "font-medium text-white" : ""}`}
                          title={col !== "signaux" ? formatValue(col, row[col]) : undefined}
                        >
                          {col === "signaux" ? (
                            <SignalBadges signals={row.signaux || []} />
                          ) : col === "variation_ca_pct" && row[col] != null ? (
                            <span className={Number(row[col]) >= 0 ? "text-emerald-400" : "text-amber-400"}>
                              {formatValue(col, row[col])}
                            </span>
                          ) : col === "site_web" && row[col] ? (
                            <a
                              href={
                                String(row[col]).startsWith("http")
                                  ? row[col]
                                  : `https://${row[col]}`
                              }
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-400 hover:text-blue-300 truncate"
                            >
                              {String(row[col])
                                .replace(/^https?:\/\//, "")
                                .replace(/\/$/, "")}
                            </a>
                          ) : col === "telephone" && row[col] ? (
                            <a
                              href={`tel:${row[col]}`}
                              className="text-gray-400 hover:text-white"
                            >
                              {row[col]}
                            </a>
                          ) : (
                            formatValue(col, row[col])
                          )}
                        </td>
                      ))}
                      <td className="px-3 py-2">
                        <span className="inline-flex items-center gap-1.5">
                          {row.lien_annuaire && (
                            <a
                              href={row.lien_annuaire}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-gray-500 hover:text-white transition-colors"
                              title="Fiche annuaire"
                            >
                              <ExternalLink size={13} />
                            </a>
                          )}
                          {row.google_maps_url && (
                            <a
                              href={row.google_maps_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-gray-500 hover:text-blue-400 transition-colors"
                              title="Voir sur Google Maps"
                            >
                              <MapPin size={13} />
                            </a>
                          )}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
                </div>
              </div>

              {/* Mobile: cards */}
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden sm:hidden">
                {pageData.length === 0 ? (
                  <p className="px-4 py-6 text-center text-gray-600 text-sm">
                    Aucun résultat ne correspond au filtre.
                  </p>
                ) : (
                  <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 pb-2 pt-3">
                    {pageData.map((row, i) => (
                      <MobileCard
                        key={i}
                        row={row}
                        visibleCols={visibleCols}
                        segmentLabelByKey={segmentLabelByKey}
                        showRelevance={hasRelevanceData}
                      />
                    ))}
                  </div>
                )}
              </div>

              {pagination}
            </div>
          )}
        </div>
      </div>
      {exportBar}
    </div>
  );
}
