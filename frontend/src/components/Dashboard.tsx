"use client";

import { useState, useEffect } from "react";
import {
  Download,
  Calendar,
  ArrowLeft,
  FileSpreadsheet,
  Building,
} from "lucide-react";
import { apiGet, apiPost, type SearchHistoryItem, type ExportResponse } from "@/lib/api";

interface Props {
  onBack: () => void;
}

const INTENT_LABELS: Record<string, string> = {
  recherche_entreprise: "Recherche entreprise",
  recherche_dirigeant: "Recherche dirigeant",
  enrichissement: "Enrichissement",
};

export default function Dashboard({ onBack }: Props) {
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [exportingId, setExportingId] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const data = await apiGet<SearchHistoryItem[]>("/search/history");
      setHistory(data);
    } catch {}
    setLoading(false);
  };

  const handleExport = async (searchId: string) => {
    setExportingId(searchId);
    try {
      const res = await apiPost<ExportResponse>("/search/export", {
        search_id: searchId,
        format: "xlsx",
      });
      window.open(res.download_url, "_blank");
      await loadHistory();
    } catch {
      /* parent gère les toasts */
    }
    setExportingId(null);
  };

  return (
    <div className="max-w-3xl mx-auto py-10 px-4 sm:px-6">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors mb-6"
      >
        <ArrowLeft size={14} />
        Nouvelle recherche
      </button>

      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-white">Historique</h1>
        <p className="text-gray-500 text-sm mt-1">
          Vos recherches passées et exports
        </p>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-white/[0.06] bg-surface-1 p-4 animate-pulse"
            >
              <div className="h-4 bg-white/[0.04] rounded w-3/4 mb-3" />
              <div className="h-3 bg-white/[0.03] rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : history.length === 0 ? (
        <div className="text-center py-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-white/[0.04] mb-4">
            <Building size={28} className="text-gray-600" />
          </div>
          <p className="text-gray-400 mb-1">Aucune recherche pour l&apos;instant</p>
          <p className="text-gray-600 text-sm mb-4">
            Vos recherches apparaîtront ici
          </p>
          <button
            onClick={onBack}
            className="text-white hover:underline underline-offset-2 text-sm transition-colors"
          >
            Faire votre première recherche
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {history.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-white/[0.06] bg-surface-1 p-4 hover:border-white/[0.12] transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium truncate">
                    {item.query}
                  </p>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-xs text-gray-600">
                    <span className="inline-flex items-center gap-1">
                      <Calendar size={11} />
                      {new Date(item.created_at).toLocaleDateString("fr-FR", {
                        day: "numeric",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    <span className="text-gray-500">
                      {item.results_count} résultat{item.results_count > 1 ? "s" : ""}
                    </span>
                    <span>
                      {item.credits_used} crédit{item.credits_used > 1 ? "s" : ""}
                    </span>
                    <span className="text-gray-600 bg-white/[0.04] px-1.5 py-0.5 rounded text-[11px]">
                      {INTENT_LABELS[item.intent] || item.intent.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {item.exported ? (
                    <span className="inline-flex items-center gap-1 text-[11px] text-green-400/80 bg-green-400/8 px-2 py-1 rounded">
                      <FileSpreadsheet size={11} />
                      Exporté
                    </span>
                  ) : (
                    <button
                      onClick={() => handleExport(item.id)}
                      disabled={exportingId === item.id}
                      className="inline-flex items-center gap-1 text-xs bg-white text-gray-950 px-3 py-1.5 rounded-lg font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors"
                    >
                      <Download size={11} />
                      {exportingId === item.id ? "Export..." : "Exporter"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
