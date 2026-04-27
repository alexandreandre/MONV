"use client";

import { useState, useMemo, type ElementType } from "react";
import {
  Landmark,
  Download,
  X,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Clock,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  MapPin,
} from "lucide-react";

interface Signal {
  type: string;
  label: string;
  detail?: string | null;
  severity: string;
}

interface RachatDossierProps {
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
  guardEntities?: {
    secteur?: string | null;
    localisation?: string | null;
    departement?: string | null;
    region?: string | null;
  };
}

function fmtEur(val: number | null | undefined): string {
  if (val == null) return "—";
  if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(1)} M€`;
  if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(0)} k€`;
  return `${val} €`;
}

function fmtPct(val: number | null | undefined): string {
  if (val == null) return "—";
  return `${val >= 0 ? "+" : ""}${val.toFixed(1)} %`;
}

function ageFromDate(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null;
  const year = parseInt(dateStr.slice(0, 4), 10);
  if (isNaN(year)) return null;
  return new Date().getFullYear() - year;
}

const SIGNAL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  positive: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20" },
  warning: { bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/20" },
  info: { bg: "bg-sky-500/10", text: "text-sky-400", border: "border-sky-500/20" },
};

const SIGNAL_ICONS: Record<string, ElementType> = {
  forte_croissance: TrendingUp,
  ca_en_baisse: TrendingDown,
  resultat_negatif: AlertTriangle,
  societe_ancienne: Clock,
  societe_mature: Clock,
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

// Score de transmission 0-100 basé sur les données disponibles
function computeTransmissionScore(row: Record<string, any>): {
  score: number;
  label: string;
  color: string;
  factors: string[];
} {
  let score = 0;
  const factors: string[] = [];

  const age = ageFromDate(row.date_creation);
  if (age !== null) {
    if (age >= 30) {
      score += 35;
      factors.push(`${age} ans d'ancienneté`);
    } else if (age >= 20) {
      score += 20;
      factors.push(`${age} ans d'ancienneté`);
    } else if (age >= 15) {
      score += 10;
      factors.push(`${age} ans d'ancienneté`);
    }
  }

  if (row.chiffre_affaires) {
    score += 20;
    factors.push(`CA ${fmtEur(row.chiffre_affaires)}`);
  }

  if (row.resultat_net !== null && row.resultat_net !== undefined) {
    if (row.resultat_net > 0) {
      score += 20;
      factors.push("Résultat positif");
    } else {
      score -= 10;
      factors.push("Résultat négatif");
    }
  }

  if (row.variation_ca_pct !== null && row.variation_ca_pct !== undefined) {
    if (row.variation_ca_pct >= 0 && row.variation_ca_pct < 20) {
      score += 15;
      factors.push("Croissance stable");
    } else if (row.variation_ca_pct >= 20) {
      score += 10;
      factors.push("Forte croissance");
    }
  }

  if (row.dirigeant_nom) {
    score += 10;
    factors.push("Dirigeant identifié");
  }

  const clamped = Math.max(0, Math.min(100, score));
  let label = "Faible";
  let color = "text-gray-500";
  if (clamped >= 70) {
    label = "Élevé";
    color = "text-emerald-400";
  } else if (clamped >= 45) {
    label = "Modéré";
    color = "text-amber-400";
  } else if (clamped >= 25) {
    label = "Limité";
    color = "text-sky-400";
  }

  return { score: clamped, label, color, factors };
}

function CibleCard({ row, rank }: { row: Record<string, any>; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const age = ageFromDate(row.date_creation);
  const signals: Signal[] = Array.isArray(row.signaux) ? row.signaux : [];
  const ts = computeTransmissionScore(row);

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] overflow-hidden">
      {/* Header */}
      <div className="flex items-start gap-3 p-4">
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center text-[11px] font-bold text-violet-300">
          {rank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white truncate">{row.nom || "—"}</p>
              <p className="text-[11px] text-gray-500 mt-0.5">
                {row.libelle_activite || row.activite_principale || "—"}
                {row.ville ? ` · ${row.ville}` : ""}
              </p>
            </div>
            <div className="flex-shrink-0 text-right">
              <p className={`text-sm font-bold ${ts.color}`}>{ts.label}</p>
              <p className="text-[10px] text-gray-600">score {ts.score}/100</p>
            </div>
          </div>
        </div>
      </div>

      {/* Métriques clés */}
      <div className="grid grid-cols-3 divide-x divide-white/[0.04] border-t border-white/[0.04]">
        {[
          { label: "CA", value: fmtEur(row.chiffre_affaires) },
          { label: "Résultat", value: fmtEur(row.resultat_net) },
          { label: "Ancienneté", value: age !== null ? `${age} ans` : "—" },
        ].map((m) => (
          <div key={m.label} className="px-3 py-2 text-center">
            <p className="text-[10px] text-gray-600 uppercase tracking-wider">{m.label}</p>
            <p className="text-sm font-semibold text-white mt-0.5">{m.value}</p>
          </div>
        ))}
      </div>

      {/* Signaux */}
      {signals.length > 0 && (
        <div className="px-4 py-2 border-t border-white/[0.04] flex flex-wrap gap-1">
          {signals.map((s) => (
            <SignalBadge key={s.type} signal={s} />
          ))}
        </div>
      )}

      {/* Détail expandable */}
      <div className="border-t border-white/[0.04]">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-4 py-2 text-[11px] text-gray-600 hover:text-gray-400 transition-colors"
        >
          <span>Détail de l&apos;analyse</span>
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>

        {expanded && (
          <div className="px-4 pb-4 space-y-3">
            {/* Données financières */}
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "CA N-1", value: fmtEur(row.ca_n_minus_1) },
                { label: "Variation CA", value: fmtPct(row.variation_ca_pct) },
                { label: "Effectif", value: row.effectif_label || "—" },
                { label: "Forme juridique", value: row.forme_juridique || "—" },
                { label: "SIREN", value: row.siren || "—" },
                { label: "Catégorie", value: row.categorie_entreprise || "—" },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-lg bg-white/[0.02] border border-white/[0.04] px-3 py-2"
                >
                  <p className="text-[10px] text-gray-600 uppercase tracking-wider">{label}</p>
                  <p className="text-xs font-medium text-white mt-0.5">{value}</p>
                </div>
              ))}
            </div>

            {/* Dirigeant */}
            {row.dirigeant_nom && (
              <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] px-3 py-2">
                <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-1">Dirigeant</p>
                <p className="text-xs text-white">
                  {[row.dirigeant_prenom, row.dirigeant_nom].filter(Boolean).join(" ")}
                  {row.dirigeant_fonction ? ` — ${row.dirigeant_fonction}` : ""}
                </p>
              </div>
            )}

            {/* Facteurs du score */}
            <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] px-3 py-2">
              <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-1">
                Facteurs score transmission
              </p>
              <div className="flex flex-wrap gap-1">
                {ts.factors.map((f) => (
                  <span
                    key={f}
                    className="text-[10px] text-gray-400 bg-white/[0.04] rounded px-1.5 py-0.5"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>

            {/* Liens */}
            <div className="flex gap-2">
              {row.lien_annuaire && (
                <a
                  href={row.lien_annuaire}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] text-violet-400 hover:text-violet-300"
                >
                  <ExternalLink size={10} /> Fiche annuaire
                </a>
              )}
              {row.google_maps_url && (
                <a
                  href={row.google_maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] text-violet-400 hover:text-violet-300"
                >
                  <MapPin size={10} /> Maps
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RachatDossier({
  data,
  columns: _columns,
  total,
  searchId,
  creditsRequired,
  userCredits,
  creditsUnlimited = false,
  onExport,
  exporting,
  query,
  guardEntities,
}: RachatDossierProps) {
  const [dismissed, setDismissed] = useState(false);
  const [sortBy, setSortBy] = useState<"score" | "ca" | "age">("score");
  const [filterAge, setFilterAge] = useState<string>("tous");

  const canExport = creditsUnlimited || userCredits >= creditsRequired;

  type ScoredRow = Record<string, any> & {
    _ts: ReturnType<typeof computeTransmissionScore>;
  };

  const scored = useMemo((): ScoredRow[] => {
    return data.map((row) => ({
      ...row,
      _ts: computeTransmissionScore(row),
    }));
  }, [data]);

  const filtered = useMemo(() => {
    let rows = scored;
    if (filterAge !== "tous") {
      const minAge = parseInt(filterAge, 10);
      rows = rows.filter((r) => {
        const age = ageFromDate(r.date_creation);
        return age !== null && age >= minAge;
      });
    }
    return rows;
  }, [scored, filterAge]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      if (sortBy === "score") return b._ts.score - a._ts.score;
      if (sortBy === "ca")
        return (Number(b.chiffre_affaires) || 0) - (Number(a.chiffre_affaires) || 0);
      if (sortBy === "age") {
        const ageA = ageFromDate(a.date_creation) ?? 0;
        const ageB = ageFromDate(b.date_creation) ?? 0;
        return ageB - ageA;
      }
      return 0;
    });
  }, [filtered, sortBy]);

  // KPIs
  const nbWithCa = data.filter((r) => r.chiffre_affaires != null).length;
  const nbWithResult = data.filter((r) => r.resultat_net != null).length;
  const nbAncient = data.filter((r) => (ageFromDate(r.date_creation) ?? 0) >= 20).length;
  const nbHighScore = scored.filter((r) => r._ts.score >= 45).length;

  const secteur = guardEntities?.secteur || query || "";
  const zone =
    guardEntities?.localisation || guardEntities?.region || guardEntities?.departement || "";

  if (dismissed) return null;

  return (
    <div className="dark mt-3 rounded-xl border border-violet-500/20 bg-surface-1 overflow-hidden animate-fade-in">
      {/* Barre actions */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/[0.04]">
        <div className="flex items-center gap-1.5 text-[11px] text-gray-600">
          <span>MONV</span>
          <span>/</span>
          <span>Analyse acquisition</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onExport(searchId, "xlsx")}
            disabled={exporting || !canExport}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-white/[0.08] text-gray-300 text-[11px] font-medium hover:bg-white/[0.12] disabled:opacity-40 transition-colors"
          >
            <Download size={11} /> XLSX
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

      {/* Hero */}
      <div className="px-5 pt-5 pb-4 border-b border-white/[0.04]">
        <div className="flex items-start gap-3 mb-3">
          <div className="p-2 rounded-lg bg-violet-500/15 flex-shrink-0">
            <Landmark size={16} className="text-violet-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white leading-tight">
              {secteur ? `Cibles acquisition — ${secteur}` : "Cibles acquisition"}
            </h2>
            <p className="text-sm text-gray-400 mt-0.5">
              {zone && <span>{zone} · </span>}
              {total.toLocaleString("fr-FR")} entreprises identifiées
            </p>
          </div>
        </div>
        <p className="text-[11px] text-gray-600">
          Cadre d&apos;analyse factuel — données publiques INSEE. Aucune valorisation ni conseil
          en investissement.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-white/[0.04] border-b border-white/[0.04]">
        {[
          { label: "Panel", value: total.toLocaleString("fr-FR"), sub: "cibles identifiées" },
          { label: "Score ≥ Modéré", value: String(nbHighScore), sub: "potentiel transmission" },
          { label: "Ancienneté ≥ 20 ans", value: String(nbAncient), sub: "signal transmission" },
          { label: "Avec CA connu", value: `${nbWithCa}/${data.length}`, sub: `${nbWithResult} avec résultat` },
        ].map((k) => (
          <div key={k.label} className="px-5 py-3 flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-wider text-gray-600 font-medium">
              {k.label}
            </span>
            <span className="text-2xl font-bold text-white tabular-nums leading-tight">{k.value}</span>
            <span className="text-[11px] text-gray-600">{k.sub}</span>
          </div>
        ))}
      </div>

      {/* Filtres + tri */}
      <div className="flex flex-wrap items-center gap-2 px-5 py-3 border-b border-white/[0.04] bg-white/[0.01]">
        <span className="text-[11px] text-gray-600 mr-1">Trier :</span>
        {(
          [
            ["score", "Score transmission"],
            ["ca", "CA"],
            ["age", "Ancienneté"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setSortBy(key)}
            className={`px-2.5 py-1.5 rounded-lg text-[12px] border transition-colors ${
              sortBy === key
                ? "bg-violet-500/10 border-violet-500/30 text-violet-300"
                : "bg-white/[0.04] border-white/[0.08] text-gray-400 hover:text-gray-300"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="text-gray-700 mx-1">|</span>
        <span className="text-[11px] text-gray-600">Ancienneté min :</span>
        <select
          value={filterAge}
          onChange={(e) => setFilterAge(e.target.value)}
          className={`rounded-lg px-2.5 py-1.5 text-[12px] border transition-colors cursor-pointer focus:outline-none ${
            filterAge !== "tous"
              ? "bg-violet-500/10 border-violet-500/30 text-violet-300"
              : "bg-white/[0.04] border-white/[0.08] text-gray-400"
          }`}
        >
          <option value="tous">Toutes</option>
          <option value="10">≥ 10 ans</option>
          <option value="15">≥ 15 ans</option>
          <option value="20">≥ 20 ans</option>
          <option value="30">≥ 30 ans</option>
        </select>
        <span className="ml-auto text-[11px] text-gray-600">
          {sorted.length !== total && (
            <>
              {sorted.length} /{" "}
            </>
          )}
          {total.toLocaleString("fr-FR")} cibles
        </span>
      </div>

      {/* Liste des cibles */}
      <div className="p-4 space-y-3">
        {sorted.slice(0, 20).map((row, i) => (
          <CibleCard key={row.siren || String(i)} row={row} rank={i + 1} />
        ))}
        {sorted.length === 0 && (
          <p className="text-sm text-gray-600 text-center py-8">
            Aucune cible ne correspond aux filtres sélectionnés.
          </p>
        )}
      </div>

      {/* Export bas */}
      {total > 20 && (
        <div className="border-t border-white/[0.04] px-5 py-3 flex items-center justify-between">
          <p className="text-sm text-gray-500">
            {sorted.length} cibles affichées sur {total} identifiées
          </p>
          <button
            type="button"
            onClick={() => onExport(searchId, "xlsx")}
            disabled={exporting || !canExport}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white text-gray-950 text-sm font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors min-h-[36px]"
          >
            <Download size={13} />
            {exporting ? "Export..." : `Exporter tout (${creditsRequired} cr.)`}
          </button>
        </div>
      )}

      {/* Disclaimer */}
      <div className="px-5 py-3 border-t border-white/[0.04]">
        <p className="text-[10px] text-gray-700">
          Ce cadre d&apos;analyse est purement indicatif. Il ne constitue ni un conseil juridique,
          ni un conseil financier, ni une valorisation. Toute décision d&apos;acquisition doit
          s&apos;appuyer sur un audit professionnel.
        </p>
      </div>
    </div>
  );
}
