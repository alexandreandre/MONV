"use client";

import { Menu, CreditCard } from "lucide-react";
import type { User } from "@/lib/api";

interface Props {
  user: User;
  onMenuOpen: () => void;
  onNavigateCredits: () => void;
}

export default function MobileHeader({
  user,
  onMenuOpen,
  onNavigateCredits,
}: Props) {
  return (
    <div className="md:hidden sticky top-0 z-30 flex items-center justify-between px-3 py-2.5 bg-surface-0/90 backdrop-blur-md border-b border-white/[0.06]">
      <button
        onClick={onMenuOpen}
        className="p-2 -ml-1 rounded-lg hover:bg-white/[0.06] active:bg-white/[0.1] text-gray-400 transition-colors"
        aria-label="Ouvrir le menu"
      >
        <Menu size={20} />
      </button>

      <span className="text-sm font-bold tracking-tight text-white">MONV</span>

      <button
        onClick={onNavigateCredits}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-gray-500 hover:bg-white/[0.06] active:bg-white/[0.1] transition-colors"
        aria-label="Crédits"
      >
        <CreditCard size={15} />
        <span className="text-xs tabular-nums font-medium">
          {user.credits_unlimited ? "∞" : user.credits}
        </span>
      </button>
    </div>
  );
}
