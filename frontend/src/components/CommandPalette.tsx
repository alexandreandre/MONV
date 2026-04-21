"use client";

import * as React from "react";
import {
  Compass,
  CreditCard,
  History,
  MessageSquarePlus,
  Moon,
  Sun,
  Folder,
  MessageSquare,
} from "lucide-react";
import { useTheme } from "next-themes";

import type { Conversation, ProjectFolder } from "@/lib/api";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conversations: Conversation[];
  projectFolders: ProjectFolder[];
  onNewChat: () => void;
  onOpenAtelier: () => void;
  onNavigateDashboard: () => void;
  onNavigateCredits: () => void;
  onSelectConversation: (id: string) => void;
  onSelectProjectFolder: (id: string) => void;
  onLogout: () => void;
  /** Affiche déconnexion (utilisateur connecté ou session en cours). */
  canLogout?: boolean;
}

export function CommandPalette({
  open,
  onOpenChange,
  conversations,
  projectFolders,
  onNewChat,
  onOpenAtelier,
  onNavigateDashboard,
  onNavigateCredits,
  onSelectConversation,
  onSelectProjectFolder,
  onLogout,
  canLogout = true,
}: CommandPaletteProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const run = React.useCallback(
    (fn: () => void) => {
      onOpenChange(false);
      fn();
    },
    [onOpenChange]
  );

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
      if (e.key === "n" && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
        e.preventDefault();
        run(onNewChat);
      }
      if (e.key === "a" && (e.metaKey || e.ctrlKey) && e.shiftKey) {
        e.preventDefault();
        run(onOpenAtelier);
      }
      if (e.key === "," && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        run(onNavigateCredits);
      }
      if (e.key === "?" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const t = e.target as HTMLElement | null;
        if (
          t &&
          (t.tagName === "INPUT" ||
            t.tagName === "TEXTAREA" ||
            t.isContentEditable)
        ) {
          return;
        }
        e.preventDefault();
        onOpenChange(true);
      }
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, [
    open,
    onOpenChange,
    onNewChat,
    onOpenAtelier,
    onNavigateCredits,
    onNavigateDashboard,
    run,
  ]);

  const recent = [...conversations]
    .sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
    .slice(0, 12);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="overflow-hidden p-0 sm:max-w-xl"
      >
        <DialogHeader className="sr-only">
          <DialogTitle>Commandes</DialogTitle>
          <DialogDescription>
            Navigation rapide et raccourcis clavier.
          </DialogDescription>
        </DialogHeader>
        <Command className="rounded-lg border-0 shadow-none">
          <CommandInput placeholder="Rechercher une action, une conversation…" />
          <CommandList>
            <CommandEmpty>Aucun résultat.</CommandEmpty>
            <CommandGroup heading="Actions">
              <CommandItem
                onSelect={() => run(onNewChat)}
                keywords={["nouveau", "chat", "recherche"]}
              >
                <MessageSquarePlus className="size-4" />
                Nouvelle recherche
                <CommandShortcut>⌘N</CommandShortcut>
              </CommandItem>
              <CommandItem
                onSelect={() => run(onOpenAtelier)}
                keywords={["atelier", "agent", "entreprise"]}
              >
                <Compass className="size-4" />
                Ouvrir l’Atelier
                <CommandShortcut>⇧⌘A</CommandShortcut>
              </CommandItem>
              <CommandItem
                onSelect={() => run(onNavigateDashboard)}
                keywords={["historique", "tableau"]}
              >
                <History className="size-4" />
                Historique
              </CommandItem>
              <CommandItem
                onSelect={() => run(onNavigateCredits)}
                keywords={["crédits", "paiement"]}
              >
                <CreditCard className="size-4" />
                Crédits
                <CommandShortcut>⌘,</CommandShortcut>
              </CommandItem>
              <CommandItem
                onSelect={() =>
                  run(() =>
                    setTheme(
                      mounted && theme === "dark" ? "light" : "dark"
                    )
                  )
                }
                keywords={["thème", "clair", "sombre"]}
              >
                {mounted && theme === "dark" ? (
                  <Sun className="size-4" />
                ) : (
                  <Moon className="size-4" />
                )}
                Basculer clair / sombre
              </CommandItem>
            </CommandGroup>
            {projectFolders.length > 0 && (
              <>
                <CommandSeparator />
                <CommandGroup heading="Projets">
                  {projectFolders.map((f) => (
                    <CommandItem
                      key={f.id}
                      onSelect={() => run(() => onSelectProjectFolder(f.id))}
                      keywords={[f.name]}
                    >
                      <Folder className="size-4" />
                      {f.name}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}
            {recent.length > 0 && (
              <>
                <CommandSeparator />
                <CommandGroup heading="Conversations récentes">
                  {recent.map((c) => (
                    <CommandItem
                      key={c.id}
                      onSelect={() => run(() => onSelectConversation(c.id))}
                      keywords={[c.title]}
                    >
                      <MessageSquare className="size-4" />
                      <span className="truncate">{c.title}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}
            {canLogout ? (
              <>
                <CommandSeparator />
                <CommandGroup heading="Session">
                  <CommandItem
                    onSelect={() => run(onLogout)}
                    keywords={["déconnexion", "logout"]}
                    className="text-destructive"
                  >
                    Déconnexion
                  </CommandItem>
                </CommandGroup>
              </>
            ) : null}
          </CommandList>
        </Command>
        <p className="border-t px-3 py-2 text-[11px] text-muted-foreground">
          Raccourcis : <kbd className="rounded border bg-muted px-1">⌘K</kbd>{" "}
          palette · <kbd className="rounded border bg-muted px-1">⌘N</kbd>{" "}
          nouveau · <kbd className="rounded border bg-muted px-1">⇧⌘A</kbd>{" "}
          Atelier · <kbd className="rounded border bg-muted px-1">⌘,</kbd>{" "}
          crédits · <kbd className="rounded border bg-muted px-1">?</kbd> aide
        </p>
      </DialogContent>
    </Dialog>
  );
}
