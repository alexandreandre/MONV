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
  X,
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

// Colonnes masquées dans le tableau de prospection (trop techniques,
// inutiles pour qualifier un prospect).
const PROSPECTION_COLS_HIDE = new Set([
  "siret",              // doublon du SIREN
  "activite_principale", // code brut NAF, peu lisible
  "region",             // doublon département
  "tranche_effectif",   // code INSEE illisible (ex: "03"), doublon de effectif_label
  "forme_juridique",    // rarement utile en prospection
  "numero_tva",         // technique
  "date_cloture_exercice", // technique comptable
  "annee_dernier_ca",   // visible dans le CA directement
  "annee_n_minus_1",    // idem
  "effectif_financier", // doublon de effectif_label
  "dirigeant_2_nom",    // secondaire
  "dirigeant_2_fonction", // secondaire
]);

/** Colonnes fixes du tableau desktop (6) + colonne Liens = 7 colonnes max. */
const TABLE_COLS = [
  "signaux",
  "nom",
  "telephone",
  "site_web",
  "ville",
  "effectif_label",
] as const;

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

function hasDetailValue(v: unknown): boolean {
  return v != null && v !== "";
}

function DesktopDetailPanel({
  row,
  onClose,
}: {
  row: Record<string, any>;
  onClose: () => void;
}) {
  const addrParts = [row.adresse, row.code_postal, row.ville].filter(
    (p) => p != null && String(p).trim() !== ""
  );
  const fullAddress =
    addrParts.length > 0 ? addrParts.map((p) => String(p).trim()).join(", ") : null;

  const finRows: [string, string][] = [
    ["chiffre_affaires", "Chiffre d'affaires"],
    ["resultat_net", "Résultat net"],
    ["ca_n_minus_1", "CA N-1"],
    ["variation_ca_pct", "Variation CA %"],
    ["ebe", "EBE"],
    ["capitaux_propres", "Capitaux propres"],
  ];
  const hasFinSection = finRows.some(([k]) => hasDetailValue(row[k]));

  const effectifDisplay =
    hasDetailValue(row.effectif_label)
      ? formatValue("effectif_label", row.effectif_label)
      : hasDetailValue(row.effectif_financier)
        ? formatValue("effectif_financier", row.effectif_financier)
        : null;

  const dirigeantLine = [row.dirigeant_prenom, row.dirigeant_nom]
    .filter((p) => p != null && String(p).trim() !== "")
    .map((p) => String(p).trim())
    .join(" ");

  const hasDir2 =
    hasDetailValue(row.dirigeant_2_nom) || hasDetailValue(row.dirigeant_2_fonction);

  const signauxList: Signal[] = Array.isArray(row.signaux) ? row.signaux : [];

  return (
    <div className="flex h-full w-full max-w-[320px] flex-col bg-surface-1 border-l border-white/[0.08] shadow-xl">
      <header className="flex shrink-0 items-start justify-between gap-2 border-b border-white/[0.08] px-3 py-3">
        <h2 className="pr-2 text-sm font-semibold leading-tight text-white">
          {row.nom || "—"}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-white/[0.08] hover:text-white"
          aria-label="Fermer le panneau"
        >
          <X size={18} />
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        <p className="border-b border-white/[0.04] px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-gray-500">
          Coordonnées
        </p>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">Téléphone</span>
          <div className="mt-0.5 text-sm text-gray-200">
            {row.telephone ? (
              <a
                href={`tel:${row.telephone}`}
                className="text-sky-400 hover:text-sky-300"
                onClick={(e) => e.stopPropagation()}
              >
                {row.telephone}
              </a>
            ) : (
              "—"
            )}
          </div>
        </div>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">Site web</span>
          <div className="mt-0.5 truncate text-sm text-gray-200">
            {row.site_web ? (
              <a
                href={
                  String(row.site_web).startsWith("http")
                    ? row.site_web
                    : `https://${row.site_web}`
                }
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300"
                onClick={(e) => e.stopPropagation()}
              >
                {String(row.site_web)
                  .replace(/^https?:\/\//, "")
                  .replace(/\/$/, "")}
              </a>
            ) : (
              "—"
            )}
          </div>
        </div>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">Adresse</span>
          <div className="mt-0.5 text-sm text-gray-200">{fullAddress || "—"}</div>
        </div>
        <div className="flex flex-col gap-2 border-b border-white/[0.04] px-3 py-2.5">
          {row.lien_annuaire ? (
            <a
              href={row.lien_annuaire}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-fit items-center justify-center rounded-lg border border-white/[0.12] bg-white/[0.06] px-3 py-2 text-xs font-medium text-gray-200 transition-colors hover:bg-white/[0.1]"
              onClick={(e) => e.stopPropagation()}
            >
              Voir la fiche
            </a>
          ) : null}
          {row.google_maps_url ? (
            <a
              href={row.google_maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-fit items-center justify-center rounded-lg border border-white/[0.12] bg-white/[0.06] px-3 py-2 text-xs font-medium text-gray-200 transition-colors hover:bg-white/[0.1]"
              onClick={(e) => e.stopPropagation()}
            >
              Voir sur Maps
            </a>
          ) : null}
        </div>

        <p className="border-b border-white/[0.04] px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-gray-500">
          Entreprise
        </p>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">SIREN</span>
          <div className="mt-0.5 text-sm text-gray-200">{formatValue("siren", row.siren)}</div>
        </div>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">Activité</span>
          <div className="mt-0.5 text-sm text-gray-200">
            {formatValue("libelle_activite", row.libelle_activite)}
          </div>
        </div>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">Forme juridique</span>
          <div className="mt-0.5 text-sm text-gray-200">
            {formatValue("forme_juridique", row.forme_juridique)}
          </div>
        </div>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">Date de création</span>
          <div className="mt-0.5 text-sm text-gray-200">
            {formatValue("date_creation", row.date_creation)}
          </div>
        </div>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">Effectif</span>
          <div className="mt-0.5 text-sm text-gray-200">{effectifDisplay || "—"}</div>
        </div>
        <div className="border-b border-white/[0.04] px-3 py-2.5">
          <span className="text-[10px] uppercase text-gray-500">Catégorie</span>
          <div className="mt-0.5 text-sm text-gray-200">
            {formatValue("categorie_entreprise", row.categorie_entreprise)}
          </div>
        </div>

        {hasFinSection && (
          <>
            <p className="border-b border-white/[0.04] px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-gray-500">
              Financier
            </p>
            {finRows.map(([key, label]) =>
              hasDetailValue(row[key]) ? (
                <div key={key} className="border-b border-white/[0.04] px-3 py-2.5">
                  <span className="text-[10px] uppercase text-gray-500">{label}</span>
                  <div
                    className={`mt-0.5 text-sm ${
                      key === "variation_ca_pct" && row[key] != null
                        ? Number(row[key]) >= 0
                          ? "text-emerald-400"
                          : "text-amber-400"
                        : "text-gray-200"
                    }`}
                  >
                    {formatValue(key, row[key])}
                  </div>
                </div>
              ) : null
            )}
          </>
        )}

        {hasDetailValue(row.dirigeant_nom) && (
          <>
            <p className="border-b border-white/[0.04] px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-gray-500">
              Dirigeant
            </p>
            <div className="border-b border-white/[0.04] px-3 py-2.5">
              <span className="text-[10px] uppercase text-gray-500">Nom</span>
              <div className="mt-0.5 text-sm text-gray-200">{dirigeantLine || "—"}</div>
            </div>
            <div className="border-b border-white/[0.04] px-3 py-2.5">
              <span className="text-[10px] uppercase text-gray-500">Fonction</span>
              <div className="mt-0.5 text-sm text-gray-200">
                {formatValue("dirigeant_fonction", row.dirigeant_fonction)}
              </div>
            </div>
            {hasDir2 && (
              <div className="border-b border-white/[0.04] px-3 py-2.5">
                <span className="text-[10px] uppercase text-gray-500">Dirigeant 2</span>
                <div className="mt-0.5 text-sm text-gray-200">
                  {hasDetailValue(row.dirigeant_2_nom)
                    ? String(row.dirigeant_2_nom)
                    : "—"}
                  {hasDetailValue(row.dirigeant_2_fonction)
                    ? ` — ${String(row.dirigeant_2_fonction)}`
                    : ""}
                </div>
              </div>
            )}
          </>
        )}

        {signauxList.length > 0 && (
          <>
            <p className="border-b border-white/[0.04] px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-gray-500">
              Signaux
            </p>
            <div className="border-b border-white/[0.04] px-3 py-2.5">
              <SignalBadges signals={signauxList} />
            </div>
          </>
        )}
      </div>
    </div>
  );
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
  mapPoints,
  segmentLabelByKey,
}: Props) {
  const rowData = Array.isArray(data) ? data : [];
  const colData = Array.isArray(columns) ? columns : [];
  const geoPoints = Array.isArray(mapPoints) ? mapPoints : [];

  const canExport = creditsUnlimited || userCredits >= creditsRequired;
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [filterText, setFilterText] = useState("");
  const [currentPage, setCurrentPage] = useState(0);
  const [signalFilter, setSignalFilter] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "map">("table");
  const [showExcluded, setShowExcluded] = useState(false);
  const [selectedRow, setSelectedRow] = useState<Record<string, any> | null>(null);

  const hasRelevanceData = useMemo(
    () =>
      rowData.some(
        (r) => r.relevance_flag != null && String(r.relevance_flag).length > 0
      ),
    [rowData]
  );
  const hasSegmentTags = useMemo(
    () => rowData.some((r) => Array.isArray(r.segments) && r.segments.length > 0),
    [rowData]
  );
  const excludedCount = useMemo(
    () => rowData.filter((r) => r.relevance_flag === "excluded").length,
    [rowData]
  );

  const dataEffective = useMemo(() => {
    if (showExcluded || !hasRelevanceData) return rowData;
    return rowData.filter((r) => r.relevance_flag !== "excluded");
  }, [rowData, hasRelevanceData, showExcluded]);

  const hasGeoData = geoPoints.length > 0;

  const filteredMapPoints = useMemo(() => {
    let pts = geoPoints;
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
  }, [geoPoints, signalFilter, filterText]);

  const visibleCols = colData.filter(
    (c) =>
      c !== "lien_annuaire" &&
      c !== "google_maps_url" &&
      !META_COLS_HIDE.has(c) &&
      !PROSPECTION_COLS_HIDE.has(c)
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
            ? `Toutes les lignes affichées (${rowData.length}), dont ${excludedCount} écartée(s) par pertinence.`
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
              {/* Desktop: table + panneau détail */}
              <div className="relative hidden min-h-0 flex-1 flex-col overflow-hidden sm:flex">
                <div className="relative min-h-0 flex-1 overflow-hidden">
                  <div className="min-h-0 h-full overflow-x-auto overflow-y-auto scrollbar-thin">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 z-[1] bg-surface-1 shadow-[0_1px_0_0_rgba(255,255,255,0.04)]">
                        <tr className="bg-white/[0.03]">
                          {TABLE_COLS.map((col) => (
                            <th
                              key={col}
                              onClick={
                                col === "signaux" ? undefined : () => toggleSort(col)
                              }
                              className={`px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wider whitespace-nowrap select-none text-gray-500 ${
                                col === "signaux"
                                  ? "cursor-default"
                                  : "cursor-pointer hover:text-gray-300"
                              }`}
                            >
                              <span className="inline-flex items-center gap-1">
                                {COL_LABELS[col] || col}
                                {col !== "signaux" &&
                                  sortCol === col &&
                                  (sortAsc ? (
                                    <ChevronUp size={11} />
                                  ) : (
                                    <ChevronDown size={11} />
                                  ))}
                              </span>
                            </th>
                          ))}
                          <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-gray-500">
                            Liens
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/[0.04]">
                        {pageData.length === 0 ? (
                          <tr>
                            <td
                              colSpan={TABLE_COLS.length + 1}
                              className="px-3 py-6 text-center text-sm text-gray-600"
                            >
                              Aucun résultat ne correspond au filtre.
                            </td>
                          </tr>
                        ) : (
                          pageData.map((row, i) => (
                            <tr
                              key={i}
                              role="button"
                              tabIndex={0}
                              onClick={() => setSelectedRow(row)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  setSelectedRow(row);
                                }
                              }}
                              className={`cursor-pointer transition-colors hover:bg-white/[0.02] ${
                                selectedRow === row
                                  ? "border-l-2 border-l-white/30 bg-white/[0.06]"
                                  : ""
                              }`}
                            >
                              {TABLE_COLS.map((col) => (
                                <td
                                  key={col}
                                  className={`px-3 py-2 text-gray-400 ${
                                    col === "signaux"
                                      ? "whitespace-normal"
                                      : "max-w-[220px] truncate whitespace-nowrap"
                                  } ${col === "nom" ? "font-medium text-white" : ""}`}
                                  title={
                                    col !== "signaux"
                                      ? formatValue(col, row[col])
                                      : undefined
                                  }
                                >
                                  {col === "signaux" ? (
                                    <SignalBadges signals={row.signaux || []} />
                                  ) : col === "site_web" && row[col] ? (
                                    <a
                                      href={
                                        String(row[col]).startsWith("http")
                                          ? row[col]
                                          : `https://${row[col]}`
                                      }
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="truncate text-blue-400 hover:text-blue-300"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      {String(row[col])
                                        .replace(/^https?:\/\//, "")
                                        .replace(/\/$/, "")}
                                    </a>
                                  ) : col === "telephone" && row[col] ? (
                                    <a
                                      href={`tel:${row[col]}`}
                                      className="text-gray-400 hover:text-white"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      {row[col]}
                                    </a>
                                  ) : (
                                    formatValue(col, row[col])
                                  )}
                                </td>
                              ))}
                              <td
                                className="px-3 py-2"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <span className="inline-flex items-center gap-1.5">
                                  {row.lien_annuaire && (
                                    <a
                                      href={row.lien_annuaire}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-gray-500 transition-colors hover:text-white"
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
                                      className="text-gray-500 transition-colors hover:text-blue-400"
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

                  <div
                    className={`absolute inset-y-0 right-0 z-20 w-[320px] max-w-full transition-transform duration-300 ease-out ${
                      selectedRow
                        ? "translate-x-0"
                        : "pointer-events-none translate-x-full"
                    }`}
                  >
                    {selectedRow ? (
                      <DesktopDetailPanel
                        row={selectedRow}
                        onClose={() => setSelectedRow(null)}
                      />
                    ) : null}
                  </div>
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
