"use client";

import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Compass,
  Factory,
  Hotel,
  ShoppingBag,
  Sparkles,
  Utensils,
} from "lucide-react";
import { AGENT_META } from "@/lib/agents";

interface Props {
  onBack: () => void;
  onSubmit: (pitch: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

const EXAMPLE_PITCHES: { icon: typeof Utensils; label: string; query: string }[] = [
  {
    icon: Utensils,
    label: "Restaurant japonais premium à Lyon",
    query:
      "Je veux ouvrir un restaurant japonais haut de gamme à Lyon, avec service à table, livraison locale et vente en ligne de sakés rares importés.",
  },
  {
    icon: ShoppingBag,
    label: "Boutique de vêtements éthiques",
    query:
      "Je lance une boutique de vêtements éthiques à Bordeaux pour une clientèle 25-45 ans urbaine, avec une boutique physique et un site e-commerce.",
  },
  {
    icon: Hotel,
    label: "Coworking familial en Normandie",
    query:
      "Je veux créer un espace de coworking avec garderie intégrée à Caen pour les jeunes parents entrepreneurs, en location à la journée ou au mois.",
  },
  {
    icon: Factory,
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
  disabled = false,
  loading = false,
}: Props) {
  const meta = AGENT_META.atelier;
  const Icon = meta.icon;
  const [pitch, setPitch] = useState("");

  const canSubmit = pitch.trim().length >= 20 && !disabled && !loading;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit(pitch.trim());
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
          className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors mb-6"
        >
          <ArrowLeft size={14} />
          Retour
        </button>

        <div className="rounded-2xl border border-white/[0.06] bg-surface-1 overflow-hidden mb-6 sm:mb-8">
          <div
            className={`h-1 w-full bg-gradient-to-r ${meta.gradientFrom} ${meta.gradientTo} opacity-60`}
          />

          <div className="px-5 sm:px-8 py-7 sm:py-9">
            <div className="flex items-start gap-4 mb-5">
              <div
                className={`flex-shrink-0 w-11 h-11 rounded-xl bg-gradient-to-br ${meta.gradientFrom} ${meta.gradientTo} flex items-center justify-center text-white`}
              >
                <Icon size={20} />
              </div>
              <div>
                <span
                  className={`inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.1em] ${meta.accentText}`}
                >
                  <Sparkles size={10} />
                  Agent Atelier
                </span>
                <h1 className="text-xl sm:text-2xl font-bold text-white leading-tight mt-1">
                  Concevons ton entreprise
                </h1>
              </div>
            </div>

            <p className="text-sm text-gray-400 leading-relaxed max-w-xl">
              Décris ton projet en quelques phrases. Je te poserai 4 questions
              courtes, puis je produirai un dossier complet : business model,
              cartographie des flux, et surtout des{" "}
              <span className="text-gray-200">
                tableaux d&rsquo;entreprises réelles
              </span>{" "}
              à contacter (fournisseurs, clients, concurrents, prestataires).
            </p>

            <div className="mt-6">
              <label
                htmlFor="pitch"
                className="block text-[11px] font-medium uppercase tracking-[0.1em] text-gray-500 mb-2"
              >
                Ton projet
              </label>
              <textarea
                id="pitch"
                value={pitch}
                onChange={(e) => setPitch(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={disabled || loading}
                rows={5}
                placeholder={meta.placeholder}
                className="w-full bg-surface-2 border border-white/[0.08] rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-white/[0.22] transition-colors resize-none leading-relaxed"
              />
              <div className="mt-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <p className="text-[11px] text-gray-600">
                  Plus tu donnes de contexte (secteur, ville, cible), meilleur
                  sera le dossier.{" "}
                  <kbd className="px-1 py-0.5 rounded border border-white/[0.06] text-[10px] text-gray-500">
                    ⌘ + Entrée
                  </kbd>{" "}
                  pour envoyer.
                </p>
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!canSubmit}
                  className={`inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition-colors min-h-[44px] ${
                    canSubmit
                      ? "bg-white text-gray-950 hover:bg-gray-200 active:bg-gray-300"
                      : "bg-white/[0.06] text-gray-600 cursor-not-allowed"
                  }`}
                >
                  {loading ? "Analyse en cours…" : "Lancer l'Atelier"}
                  {!loading && <ArrowRight size={15} />}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div>
          <p className="text-[11px] font-medium text-gray-600 uppercase tracking-wider mb-3">
            Ou pars d&rsquo;un exemple
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {EXAMPLE_PITCHES.map((ex) => {
              const ExIcon = ex.icon;
              return (
                <button
                  key={ex.label}
                  type="button"
                  disabled={disabled || loading}
                  onClick={() => setPitch(ex.query)}
                  className="group text-left rounded-xl border border-white/[0.06] bg-surface-1 px-3.5 py-3 hover:border-white/[0.14] hover:bg-surface-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={`flex-shrink-0 w-8 h-8 rounded-lg bg-white/[0.04] group-hover:bg-white/[0.08] flex items-center justify-center ${meta.accentText} transition-colors`}
                    >
                      <ExIcon size={14} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white leading-snug">
                        {ex.label}
                      </p>
                      <p className="text-xs text-gray-500 line-clamp-2 mt-0.5 leading-snug">
                        {ex.query}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-8 rounded-xl border border-white/[0.06] bg-surface-2 px-4 py-3 flex items-start gap-3">
          <Compass size={14} className="text-gray-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-gray-400 leading-relaxed">
            L&rsquo;Atelier lance <span className="text-gray-200">plusieurs</span>{" "}
            recherches MONV en une session (une par type d&rsquo;entreprise
            identifiée). Les résultats s&rsquo;exportent comme une recherche
            normale. Les crédits ne sont débités qu&rsquo;à l&rsquo;export.
          </p>
        </div>
      </div>
    </div>
  );
}
