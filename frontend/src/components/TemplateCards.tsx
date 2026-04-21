"use client";

import {
  Rocket,
  Factory,
  Building,
  Briefcase,
  UtensilsCrossed,
  Wallet,
  Monitor,
  Truck,
  Calculator,
  Megaphone,
  Scale,
  ArrowRight,
  Activity,
  Hotel,
  BarChart3,
} from "lucide-react";
import type { Template } from "@/lib/api";

const ICONS: Record<string, React.ReactNode> = {
  chart: <BarChart3 size={16} />,
  hotel: <Hotel size={16} />,
  activity: <Activity size={16} />,
  rocket: <Rocket size={16} />,
  factory: <Factory size={16} />,
  building: <Building size={16} />,
  briefcase: <Briefcase size={16} />,
  utensils: <UtensilsCrossed size={16} />,
  wallet: <Wallet size={16} />,
  monitor: <Monitor size={16} />,
  truck: <Truck size={16} />,
  calculator: <Calculator size={16} />,
  megaphone: <Megaphone size={16} />,
  scale: <Scale size={16} />,
};

interface Props {
  templates: Template[];
  onSelect: (query: string) => void;
  /** Dans un panneau parent déjà centré : pas de max-width supplémentaire. */
  nested?: boolean;
}

export default function TemplateCards({
  templates,
  onSelect,
  nested = false,
}: Props) {
  return (
    <div
      className={`grid grid-cols-1 sm:grid-cols-2 gap-2 ${
        nested ? "w-full" : "max-w-3xl mx-auto"
      }`}
    >
      {templates.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t.query)}
          className="group flex items-start gap-3 text-left rounded-lg border border-border bg-card px-4 py-3.5 hover:border-border hover:bg-muted/50 min-h-[44px]"
        >
          <span className="text-muted-foreground mt-0.5 flex-shrink-0 group-hover:text-muted-foreground">
            {ICONS[t.icon] || <Building size={16} />}
          </span>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm text-muted-foreground group-hover:text-foreground">
              {t.title}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
              {t.description}
            </p>
          </div>
          <ArrowRight
            size={14}
            className="mt-1 flex-shrink-0 text-muted-foreground opacity-40 group-hover:opacity-70"
          />
        </button>
      ))}
    </div>
  );
}
