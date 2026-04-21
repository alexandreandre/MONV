"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import type {
  AgentSynthesis,
  AtelierChecklist,
  ChecklistItem,
  ChecklistSection,
} from "@/lib/api";

type PanelItem = {
  sectionTitle: string;
  label: string;
  guide: string;
};

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

/** Normalise une checklist API (clés FR / formes variables). */
function parseLooseChecklist(raw: unknown): AtelierChecklist | null {
  const r = asRecord(raw);
  if (!r) return null;

  const headline = String(r.headline ?? r.titre ?? "").trim() || "Feuille de route";
  const ledeRaw = r.lede ?? r.intro;
  const lede = typeof ledeRaw === "string" && ledeRaw.trim() ? ledeRaw.trim() : null;
  const pitfallsTitleRaw = r.pitfalls_title ?? r.pieges_titre;
  const pitfallsTitle =
    typeof pitfallsTitleRaw === "string" && pitfallsTitleRaw.trim()
      ? pitfallsTitleRaw.trim()
      : null;

  const sectionsIn = (r.sections ?? r.etapes ?? r.phases ?? []) as unknown;
  const sections: ChecklistSection[] = [];
  if (Array.isArray(sectionsIn)) {
    for (const sec of sectionsIn) {
      const s = asRecord(sec);
      if (!s) continue;
      const title = String(s.title ?? s.nom ?? s.phase ?? s.intitule ?? "").trim();
      if (!title) continue;
      const subtitle =
        typeof s.subtitle === "string" && s.subtitle.trim()
          ? s.subtitle.trim()
          : typeof s.sous_titre === "string" && s.sous_titre.trim()
            ? s.sous_titre.trim()
            : null;
      const itemsIn = (s.items ?? s.actions ?? s.taches ?? s.etapes ?? []) as unknown;
      const items: ChecklistItem[] = [];
      if (Array.isArray(itemsIn)) {
        for (const it of itemsIn) {
          if (typeof it === "string" && it.trim()) {
            items.push({ label: it.trim(), guide: "" });
            continue;
          }
          const o = asRecord(it);
          if (!o) continue;
          const label = String(
            o.label ?? o.texte ?? o.action ?? o.titre ?? o.nom ?? "",
          ).trim();
          if (!label) continue;
          const guide = String(o.guide ?? o.aide ?? o.detail ?? o.description ?? "").trim();
          items.push({ label, guide });
        }
      }
      if (items.length > 0) {
        sections.push({ title, subtitle, items });
      }
    }
  }

  const pitfalls: ChecklistItem[] = [];
  const pitIn = (r.pitfalls ?? r.pieges ?? []) as unknown;
  if (Array.isArray(pitIn)) {
    for (const it of pitIn) {
      if (typeof it === "string" && it.trim()) {
        pitfalls.push({ label: it.trim(), guide: "" });
        continue;
      }
      const o = asRecord(it);
      if (!o) continue;
      const label = String(o.label ?? o.texte ?? o.action ?? "").trim();
      if (!label) continue;
      const guide = String(o.guide ?? o.aide ?? o.detail ?? "").trim();
      pitfalls.push({ label, guide });
    }
  }

  if (sections.length === 0 && pitfalls.length === 0) return null;
  return {
    headline,
    lede,
    sections,
    pitfalls_title: pitfallsTitle,
    pitfalls,
  };
}

function buildFallbackChecklist(synthesis: AgentSynthesis): AtelierChecklist {
  const steps = (synthesis.prochaines_etapes ?? []).map((s) => String(s).trim()).filter(Boolean);
  const forces = (synthesis.forces ?? []).map((s) => String(s).trim()).filter(Boolean);
  const risques = (synthesis.risques ?? []).map((s) => String(s).trim()).filter(Boolean);
  const kpis = (synthesis.kpis ?? []).map((s) => String(s).trim()).filter(Boolean);

  const sections: ChecklistSection[] = [];

  if (steps.length > 0) {
    sections.push({
      title: "Prochaines étapes",
      subtitle: null,
      items: steps.map((label) => ({ label, guide: "" })),
    });
  }
  if (forces.length > 0) {
    sections.push({
      title: "Forces à exploiter",
      subtitle: null,
      items: forces.map((label) => ({
        label,
        guide:
          "Capitalisez sur ce point dans votre discours investisseurs, partenariats et recrutement.",
      })),
    });
  }
  if (risques.length > 0) {
    sections.push({
      title: "Risques à traiter",
      subtitle: null,
      items: risques.map((label) => ({
        label,
        guide:
          "Prévoyez une contre-mesure (budget, clause, plan B) et validez-la avec un conseil de métier ou juridique.",
      })),
    });
  }
  if (kpis.length > 0) {
    sections.push({
      title: "Indicateurs à suivre",
      subtitle: null,
      items: kpis.map((label) => ({
        label,
        guide: "Définissez la fréquence de suivi (hebdo / mensuel) et la source de donnée.",
      })),
    });
  }

  if (sections.length > 0) {
    return {
      headline: "Plan d’action prioritaire",
      lede: "À décliner avec votre équipe et vos conseils.",
      sections,
      pitfalls_title: null,
      pitfalls: [],
    };
  }

  return {
    headline: "Feuille de route",
    lede: "Relancez une génération de dossier ou affinez le brief pour obtenir une checklist détaillée.",
    sections: [
      {
        title: "À structurer",
        subtitle: null,
        items: [
          {
            label: "Cadrer trois décisions bloquantes pour les 30 prochains jours",
            guide:
              "Choisissez trois sujets (ex. financement, local, offre) et assignez un propriétaire, une échéance et un critère de « fait / pas fait ».",
          },
          {
            label: "Aligner brief, chiffres et discours investisseur",
            guide:
              "Même histoire partout : pitch une page, ordres de grandeur cohérents, risques assumés avec plans de mitigation.",
          },
          {
            label: "Prendre deux rendez-vous terrain ou experts",
            guide:
              "Un dispositif d’accompagnement territorial et un expert sectoriel suffisent souvent à débloquer la suite.",
          },
        ],
      },
    ],
    pitfalls_title: null,
    pitfalls: [],
  };
}

function normalizeChecklist(synthesis: AgentSynthesis): AtelierChecklist {
  const loose = parseLooseChecklist(synthesis.checklist);
  if (loose) return loose;
  return buildFallbackChecklist(synthesis);
}

interface DossierChecklistProps {
  synthesis: AgentSynthesis;
}

export default function DossierChecklist({ synthesis }: DossierChecklistProps) {
  const data = useMemo(
    () => normalizeChecklist(synthesis ?? ({} as AgentSynthesis)),
    [synthesis],
  );
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<PanelItem | null>(null);

  const openItem = useCallback((sectionTitle: string, item: ChecklistItem) => {
    setActive({
      sectionTitle,
      label: item.label,
      guide: item.guide?.trim() || "",
    });
    setOpen(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const headline = data.headline?.trim() || "Feuille de route";
  const lede = data.lede?.trim();
  const pitfallsTitle = data.pitfalls_title?.trim() || "Pièges à éviter";

  return (
    <section
      className="rounded-2xl border border-border bg-card px-5 py-5 sm:px-6"
      aria-label="Checklist d’actions"
    >
      <div className="mb-5 border-b border-border pb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground mb-2">
          Checklist d’action
        </p>
        <h3 className="text-base sm:text-lg font-semibold text-foreground leading-snug">
          {headline}
        </h3>
        {lede ? (
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">{lede}</p>
        ) : null}
      </div>

      <div className="space-y-8">
        {data.sections.map((sec, si) => (
          <div key={si}>
            <h4 className="text-xs font-semibold text-foreground tracking-tight mb-3">
              {sec.title}
              {sec.subtitle ? (
                <span className="font-normal text-muted-foreground"> — {sec.subtitle}</span>
              ) : null}
            </h4>
            <ul className="space-y-0 border border-border rounded-xl overflow-hidden divide-y divide-white/[0.05]">
              {sec.items.map((item, ii) => (
                <li key={ii}>
                  <button
                    type="button"
                    onClick={() => openItem(sec.title, item)}
                    className="w-full text-left px-3.5 py-3 sm:px-4 sm:py-3.5 flex gap-3 items-start hover:bg-muted/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-teal-500/40 transition-colors"
                  >
                    <span
                      className="mt-1 h-3.5 w-3.5 shrink-0 rounded border border-white/25 bg-transparent"
                      aria-hidden
                    />
                    <span className="text-sm text-foreground leading-relaxed min-w-0">
                      {item.label}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}

        {data.pitfalls && data.pitfalls.length > 0 ? (
          <div>
            <h4 className="text-xs font-semibold text-amber-200/90 mb-3">{pitfallsTitle}</h4>
            <ul className="space-y-0 border border-amber-500/20 rounded-xl overflow-hidden divide-y divide-amber-500/10">
              {data.pitfalls.map((item, pi) => (
                <li key={pi}>
                  <button
                    type="button"
                    onClick={() => openItem(pitfallsTitle, item)}
                    className="w-full text-left px-3.5 py-3 sm:px-4 sm:py-3.5 flex gap-3 items-start hover:bg-amber-500/[0.06] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-amber-500/35 transition-colors"
                  >
                    <span
                      className="mt-1 h-3.5 w-3.5 shrink-0 rounded border border-amber-400/40 bg-transparent"
                      aria-hidden
                    />
                    <span className="text-sm text-foreground leading-relaxed min-w-0">
                      {item.label}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      {open && active && typeof document !== "undefined"
        ? createPortal(
            <div
              className="fixed inset-0 z-[80] flex justify-end bg-black/55 p-2 sm:p-4"
              role="presentation"
              onMouseDown={(e) => {
                if (e.target === e.currentTarget) setOpen(false);
              }}
            >
              <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="checklist-guide-title"
                className="flex h-full max-h-[min(100dvh,920px)] w-full max-w-md flex-col rounded-2xl border border-white/[0.1] bg-[#111114] shadow-2xl sm:max-h-[90vh]"
              >
                <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-1">
                      {active.sectionTitle}
                    </p>
                    <h2
                      id="checklist-guide-title"
                      className="text-sm font-semibold text-foreground leading-snug"
                    >
                      {active.label}
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="shrink-0 rounded-lg border border-border p-2 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                    aria-label="Fermer"
                  >
                    <X size={16} aria-hidden />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto px-4 py-4 scrollbar-thin">
                  {active.guide ? (
                    <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                      {active.guide}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Priorisez cette action avec un conseil métier ou votre expert-comptable :
                      le détail dépend de votre situation (forme juridique, financement, local).
                    </p>
                  )}
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </section>
  );
}
