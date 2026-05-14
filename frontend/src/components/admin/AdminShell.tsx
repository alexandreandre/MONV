"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { LayoutDashboard, GitBranch, ScrollText, Settings2, Workflow } from "lucide-react";

const NAV = [
  { href: "/admin", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/admin/modes", label: "Modes & agents", icon: Workflow },
  { href: "/admin/versions", label: "Versions", icon: GitBranch },
  { href: "/admin/logs", label: "Exécutions", icon: ScrollText },
  { href: "/admin/settings", label: "Paramètres", icon: Settings2 },
];

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-56 shrink-0 border-r border-border md:flex md:flex-col">
        <div className="border-b border-border px-4 py-4">
          <Link href="/admin" className="font-semibold tracking-tight">
            MONV Admin
          </Link>
          <p className="mt-1 text-xs text-muted-foreground">Pilote des agents IA</p>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 p-2">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/admin" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
              >
                <Icon className="size-4 shrink-0 opacity-80" aria-hidden />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-3 text-xs text-muted-foreground">
          <Link href="/" className="underline-offset-4 hover:underline">
            Retour à l’app
          </Link>
        </div>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
