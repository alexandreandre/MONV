"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type {
  AtelierImpact,
  BusinessDossierPayload,
  ProjectBrief,
} from "@/lib/api";
import { regenerateAtelierCanvas, updateAtelierBrief } from "@/lib/api";

export interface BriefDrawerProps {
  open: boolean;
  onClose: () => void;
  conversationId: string;
  brief: ProjectBrief;
  onDossierReplaced: (dossier: BusinessDossierPayload) => void;
  onNotify: (kind: "success" | "error", message: string) => void;
  onCreditsRemaining?: (credits: number) => void;
}

function emptyBrief(base: ProjectBrief): ProjectBrief {
  return {
    nom: base.nom ?? "",
    tagline: base.tagline ?? "",
    secteur: base.secteur ?? "",
    localisation: base.localisation ?? "",
    cible: base.cible ?? "",
    budget: base.budget ?? "",
    modele_revenus: base.modele_revenus ?? "",
    ambition: base.ambition ?? "",
    budget_min_eur: base.budget_min_eur ?? null,
    budget_max_eur: base.budget_max_eur ?? null,
    budget_hypotheses: [...(base.budget_hypotheses ?? [])],
  };
}

export default function BriefDrawer({
  open,
  onClose,
  conversationId,
  brief,
  onDossierReplaced,
  onNotify,
  onCreditsRemaining,
}: BriefDrawerProps) {
  const [draft, setDraft] = useState<ProjectBrief>(() => emptyBrief(brief));
  const [impacts, setImpacts] = useState<AtelierImpact[]>(["canvas"]);
  const [busy, setBusy] = useState<null | "canvas" | "save">(null);

  useEffect(() => {
    if (open) {
      setDraft(emptyBrief(brief));
      setImpacts(["canvas"]);
    }
  }, [open, brief]);

  if (!open) return null;

  function toggleImpact(i: AtelierImpact) {
    setImpacts((prev) =>
      prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]
    );
  }

  async function handleRegenerateCanvas() {
    setBusy("canvas");
    try {
      const res = await regenerateAtelierCanvas({ conversation_id: conversationId });
      onDossierReplaced(res.dossier);
      if (typeof res.credits_remaining === "number") {
        onCreditsRemaining?.(res.credits_remaining);
      }
      onNotify("success", "Canvas régénéré.");
    } catch (e: unknown) {
      onNotify("error", e instanceof Error ? e.message : "Canvas indisponible.");
    } finally {
      setBusy(null);
    }
  }

  async function handleSaveBrief() {
    if (impacts.length === 0) {
      onNotify("error", "Choisis au moins une zone à recalculer.");
      return;
    }
    setBusy("save");
    try {
      const res = await updateAtelierBrief({
        conversation_id: conversationId,
        brief: draft,
        impacts,
      });
      onDossierReplaced(res.dossier);
      if (typeof res.credits_remaining === "number") {
        onCreditsRemaining?.(res.credits_remaining);
      }
      onNotify("success", "Brief enregistré.");
      onClose();
    } catch (e: unknown) {
      onNotify("error", e instanceof Error ? e.message : "Enregistrement impossible.");
    } finally {
      setBusy(null);
    }
  }

  const field = (
    id: keyof ProjectBrief,
    label: string,
    multiline?: boolean
  ) => (
    <label key={String(id)} className="block">
      <span className="text-[11px] uppercase tracking-[0.1em] text-gray-500">
        {label}
      </span>
      {multiline ? (
        <textarea
          className="mt-1 w-full rounded-lg border border-white/[0.08] bg-surface-0 px-3 py-2 text-sm text-gray-200 min-h-[72px]"
          value={String(draft[id] ?? "")}
          onChange={(e) =>
            setDraft((d) => ({ ...d, [id]: e.target.value } as ProjectBrief))
          }
        />
      ) : (
        <input
          type="text"
          className="mt-1 w-full rounded-lg border border-white/[0.08] bg-surface-0 px-3 py-2 text-sm text-gray-200"
          value={String(draft[id] ?? "")}
          onChange={(e) =>
            setDraft((d) => ({ ...d, [id]: e.target.value } as ProjectBrief))
          }
        />
      )}
    </label>
  );

  return (
    <div className="fixed inset-0 z-[80] flex justify-end">
      <button
        type="button"
        aria-label="Fermer"
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />
      <aside className="relative w-full max-w-md h-full bg-surface-1 border-l border-white/[0.08] shadow-2xl flex flex-col animate-fade-in">
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-white/[0.06]">
          <h2 className="text-sm font-semibold text-white">Affiner le brief</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/[0.06]"
            aria-label="Fermer le panneau"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-4 space-y-3">
          {field("nom", "Nom du projet")}
          {field("tagline", "Accroche", true)}
          {field("secteur", "Secteur", true)}
          {field("localisation", "Localisation")}
          {field("cible", "Cible")}
          {field("budget", "Budget", true)}
          {field("modele_revenus", "Modèle de revenus")}
          {field("ambition", "Ambition 2–3 ans", true)}

          <div className="pt-2 border-t border-white/[0.06]">
            <p className="text-[11px] uppercase tracking-[0.1em] text-gray-500 mb-2">
              Recalculer après enregistrement
            </p>
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ["canvas", "Canvas"],
                  ["flows", "Flux"],
                  ["segments", "Segments"],
                ] as const
              ).map(([key, label]) => (
                <label
                  key={key}
                  className="inline-flex items-center gap-2 text-xs text-gray-300 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={impacts.includes(key)}
                    onChange={() => toggleImpact(key)}
                    className="rounded border-white/20"
                  />
                  {label}
                </label>
              ))}
            </div>
            <p className="text-[11px] text-gray-600 mt-2">
              Les segments relancent tout le pipeline (coût en crédits selon segments).
            </p>
          </div>
        </div>
        <div className="border-t border-white/[0.06] p-4 space-y-2 flex flex-col gap-2">
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void handleRegenerateCanvas()}
            className="w-full rounded-xl border border-white/[0.12] bg-surface-2 px-4 py-2.5 text-sm font-medium text-gray-200 hover:bg-white/[0.04] disabled:opacity-40"
          >
            {busy === "canvas" ? "Régénération…" : "Régénérer le canvas seul"}
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void handleSaveBrief()}
            className="w-full rounded-xl bg-teal-600 hover:bg-teal-500 text-white px-4 py-2.5 text-sm font-medium disabled:opacity-40"
          >
            {busy === "save" ? "Enregistrement…" : "Enregistrer le brief"}
          </button>
        </div>
      </aside>
    </div>
  );
}
