"use client";

import * as React from "react";
import {
  ChevronRight,
  CreditCard,
  Compass,
  LogOut,
  Moon,
  Search,
  Sun,
} from "lucide-react";
import { useTheme } from "next-themes";

import type { User } from "@/lib/api";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

export type BreadcrumbSegment = { label: string; current?: boolean };

interface AppTopbarProps {
  user: User | null;
  sessionHint: boolean;
  segments: BreadcrumbSegment[];
  onOpenCommand: () => void;
  onNavigateCredits: () => void;
  onOpenAtelier: () => void;
  onLogout: () => void;
  className?: string;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function AppTopbar({
  user,
  sessionHint,
  segments,
  onOpenCommand,
  onNavigateCredits,
  onOpenAtelier,
  onLogout,
  className,
}: AppTopbarProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const creditsLabel =
    user == null
      ? "—"
      : user.credits_unlimited
        ? "∞"
        : String(user.credits);

  return (
    <header
      className={cn(
        "sticky top-0 z-20 hidden h-14 shrink-0 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:flex",
        className
      )}
    >
      <nav aria-label="Fil d’ariane" className="flex min-w-0 flex-1 items-center gap-1 text-sm">
        {segments.map((s, i) => (
          <React.Fragment key={`${s.label}-${i}`}>
            {i > 0 && (
              <ChevronRight
                className="size-4 shrink-0 text-muted-foreground"
                aria-hidden
              />
            )}
            <span
              className={cn(
                "truncate font-medium",
                s.current ? "text-foreground" : "text-muted-foreground"
              )}
            >
              {s.label}
            </span>
          </React.Fragment>
        ))}
      </nav>

      <div className="flex shrink-0 items-center gap-1.5">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="hidden lg:inline-flex gap-2 font-mono text-xs text-muted-foreground"
          onClick={onOpenCommand}
        >
          <Search className="size-4" aria-hidden />
          Rechercher
          <kbd className="pointer-events-none hidden rounded border bg-muted px-1.5 py-0.5 font-sans text-[10px] font-medium sm:inline">
            ⌘K
          </kbd>
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onOpenCommand}
          aria-label="Ouvrir la palette de commandes"
        >
          <Search className="size-4" />
        </Button>

        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onOpenAtelier}
          aria-label="Ouvrir l’Atelier"
          title="Atelier"
        >
          <Compass className="size-4" />
        </Button>

        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="hidden font-mono text-xs sm:inline-flex"
          onClick={onNavigateCredits}
          title="Crédits"
        >
          {creditsLabel}
        </Button>

        <Separator orientation="vertical" className="mx-1 h-6" />

        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={
            mounted && theme === "dark"
              ? "Passer en thème clair"
              : "Passer en thème sombre"
          }
          onClick={() =>
            setTheme(mounted && theme === "dark" ? "light" : "dark")
          }
        >
          {mounted && theme === "dark" ? (
            <Sun className="size-4" />
          ) : (
            <Moon className="size-4" />
          )}
        </Button>

        {(user || sessionHint) && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="rounded-full"
                aria-label="Menu compte"
              >
                <Avatar className="size-8">
                  <AvatarFallback className="text-xs font-semibold">
                    {user ? initials(user.name) : "…"}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {user && (
                <>
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                      <p className="text-sm font-medium leading-none">
                        {user.name}
                      </p>
                      <p className="text-xs leading-none text-muted-foreground">
                        {user.email}
                      </p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                </>
              )}
              <DropdownMenuItem onClick={onNavigateCredits}>
                <CreditCard className="mr-2 size-4" />
                Crédits
                {user && (
                  <span className="ml-auto font-mono text-xs text-muted-foreground">
                    {user.credits_unlimited ? "∞" : user.credits}
                  </span>
                )}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onOpenAtelier}>
                <Compass className="mr-2 size-4" />
                Atelier
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={onLogout}
                className="text-destructive focus:text-destructive"
              >
                <LogOut className="mr-2 size-4" />
                Déconnexion
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  );
}
