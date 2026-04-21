"use client";

import { Menu, CreditCard, Compass, Search } from "lucide-react";
import type { User } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  user: User | null;
  onMenuOpen: () => void;
  onNavigateCredits: () => void;
  /** Accès rapide à l’agent Atelier (landing / chat). */
  onOpenAtelier?: () => void;
  /** Ouvre la palette de commandes (⌘K). */
  onOpenCommand?: () => void;
}

export default function MobileHeader({
  user,
  onMenuOpen,
  onNavigateCredits,
  onOpenAtelier,
  onOpenCommand,
}: Props) {
  return (
    <div
      className={cn(
        "sticky top-0 z-30 flex items-center gap-2 border-b border-border bg-background/90 px-2 py-2 backdrop-blur-md supports-[backdrop-filter]:bg-background/80 md:hidden"
      )}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={onMenuOpen}
        className="-ml-0.5 shrink-0"
        aria-label="Ouvrir le menu"
      >
        <Menu className="size-5" />
      </Button>

      <span className="min-w-0 flex-1 truncate text-center text-sm font-semibold tracking-tight text-foreground">
        MONV
      </span>

      <div className="flex shrink-0 items-center gap-0.5">
        {onOpenCommand && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onOpenCommand}
            aria-label="Rechercher et commandes"
          >
            <Search className="size-[18px]" />
          </Button>
        )}
        {onOpenAtelier && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onOpenAtelier}
            className="text-primary"
            aria-label="Ouvrir l’agent Atelier"
          >
            <Compass className="size-[18px]" strokeWidth={2.25} />
          </Button>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onNavigateCredits}
          className="gap-1 px-2 font-mono text-xs tabular-nums text-muted-foreground"
          aria-label="Crédits"
        >
          <CreditCard className="size-[15px]" />
          {user ? (
            user.credits_unlimited ? (
              "∞"
            ) : (
              user.credits
            )
          ) : (
            <span
              className="inline-block h-3 w-7 animate-pulse rounded bg-muted"
              aria-hidden
            />
          )}
        </Button>
      </div>
    </div>
  );
}
