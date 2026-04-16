"use client";

import { Menu, CreditCard, Compass } from "lucide-react";
import type { User } from "@/lib/api";

interface Props {
  user: User | null;
  onMenuOpen: () => void;
  onNavigateCredits: () => void;
  /** Accès rapide à l’agent Atelier (landing / chat). */
  onOpenAtelier?: () => void;
}

export default function MobileHeader({
  user,
  onMenuOpen,
  onNavigateCredits,
  onOpenAtelier,
}: Props) {
  return (
    <div className="md:hidden sticky top-0 z-30 flex items-center gap-2 px-2 py-2.5 bg-surface-0/90 backdrop-blur-md border-b border-white/[0.06]">
      <button
        type="button"
        onClick={onMenuOpen}
        className="p-2 -ml-0.5 rounded-lg hover:bg-white/[0.06] active:bg-white/[0.1] text-gray-400 transition-colors shrink-0"
        aria-label="Ouvrir le menu"
      >
        <Menu size={20} />
      </button>

      <span className="text-sm font-bold tracking-tight text-white flex-1 text-center min-w-0 truncate">
        MONV
      </span>

      <div className="flex items-center shrink-0 gap-0.5">
        {onOpenAtelier && (
          <button
            type="button"
            onClick={onOpenAtelier}
            className="p-2 rounded-lg text-teal-300/90 hover:bg-teal-500/15 active:bg-teal-500/25 transition-colors"
            aria-label="Ouvrir l’agent Atelier"
          >
            <Compass size={18} strokeWidth={2.25} />
          </button>
        )}
        <button
          type="button"
          onClick={onNavigateCredits}
          className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-gray-500 hover:bg-white/[0.06] active:bg-white/[0.1] transition-colors"
          aria-label="Crédits"
        >
          <CreditCard size={15} />
          <span className="text-xs tabular-nums font-medium min-w-[1.25rem] inline-flex justify-end">
            {user ? (
              user.credits_unlimited ? (
                "∞"
              ) : (
                user.credits
              )
            ) : (
              <span
                className="h-3 w-7 rounded bg-white/[0.08] animate-pulse"
                aria-hidden
              />
            )}
          </span>
        </button>
      </div>
    </div>
  );
}
