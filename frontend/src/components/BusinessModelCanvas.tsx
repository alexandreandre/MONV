"use client";

import {
  Award,
  Boxes,
  Coins,
  Flag,
  Handshake,
  Heart,
  Receipt,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import type { BusinessCanvas } from "@/lib/api";

interface Props {
  canvas: BusinessCanvas;
}

function bulletList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map((x) => String(x).trim()).filter(Boolean);
}

/**
 * Mise en page inspirée du Business Model Canvas de Strategyzer, mais
 * restyled pour correspondre au design system dark de MONV.
 *
 * Grille responsive :
 *   - Mobile : 9 blocs empilés
 *   - Desktop : 5 colonnes × 2 rangées, + structure de coûts / revenus
 *     en full-width sur une 3e rangée (comme le BMC d'origine).
 */
export default function BusinessModelCanvas({ canvas }: Props) {
  const c = canvas ?? ({} as BusinessCanvas);
  return (
    <div className="rounded-2xl border border-border bg-card p-3 sm:p-4">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-2 sm:gap-3">
        <Cell
          title="Partenaires clés"
          icon={Handshake}
          items={bulletList(c.partenaires_cles)}
          accent="bg-sky-500/5 border-sky-500/15"
          className="md:row-span-2"
        />
        <div className="md:col-span-1 flex flex-col gap-2 sm:gap-3">
          <Cell
            title="Activités clés"
            icon={Workflow}
            items={bulletList(c.activites_cles)}
            accent="bg-emerald-500/5 border-emerald-500/15"
          />
          <Cell
            title="Ressources clés"
            icon={Boxes}
            items={bulletList(c.ressources_cles)}
            accent="bg-emerald-500/5 border-emerald-500/15"
          />
        </div>
        <Cell
          title="Proposition de valeur"
          icon={Award}
          items={bulletList(c.proposition_valeur)}
          accent="bg-teal-500/8 border-teal-500/20"
          emphasize
          className="md:row-span-2"
        />
        <div className="md:col-span-1 flex flex-col gap-2 sm:gap-3">
          <Cell
            title="Relation client"
            icon={Heart}
            items={bulletList(c.relation_client)}
            accent="bg-teal-500/5 border-teal-500/12"
          />
          <Cell
            title="Canaux"
            icon={Flag}
            items={bulletList(c.canaux)}
            accent="bg-teal-500/5 border-teal-500/12"
          />
        </div>
        <Cell
          title="Segments clients"
          icon={Users}
          items={bulletList(c.segments_clients)}
          accent="bg-amber-500/5 border-amber-500/15"
          className="md:row-span-2"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 sm:gap-3 mt-2 sm:mt-3">
        <Cell
          title="Structure de coûts"
          icon={Receipt}
          items={bulletList(c.structure_couts)}
          accent="bg-slate-500/5 border-slate-500/15"
        />
        <Cell
          title="Sources de revenus"
          icon={Coins}
          items={bulletList(c.sources_revenus)}
          accent="bg-emerald-500/6 border-emerald-500/15"
        />
      </div>
    </div>
  );
}

interface CellProps {
  title: string;
  icon: LucideIcon;
  items: string[];
  accent?: string;
  emphasize?: boolean;
  className?: string;
}

function Cell({
  title,
  icon: Icon,
  items,
  accent = "bg-white/[0.02] border-border",
  emphasize = false,
  className = "",
}: CellProps) {
  const list = Array.isArray(items) ? items : [];
  return (
    <div
      className={`rounded-xl border ${accent} px-3 py-3 min-h-[110px] flex flex-col ${className}`}
    >
      <div className="flex items-center gap-1.5 mb-2">
        <Icon
          size={12}
          className={emphasize ? "text-teal-300" : "text-muted-foreground"}
        />
        <h4
          className={`text-[10px] font-semibold uppercase tracking-[0.1em] ${
            emphasize ? "text-teal-200" : "text-muted-foreground"
          }`}
        >
          {title}
        </h4>
      </div>
      {list.length === 0 ? (
        <p className="text-[11px] text-muted-foreground italic">Non précisé</p>
      ) : (
        <ul className="space-y-1 text-xs text-muted-foreground leading-snug">
          {list.map((item, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <span className="mt-1 w-1 h-1 rounded-full bg-gray-500 flex-shrink-0" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
