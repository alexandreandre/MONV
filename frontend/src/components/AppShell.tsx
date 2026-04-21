"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface AppShellProps {
  /** Barre latérale (desktop + drawer géré à l’intérieur). */
  sidebar: React.ReactNode;
  /** Header mobile (md:hidden). */
  mobileHeader?: React.ReactNode;
  /** Topbar desktop (hidden md:flex). */
  desktopTopbar?: React.ReactNode;
  /** Palette de commandes / raccourcis (overlay global). */
  commandPalette?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function AppShell({
  sidebar,
  mobileHeader,
  desktopTopbar,
  commandPalette,
  children,
  className,
}: AppShellProps) {
  return (
    <div
      className={cn(
        "flex h-[100dvh] min-h-0 w-full bg-background text-foreground",
        className
      )}
    >
      {sidebar}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {mobileHeader}
        {desktopTopbar}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {children}
        </div>
      </div>
      {commandPalette}
    </div>
  );
}
