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
              className={`flex-shrink-0 inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors min-h-[36px] ${
                active
                  ? meta.accent
                  : "border-white/[0.08] text-gray-500 hover:text-gray-300 hover:border-white/[0.16]"
              } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
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
            className={`flex flex-col items-start gap-1 rounded-xl border px-3 py-3 text-left transition-all min-h-[44px] ${
              active
                ? meta.accent + " shadow-[0_0_0_1px_rgba(255,255,255,0.04)]"
                : "border-white/[0.06] bg-surface-1 hover:border-white/[0.12] hover:bg-surface-2 text-gray-400"
            } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            <span className="inline-flex items-center gap-1.5 text-sm font-medium">
              <Icon size={14} />
              {meta.label}
            </span>
            <span className="text-[11px] text-gray-500 line-clamp-2 leading-snug">
              {meta.description}
            </span>
          </button>
        );
      })}
    </div>
  );
}
