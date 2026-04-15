"use client";

import { useState, useMemo } from "react";
import {
  Download,
  ExternalLink,
  ChevronUp,
  ChevronDown,
  Search,
  ChevronLeft,
  ChevronRight,
  MapPin,
} from "lucide-react";

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
};

const ROWS_PER_PAGE = 5;

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
}: Props) {
  const canExport = creditsUnlimited || userCredits >= creditsRequired;
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [filterText, setFilterText] = useState("");
  const [currentPage, setCurrentPage] = useState(0);

  const visibleCols = columns.filter(
    (c) =>
      c !== "lien_annuaire" &&
      c !== "google_maps_url" &&
      data.some((r) => r[c])
  );
  const hasGoogleMaps = data.some((r) => r.google_maps_url);

  const filtered = useMemo(() => {
    if (!filterText.trim()) return data;
    const q = filterText.toLowerCase();
    return data.filter((row) =>
      visibleCols.some((col) => {
        const val = row[col];
        return val != null && String(val).toLowerCase().includes(q);
      })
    );
  }, [data, filterText, visibleCols]);

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

  const formatValue = (col: string, val: any) => {
    if (val === null || val === undefined || val === "") return "—";
    if (col === "chiffre_affaires" || col === "resultat_net") {
      const num = Number(val);
      if (isNaN(num)) return val;
      if (Math.abs(num) >= 1_000_000)
        return `${(num / 1_000_000).toFixed(1)}\u202fM\u202f\u20ac`;
      if (Math.abs(num) >= 1_000)
        return `${(num / 1_000).toFixed(0)}\u202fk\u202f\u20ac`;
      return `${num}\u202f\u20ac`;
    }
    if (col === "date_creation" && typeof val === "string" && val.length >= 10) {
      const d = new Date(val);
      if (!isNaN(d.getTime())) {
        return d.toLocaleDateString("fr-FR", {
          day: "numeric",
          month: "short",
          year: "numeric",
        });
      }
    }
    return String(val);
  };

  return (
    <div className="mt-3 rounded-xl border border-white/[0.06] bg-surface-1 overflow-hidden animate-fade-in">
      {data.length > 3 && (
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
              className="w-full bg-surface-2 border border-white/[0.06] rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-white/[0.16] transition-colors"
            />
          </div>
        </div>
      )}

      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-white/[0.03]">
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
                  colSpan={visibleCols.length + 1}
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
                  {visibleCols.map((col) => (
                    <td
                      key={col}
                      className={`px-3 py-2 text-gray-400 whitespace-nowrap max-w-[220px] truncate ${
                        col === "nom" ? "font-medium text-white" : ""
                      }`}
                      title={formatValue(col, row[col])}
                    >
                      {col === "site_web" && row[col] ? (
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

      {totalPages > 1 && (
        <div className="border-t border-white/[0.04] px-4 py-2 flex items-center justify-between">
          <p className="text-xs text-gray-600">
            {filtered.length === data.length
              ? `${data.length} résultats (aperçu)`
              : `${filtered.length} sur ${data.length} (filtré)`}
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
              disabled={currentPage === 0}
              className="p-1 rounded text-gray-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
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
              className="p-1 rounded text-gray-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}

      {total > data.length && (
        <div className="border-t border-white/[0.04] px-4 py-3 flex items-center justify-between">
          <p className="text-sm text-gray-500">
            <span className="text-white font-medium tabular-nums">{data.length}</span> sur{" "}
            <span className="text-white font-medium tabular-nums">{total}</span> résultats
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onExport(searchId, "xlsx")}
              disabled={exporting || !canExport}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white text-gray-950 px-3 py-1.5 text-sm font-medium hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Download size={13} />
              {exporting
                ? "Export..."
                : `Excel (${creditsRequired} cr.)`}
            </button>
            <button
              onClick={() => onExport(searchId, "csv")}
              disabled={exporting || !canExport}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.06] px-3 py-1.5 text-sm font-medium text-gray-300 hover:bg-white/[0.1] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              CSV
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
