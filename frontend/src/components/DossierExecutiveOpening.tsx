"use client";

import type { BusinessDossierPayload } from "@/lib/api";

function isPhysicalLocation(raw: string): boolean {
  const t = raw.trim().toLowerCase();
  if (t.length < 2) return false;
  const skip = new Set([
    "-",
    "—",
    "n/a",
    "na",
    "online",
    "remote",
    "digital",
    "100% digital",
    "100% en ligne",
    "en ligne uniquement",
    "uniquement en ligne",
    "national (digital)",
    "international",
    "europe",
    "monde",
    "non",
    "aucune",
    "sans local",
    "saas",
    "web",
  ]);
  if (skip.has(t)) return false;
  if (t.includes("uniquement en ligne") || t.startsWith("100% web")) return false;
  return true;
}

/** Découpe un texte unique en points lisibles sans casser « 1,5 M€ ». */
function expandOrdreLines(raw: string): string[] {
  const t = raw.trim();
  if (!t) return [];
  if (t.includes("\n")) {
    return t
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  // Plusieurs phrases = plusieurs puces (scénario type restau / BP)
  if (t.length > 90) {
    const bySentence = t
      .split(/(?<=[.!?])\s+(?=[\p{Lu}0-9])/u)
      .map((s) => s.trim())
      .filter(Boolean);
    if (bySentence.length >= 2) return bySentence;
  }
  return [t];
}

function buildOrdreRows(synthesis: BusinessDossierPayload["synthesis"]): string[] {
  const ordres = (synthesis.ordres_grandeur ?? []).map((s) => s.trim()).filter(Boolean);
  if (ordres.length > 0) {
    const out: string[] = [];
    for (const line of ordres) {
      if (line.length > 100 && !line.includes("\n")) {
        out.push(...expandOrdreLines(line));
      } else {
        out.push(line);
      }
    }
    return out.slice(0, 14);
  }
  if (synthesis.budget_estimatif?.trim()) {
    return expandOrdreLines(synthesis.budget_estimatif.trim());
  }
  const k = (synthesis.kpis ?? []).map((s) => s.trim()).filter(Boolean).slice(0, 5);
  if (k.length > 0) return k;
  return [];
}

const ORDRES_PLACEHOLDER =
  "Indicateurs à structurer avec votre modèle économique : enveloppe d’investissement, mix de financement, objectifs de CA et de marge, seuil de rentabilité mensuel, besoin en fonds de roulement et hypothèse de trésorerie année 1. Relancez une génération de dossier ou affinez le brief pour enrichir ce bloc.";

const CONSEIL_PLACEHOLDER =
  "Cette semaine, identifiez deux rendez-vous concrets (ex. dispositif d’accompagnement territorial type Initiative / CCI, et un expert-comptable sectoriel). Souvent gratuits ou peu coûteux, ils cadreront financement, charges fixes et montée en charge.";

interface DossierExecutiveOpeningProps {
  brief: BusinessDossierPayload["brief"];
  synthesis: BusinessDossierPayload["synthesis"];
}

export default function DossierExecutiveOpening({
  brief,
  synthesis,
}: DossierExecutiveOpeningProps) {
  const secteur = brief.secteur?.trim();
  const loc = brief.localisation?.trim();
  const showLoc = Boolean(loc && isPhysicalLocation(loc));
  const conseil = (synthesis.conseil_semaine ?? "").trim();

  const ordreRows = buildOrdreRows(synthesis);
  const ordreIsPlaceholder = ordreRows.length === 0;
  const rows = ordreIsPlaceholder ? [ORDRES_PLACEHOLDER] : ordreRows;

  const hasMeta = Boolean(secteur) || showLoc;

  return (
    <section
      className="rounded-2xl border border-white/[0.08] bg-surface-1 px-5 py-5 sm:px-6"
      aria-label="Lecture opérationnelle"
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-gray-500 mb-4">
        Cadrage projet
      </p>

      {hasMeta ? (
        <dl className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
          {secteur ? (
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3.5 py-3">
              <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-500">
                Secteur
              </dt>
              <dd className="mt-1 text-sm font-medium text-gray-100 leading-snug">{secteur}</dd>
            </div>
          ) : null}
          {showLoc ? (
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3.5 py-3">
              <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-500">
                Localisation
              </dt>
              <dd className="mt-1 text-sm font-medium text-gray-100 leading-snug">{loc}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {/* Ordres de grandeur — toujours affiché */}
      <div
        className={`rounded-xl border px-4 py-4 sm:px-5 sm:py-4 ${
          ordreIsPlaceholder
            ? "border-amber-500/15 bg-amber-500/[0.04]"
            : "border-teal-500/20 bg-teal-500/[0.04]"
        }`}
      >
        <div className="mb-3 flex flex-col gap-1 border-b border-white/[0.06] pb-3 sm:flex-row sm:items-end sm:justify-between">
          <h3 className="text-[13px] font-semibold text-gray-100 leading-snug tracking-tight">
            Ordres de grandeur pour votre projet{" "}
            <span className="font-normal text-gray-500">(scénario central)</span>
          </h3>
          <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500 shrink-0">
            Indicatif — à challenger
          </p>
        </div>
        <ul className="space-y-2.5">
          {rows.map((line, i) => (
            <li
              key={i}
              className={`flex gap-3 text-[13px] leading-relaxed [font-variant-numeric:tabular-nums] ${
                ordreIsPlaceholder ? "text-amber-100/90" : "text-gray-200"
              }`}
            >
              <span
                className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${
                  ordreIsPlaceholder ? "bg-amber-400/70" : "bg-teal-400/90"
                }`}
                aria-hidden
              />
              <span className="min-w-0">{line}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Premier conseil concret — toujours affiché */}
      <div className="mt-4 rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-4 sm:px-5 sm:py-4">
        <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-[13px] font-semibold text-gray-100 tracking-tight">
            Premier conseil concret
          </h3>
          <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-teal-400/90">
            Cette semaine
          </span>
        </div>
        <p className="text-[13px] text-gray-200 leading-relaxed">
          {conseil || CONSEIL_PLACEHOLDER}
        </p>
      </div>
    </section>
  );
}
