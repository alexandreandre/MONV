"use client";

import { MODE_META, MODES, type Mode } from "@/lib/modes";

interface Props {
  value: Mode;
  onChange: (mode: Mode) => void;
  /** "landing" : 2x2 sur mobile, 4 colonnes au-dessus de sm.
   *  "compact" : pills horizontales scrollables, pour le header ou un encart court. */
  variant?: "landing" | "compact";
  disabled?: boolean;
}

export default function ModeSelector({
  value,
  onChange,
  variant = "landing",
  disabled = false,
}: Props) {
  if (variant === "compact") {
    return (
      <div
        role="radiogroup"
        aria-label="Mode d'usage MONV"
        className="flex gap-1.5 overflow-x-auto scrollbar-thin -mx-1 px-1 py-1"
      >
        {MODES.map((m) => {
          const meta = MODE_META[m];
          const Icon = meta.icon;
          const active = value === m;
          return (
            <button
              key={m}
              role="radio"
              aria-checked={active}
              type="button"
              disabled={disabled}
              onClick={() => onChange(m)}
              className={`min-h-[36px] flex-shrink-0 inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? meta.accent
                  : "border-border text-muted-foreground hover:border-border hover:bg-muted/60 hover:text-foreground"
              } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
            >
              <Icon size={13} />
              {meta.label}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      role="radiogroup"
      aria-label="Mode d'usage MONV"
      className="grid grid-cols-2 sm:grid-cols-4 gap-2 w-full"
    >
      {MODES.map((m) => {
        const meta = MODE_META[m];
        const Icon = meta.icon;
        const active = value === m;
        return (
          <button
            key={m}
            role="radio"
            aria-checked={active}
            type="button"
            disabled={disabled}
            onClick={() => onChange(m)}
            className={`flex min-h-[44px] flex-col items-start gap-1 rounded-xl border px-3 py-3 text-left transition-all ${
              active
                ? meta.accent + " shadow-sm ring-1 ring-border/60"
                : "border-border bg-card text-muted-foreground hover:border-border hover:bg-accent/40 hover:text-foreground"
            } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
          >
            <span className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
              <Icon size={14} />
              {meta.label}
            </span>
            <span className="line-clamp-2 text-[11px] leading-snug text-muted-foreground">
              {meta.description}
            </span>
          </button>
        );
      })}
    </div>
  );
}
