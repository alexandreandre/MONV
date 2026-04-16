"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Compass } from "lucide-react";
import { AGENT_META } from "@/lib/agents";
import type { ProjectFolder } from "@/lib/api";

interface Props {
  onBack: () => void;
  /**
   * `attachFolderId` : id d’un projet existant, ou `null` pour en créer un nouveau (défaut).
   */
  onSubmit: (pitch: string, attachFolderId: string | null) => void;
  projectFolders?: ProjectFolder[];
  disabled?: boolean;
  loading?: boolean;
}

const EXAMPLE_PITCHES: { label: string; query: string }[] = [
  {
    label: "Restaurant japonais premium à Lyon",
    query:
      "Je veux ouvrir un restaurant japonais haut de gamme à Lyon, avec service à table, livraison locale et vente en ligne de sakés rares importés.",
  },
  {
    label: "Boutique de vêtements éthiques",
    query:
      "Je lance une boutique de vêtements éthiques à Bordeaux pour une clientèle 25-45 ans urbaine, avec une boutique physique et un site e-commerce.",
  },
  {
    label: "Coworking familial en Normandie",
    query:
      "Je veux créer un espace de coworking avec garderie intégrée à Caen pour les jeunes parents entrepreneurs, en location à la journée ou au mois.",
  },
  {
    label: "Atelier d'impression 3D B2B",
    query:
      "Je monte un atelier d'impression 3D B2B à Toulouse pour produire des prototypes et petites séries pour PME industrielles locales.",
  },
];

/**
 * Écran d'accueil de l'agent Atelier. Exposé comme `Page = "atelier"` dans
 * page.tsx quand l'utilisateur clique sur la carte hero.
 */
export default function AgentWelcome({
  onBack,
  onSubmit,
  projectFolders = [],
  disabled = false,
  loading = false,
}: Props) {
  const meta = AGENT_META.atelier;
  const [pitch, setPitch] = useState("");
  /** "" = nouveau projet (comportement par défaut côté API). */
  const [attachFolderId, setAttachFolderId] = useState("");

  const canSubmit = pitch.trim().length >= 20 && !disabled && !loading;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const fid = attachFolderId.trim();
    onSubmit(pitch.trim(), fid ? fid : null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-y-auto scrollbar-thin">
      <div className="max-w-3xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 text-xs font-medium text-gray-500 hover:text-white border border-transparent hover:border-white/[0.08] rounded-lg px-2 py-1.5 -ml-2 transition-colors mb-8 focus-visible:ring-2 focus-visible:ring-teal-400/40 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-0"
        >
          <ArrowLeft size={14} aria-hidden />
          Retour à l&apos;accueil
        </button>

        <div className="rounded-xl border border-white/[0.08] bg-surface-1 mb-6 sm:mb-8 overflow-hidden">
          <div className="border-l-[3px] border-teal-600/70 px-5 sm:px-8 py-7 sm:py-9">
            <div className="flex items-start gap-4 mb-6">
              <div
                className="flex-shrink-0 w-11 h-11 sm:w-12 sm:h-12 rounded-lg border border-white/[0.08] bg-teal-950/50 flex items-center justify-center text-teal-200/95"
                aria-hidden
              >
                <Compass size={20} strokeWidth={2} />
              </div>
              <div className="min-w-0 pt-0.5">
                <p className="text-[11px] font-medium tracking-wide text-gray-500 mb-1">
                  Atelier
                </p>
                <h1 className="text-xl sm:text-2xl font-semibold text-white leading-snug tracking-tight">
                  Parcours guidé — du pitch au dossier
                </h1>
              </div>
            </div>

            <p className="text-sm text-gray-400 leading-relaxed max-w-xl">
              Quelques phrases sur le projet, puis 4 questions. Livrable : business
              model, flux, et{" "}
              <span className="text-gray-200">tableaux d&rsquo;entreprises</span>{" "}
              (fournisseurs, clients, concurrents, prestataires) à partir de données
              publiques.
            </p>

            <div className="mt-6 rounded-lg border border-white/[0.06] bg-surface-2/80 px-4 py-3">
              <label
                htmlFor="atelier-projet-rattachement"
                className="block text-xs font-medium text-gray-500 mb-2"
              >
                Projet MONV (dossier)
              </label>
              <select
                id="atelier-projet-rattachement"
                value={attachFolderId}
                onChange={(e) => setAttachFolderId(e.target.value)}
                disabled={disabled || loading}
                className="w-full rounded-lg border border-white/[0.1] bg-surface-0 px-3 py-2.5 text-sm text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/30 disabled:opacity-50"
              >
                <option value="">Nouveau projet (par défaut)</option>
                {projectFolders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-[11px] text-gray-500 leading-relaxed">
                Par défaut, un <span className="text-gray-400">nouveau</span> projet
                est créé pour cette session Atelier. Choisis un projet existant pour
                tout regrouper au même endroit.
              </p>
            </div>

            <div className="mt-7">
              <label
                htmlFor="pitch"
                className="block text-xs font-medium text-gray-500 mb-2"
              >
                Description du projet
              </label>
              <textarea
                id="pitch"
                value={pitch}
                onChange={(e) => setPitch(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={disabled || loading}
                rows={5}
                placeholder={meta.placeholder}
                className="w-full bg-surface-2 border border-white/[0.08] rounded-lg px-4 py-3.5 text-sm text-white placeholder-gray-600 focus:outline-none focus-visible:border-teal-600/45 focus-visible:ring-2 focus-visible:ring-teal-600/20 resize-none leading-relaxed disabled:opacity-60"
              />
              <div className="mt-4 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
                <p className="text-[11px] text-gray-600 leading-relaxed max-w-md">
                  Plus tu donnes de contexte (secteur, ville, cible), meilleur
                  sera le dossier.{" "}
                  <kbd className="px-1.5 py-0.5 rounded border border-white/[0.08] text-[10px] text-gray-500 font-sans not-italic">
                    ⌘ + Entrée
                  </kbd>{" "}
                  pour envoyer.
                </p>
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!canSubmit}
                  className={`inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium min-h-[44px] shrink-0 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-1 ${
                    canSubmit
                      ? "bg-white text-gray-950 hover:bg-gray-100 focus-visible:ring-teal-500/35"
                      : "bg-white/[0.06] text-gray-600 cursor-not-allowed focus-visible:ring-0"
                  }`}
                >
                  {loading ? "Analyse en cours…" : "Lancer l'Atelier"}
                  {!loading && <ArrowRight size={15} aria-hidden />}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">
            Formulations types (à adapter)
          </p>
          <ul className="flex flex-col gap-1.5">
            {EXAMPLE_PITCHES.map((ex) => (
              <li key={ex.label}>
                <button
                  type="button"
                  disabled={disabled || loading}
                  onClick={() => setPitch(ex.query)}
                  className="w-full text-left rounded-lg border border-white/[0.06] bg-surface-1 px-3 py-2.5 hover:border-white/[0.12] hover:bg-surface-2 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-teal-500/25 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-0"
                >
                  <p className="text-sm text-gray-200 leading-snug">{ex.label}</p>
                  <p className="text-[11px] text-gray-600 mt-1 line-clamp-2 leading-snug">
                    {ex.query}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-8 rounded-lg border border-white/[0.06] bg-surface-2 px-4 py-3.5 flex items-start gap-3">
          <Compass
            size={14}
            className="text-teal-200/80 flex-shrink-0 mt-0.5"
            aria-hidden
          />
          <p className="text-xs text-gray-400 leading-relaxed">
            L&rsquo;Atelier enchaîne plusieurs recherches MONV dans une même session
            (une recherche par type d&rsquo;entreprise repéré). Export comme une
            recherche classique ; crédits débités à l&rsquo;export.
          </p>
        </div>
      </div>
    </div>
  );
}
