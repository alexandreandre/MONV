"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Banknote, Info, Package } from "lucide-react";
import type { FlowEdge, FlowMap } from "@/lib/api";

interface Props {
  flows: FlowMap;
}

type FlowLayer = "valeur" | "financier" | "information";

const LAYERS: {
  id: FlowLayer;
  label: string;
  icon: typeof Package;
  accent: string;
  badge: string;
}[] = [
  {
    id: "valeur",
    label: "Flux de valeur",
    icon: Package,
    accent: "border-emerald-500/30 bg-emerald-500/5",
    badge: "bg-emerald-500/15 text-emerald-300",
  },
  {
    id: "financier",
    label: "Flux financiers",
    icon: Banknote,
    accent: "border-amber-500/30 bg-amber-500/5",
    badge: "bg-amber-500/15 text-amber-300",
  },
  {
    id: "information",
    label: "Flux d'information",
    icon: Info,
    accent: "border-sky-500/30 bg-sky-500/5",
    badge: "bg-sky-500/15 text-sky-300",
  },
];

/**
 * Cartographie des flux — rendu « chips d'acteurs + liste d'arcs ».
 * Pas de SVG généré (contrainte produit). Chaque arc est une carte
 * "from → to" lisible, avec onglets pour basculer entre les 3 couches.
 */
export default function FlowDiagram({ flows }: Props) {
  const [active, setActive] = useState<FlowLayer>("valeur");

  const edges = useMemo<FlowEdge[]>(() => {
    if (active === "valeur") return flows.flux_valeur || [];
    if (active === "financier") return flows.flux_financiers || [];
    return flows.flux_information || [];
  }, [active, flows]);

  const activeMeta = LAYERS.find((l) => l.id === active)!;

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-surface-1 p-4">
      {flows.acteurs.length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-gray-500 mb-2">
            Acteurs
          </p>
          <div className="flex flex-wrap gap-1.5">
            {flows.acteurs.map((a, i) => (
              <span
                key={i}
                className="inline-flex items-center rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[11px] text-gray-300"
              >
                {a}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 mb-3">
        {LAYERS.map((l) => {
          const Icon = l.icon;
          const isActive = l.id === active;
          return (
            <button
              key={l.id}
              type="button"
              onClick={() => setActive(l.id)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium border transition-colors ${
                isActive
                  ? l.accent + " text-white"
                  : "border-white/[0.06] bg-transparent text-gray-500 hover:text-gray-300 hover:border-white/[0.12]"
              }`}
            >
              <Icon size={12} />
              {l.label}
            </button>
          );
        })}
      </div>

      {edges.length === 0 ? (
        <p className="text-xs text-gray-500 italic py-6 text-center">
          Aucun flux {activeMeta.label.toLowerCase()} identifié.
        </p>
      ) : (
        <ul className="space-y-2">
          {edges.map((edge, i) => (
            <li
              key={i}
              className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-lg border border-white/[0.05] bg-surface-2 px-3 py-2.5"
            >
              <div className="flex items-center gap-2 text-sm text-gray-200 min-w-0 flex-1">
                <span className="truncate font-medium">{edge.origine}</span>
                <ArrowRight
                  size={14}
                  className={`flex-shrink-0 ${activeMeta.badge.split(" ").pop()}`}
                />
                <span className="truncate font-medium">{edge.destination}</span>
              </div>
              {edge.label && (
                <span
                  className={`inline-flex items-center self-start sm:self-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ${activeMeta.badge}`}
                >
                  {edge.label}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
