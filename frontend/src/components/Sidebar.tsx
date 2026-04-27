"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  MessageSquarePlus,
  History,
  CreditCard,
  LogOut,
  ChevronLeft,
  ChevronRight,
  X,
  Compass,
  FolderPlus,
  ChevronDown,
  Folder,
  MoreHorizontal,
  Pencil,
  Trash2,
  ExternalLink,
} from "lucide-react";
import type { Conversation, ProjectFolder, User } from "@/lib/api";
import {
  conversationUrl,
  MONV_CONV_DRAG_TYPE,
  readConversationIdFromDataTransfer,
} from "@/lib/conversationNav";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { normalizeMode, MODE_META, type Mode } from "@/lib/modes";
import { ATELIER_MODE_LABEL } from "@/lib/agents";

const MODE_ORDER: (Mode | "atelier")[] = [
  "prospection",
  "benchmark",
  "rachat",
  "sous_traitant",
  "atelier",
];

const MODE_DISPLAY: Record<string, { label: string; color: string }> = {
  prospection: { label: "Prospection", color: "text-emerald-400" },
  benchmark: { label: "Benchmark", color: "text-amber-400" },
  rachat: { label: "Rachat", color: "text-violet-400" },
  sous_traitant: { label: "Sous-traitant", color: "text-sky-400" },
  atelier: { label: "Atelier", color: "text-primary" },
};

interface Props {
  user: User | null;
  conversations: Conversation[];
  projectFolders: ProjectFolder[];
  conversationsLoading?: boolean;
  currentConvId: string | null;
  /** Projet ouvert (vue type ChatGPT) — surlignage dans la liste. */
  activeProjectFolderId: string | null;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onSelectProjectFolder: (folderId: string) => void;
  onCreateProjectFolder: (name: string) => Promise<void>;
  onRenameProjectFolder: (id: string, name: string) => Promise<void>;
  onDeleteProjectFolder: (id: string) => Promise<void>;
  onMoveConversationToFolder: (
    conversationId: string,
    folderId: string | null
  ) => Promise<boolean>;
  onNavigate: (page: "chat" | "dashboard" | "credits" | "atelier") => void;
  onLogout: () => void;
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

function ConversationRow({
  conv,
  currentConvId,
  projectFolders,
  onSelect,
  onMove,
  onItemClick,
}: {
  conv: Conversation;
  currentConvId: string | null;
  projectFolders: ProjectFolder[];
  onSelect: () => void;
  onMove: (conversationId: string, folderId: string | null) => Promise<boolean>;
  onItemClick?: () => void;
}) {
  const inFolder = Boolean(conv.folder_id);
  const href = conversationUrl(conv.id);

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData(MONV_CONV_DRAG_TYPE, conv.id);
        e.dataTransfer.setData("text/plain", conv.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      className={cn(
        "flex min-h-[44px] w-full items-stretch rounded-lg border border-transparent",
        currentConvId === conv.id
          ? "border-sidebar-border bg-sidebar-accent text-sidebar-foreground"
          : "text-sidebar-foreground/70 hover:bg-sidebar-accent/80 hover:text-sidebar-foreground"
      )}
    >
      <a
        href={href}
        draggable={false}
        onClick={(e) => {
          if (e.button !== 0) return;
          if (e.metaKey || e.ctrlKey || e.shiftKey) return;
          e.preventDefault();
          onSelect();
          onItemClick?.();
        }}
        className="flex min-w-0 flex-1 items-center truncate rounded-md px-2 py-2 pr-1 text-left text-sm text-inherit no-underline hover:text-inherit focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring/40 focus-visible:ring-inset"
      >
        {conv.title}
      </a>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-auto shrink-0 rounded-l-none rounded-r-lg text-sidebar-foreground/70 hover:text-sidebar-foreground"
            onPointerDown={(e) => e.stopPropagation()}
            aria-label="Options de la conversation"
          >
            <MoreHorizontal className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="w-[min(240px,calc(100vw-4rem))]"
          onPointerDown={(e) => e.stopPropagation()}
        >
          <DropdownMenuItem asChild>
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex cursor-default items-center gap-2"
            >
              <ExternalLink className="size-3.5" />
              Ouvrir dans un nouvel onglet
            </a>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-[10px] uppercase tracking-wide">
            Déplacer vers
          </DropdownMenuLabel>
          <DropdownMenuItem
            disabled={!inFolder}
            onSelect={() => {
              void onMove(conv.id, null).then((moved) => {
                if (moved) onItemClick?.();
              });
            }}
          >
            Récents
          </DropdownMenuItem>
          {projectFolders.map((f) => (
            <DropdownMenuItem
              key={f.id}
              disabled={conv.folder_id === f.id}
              className="truncate"
              onSelect={() => {
                void onMove(conv.id, f.id).then((moved) => {
                  if (moved) onItemClick?.();
                });
              }}
            >
              {f.name}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function SidebarContent({
  user,
  conversations,
  projectFolders,
  conversationsLoading = false,
  currentConvId,
  activeProjectFolderId,
  onNewChat,
  onSelectConversation,
  onSelectProjectFolder,
  onCreateProjectFolder,
  onRenameProjectFolder,
  onDeleteProjectFolder,
  onMoveConversationToFolder,
  onNavigate,
  onLogout,
  onItemClick,
}: Omit<
  Props,
  "collapsed" | "onToggle" | "mobileOpen" | "onMobileClose"
> & {
  onItemClick?: () => void;
}) {
  const nav = (action: () => void) => {
    action();
    onItemClick?.();
  };

  const [recentsOpen, setRecentsOpen] = useState(true);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("Nouveau projet");
  const [savingFolder, setSavingFolder] = useState(false);
  const [renamingFolderId, setRenamingFolderId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | "recents" | null>(null);
  const [openGroups, setOpenGroups] = useState<Set<string>>(
    () => new Set(MODE_ORDER)
  );

  const toggleGroup = (modeKey: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(modeKey)) next.delete(modeKey);
      else next.add(modeKey);
      return next;
    });
  };

  const inboxConversations = conversations.filter((c) => !c.folder_id);

  const handleDragOverFolder =
    (folderId: string) => (e: React.DragEvent) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      setDropTarget(folderId);
    };

  const handleDragOverRecents = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDropTarget("recents");
  };

  const handleDragLeaveZone =
    (e: React.DragEvent<HTMLDivElement>) => {
      const rel = e.relatedTarget as Node | null;
      if (rel && e.currentTarget.contains(rel)) return;
      setDropTarget(null);
    };

  const handleDropOnFolder =
    (folderId: string) => async (e: React.DragEvent) => {
      e.preventDefault();
      setDropTarget(null);
      const cid = readConversationIdFromDataTransfer(e.dataTransfer);
      if (!cid) return;
      const moved = await onMoveConversationToFolder(cid, folderId);
      if (moved) onItemClick?.();
    };

  const handleDropOnRecents = async (e: React.DragEvent) => {
    e.preventDefault();
    setDropTarget(null);
    const cid = readConversationIdFromDataTransfer(e.dataTransfer);
    if (!cid) return;
    const moved = await onMoveConversationToFolder(cid, null);
    if (moved) onItemClick?.();
  };

  const handleCreateSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const name = newFolderName.trim() || "Nouveau projet";
    setSavingFolder(true);
    try {
      await onCreateProjectFolder(name);
      setCreatingFolder(false);
      setNewFolderName("Nouveau projet");
    } catch {
      /* toast côté page */
    } finally {
      setSavingFolder(false);
    }
  };

  const startRenameFolder = (f: ProjectFolder) => {
    setRenamingFolderId(f.id);
    setRenameDraft(f.name);
  };

  const commitRename = async () => {
    if (!renamingFolderId) return;
    const name = renameDraft.trim();
    if (!name) return;
    try {
      await onRenameProjectFolder(renamingFolderId, name);
      setRenamingFolderId(null);
    } catch {
      /* toast page */
    }
  };

  const askDeleteFolder = async (id: string, name: string) => {
    const ok = window.confirm(
      `Supprimer le projet « ${name} » ?\n\nLes conversations restent disponibles ; elles seront rangées dans Récents.`
    );
    if (!ok) return;
    setDeletingId(id);
    try {
      await onDeleteProjectFolder(id);
    } catch {
      /* toast */
    } finally {
      setDeletingId(null);
    }
  };

  const showTree = !conversationsLoading;

  return (
    <>
      <div className="space-y-2 p-3">
        <Button
          type="button"
          onClick={() => nav(onNewChat)}
          className="h-11 w-full justify-start gap-2 font-semibold"
        >
          <MessageSquarePlus className="size-4" />
          Nouvelle recherche
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => nav(() => onNavigate("atelier"))}
          className="h-auto min-h-11 w-full justify-start gap-2.5 rounded-xl border-primary/25 bg-sidebar-accent/50 py-2.5 text-left text-sidebar-foreground hover:bg-sidebar-accent"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <Compass className="size-[17px]" strokeWidth={2.25} />
          </span>
          <span className="flex min-w-0 flex-col items-start gap-0.5 text-left">
            <span className="text-[11px] font-semibold uppercase leading-none tracking-wide text-primary">
              Agent
            </span>
            <span className="w-full truncate text-[13px] font-semibold leading-tight">
              Créé ton entreprise
            </span>
          </span>
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 pb-3">
        <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.12em] mb-2 px-1">
          PROJETS
        </p>
        <button
          type="button"
          onClick={() => {
            setCreatingFolder((v) => !v);
            setNewFolderName("Nouveau projet");
          }}
          className="flex w-full items-center gap-2 rounded-lg border border-dashed border-border bg-white/[0.02] px-3 py-2.5 text-sm text-muted-foreground hover:bg-white/[0.05] hover:border-border transition-colors min-h-[44px] mb-2"
        >
          <FolderPlus size={17} strokeWidth={2.25} className="shrink-0 text-teal-300/85" />
          <span className="font-medium">Nouveau projet</span>
        </button>

        {creatingFolder && (
          <form
            onSubmit={handleCreateSubmit}
            className="mb-3 rounded-lg border border-border bg-white/[0.03] p-2 space-y-2"
          >
            <label className="block text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Nom du projet
            </label>
            <input
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-2.5 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              placeholder="Ex. Rachat hôtel, Prospection Q2…"
              maxLength={160}
              autoFocus
              disabled={savingFolder}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCreatingFolder(false)}
                className="px-2.5 py-1.5 text-xs text-muted-foreground hover:text-muted-foreground"
                disabled={savingFolder}
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={savingFolder}
                className="rounded-md bg-white/90 px-3 py-1.5 text-xs font-semibold text-gray-950 hover:bg-white disabled:opacity-50"
              >
                {savingFolder ? "…" : "Créer"}
              </button>
            </div>
          </form>
        )}

        {conversationsLoading ? (
          <div className="space-y-1.5 px-1 mb-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-9 rounded-lg bg-white/[0.04] animate-pulse"
              />
            ))}
          </div>
        ) : (
          <div className="space-y-0.5 mb-4">
            {projectFolders.length === 0 && !creatingFolder ? (
              <p className="text-xs text-muted-foreground px-1 py-2">
                Aucun projet — crée-en un pour regrouper tes recherches.
              </p>
            ) : (
              projectFolders.map((f) => {
                const busy = deletingId === f.id;
                const selected = activeProjectFolderId === f.id;
                return (
                  <div
                    key={f.id}
                    onDragOver={handleDragOverFolder(f.id)}
                    onDragLeave={handleDragLeaveZone}
                    onDrop={handleDropOnFolder(f.id)}
                    className={`flex items-stretch rounded-lg min-h-[44px] border transition-shadow ${
                      selected
                        ? "border-border bg-white/[0.08]"
                        : "border-transparent hover:bg-muted/50"
                    } ${
                      dropTarget === f.id
                        ? "ring-2 ring-teal-400/50 ring-offset-2 ring-offset-background"
                        : ""
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        nav(() => {
                          onSelectProjectFolder(f.id);
                        })
                      }
                      className="flex flex-1 min-w-0 items-center gap-2 px-2.5 py-2 text-left text-sm text-foreground"
                    >
                      <Folder
                        size={16}
                        className={`shrink-0 ${selected ? "text-teal-300" : "text-teal-400/70"}`}
                      />
                      {renamingFolderId === f.id ? (
                        <input
                          value={renameDraft}
                          onChange={(e) => setRenameDraft(e.target.value)}
                          onBlur={() => void commitRename()}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") void commitRename();
                            if (e.key === "Escape") setRenamingFolderId(null);
                          }}
                          className="min-w-0 flex-1 rounded border border-teal-500/30 bg-background px-1.5 py-0.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-teal-400/50"
                          maxLength={160}
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span className="truncate font-medium">{f.name}</span>
                      )}
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-auto shrink-0 rounded-l-none rounded-r-lg border-l border-sidebar-border text-sidebar-foreground/65 hover:text-sidebar-foreground"
                          aria-label={`Actions projet ${f.name}`}
                        >
                          <MoreHorizontal className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-44">
                        <DropdownMenuItem
                          onSelect={() => startRenameFolder(f)}
                          className="gap-2"
                        >
                          <Pencil className="size-3.5" />
                          Renommer
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          disabled={busy}
                          className="gap-2 text-destructive focus:text-destructive"
                          onSelect={() => void askDeleteFolder(f.id, f.name)}
                        >
                          <Trash2 className="size-3.5" />
                          Supprimer
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                );
              })
            )}
          </div>
        )}

        {conversationsLoading ? (
          <div className="space-y-1.5 px-1 mt-3">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="h-9 rounded-lg bg-white/[0.04] animate-pulse"
              />
            ))}
          </div>
        ) : inboxConversations.length === 0 ? (
          <p className="text-xs text-muted-foreground px-1 py-1 mt-3">
            Aucune conversation dans Récents.
          </p>
        ) : showTree ? (
          <div className="mt-3">
            <button
              type="button"
              onClick={() => setRecentsOpen((o) => !o)}
              className="flex w-full items-center gap-1.5 rounded-lg px-1 py-1.5 text-left text-xs font-semibold text-gray-400 hover:bg-muted/50 hover:text-foreground transition-colors mb-0.5"
            >
              <ChevronDown
                size={14}
                className={`shrink-0 transition-transform ${recentsOpen ? "" : "-rotate-90"}`}
              />
              <span className="truncate">
                <span className="font-semibold text-muted-foreground tracking-wide">
                  Récents
                </span>
                <span className="ml-1.5 tabular-nums text-muted-foreground font-normal">
                  ({inboxConversations.length})
                </span>
              </span>
            </button>
            {recentsOpen && (
              <div
                onDragOver={handleDragOverRecents}
                onDragLeave={handleDragLeaveZone}
                onDrop={handleDropOnRecents}
                className={`space-y-1 pl-0.5 rounded-lg min-h-[44px] py-0.5 ${
                  dropTarget === "recents"
                    ? "ring-2 ring-white/25 ring-offset-2 ring-offset-background"
                    : ""
                }`}
              >
                {(() => {
                  const recentConvs = inboxConversations;
                  const groups: Record<string, Conversation[]> = {};
                  for (const conv of recentConvs) {
                    const raw = conv.mode ?? "";
                    const key =
                      raw === ATELIER_MODE_LABEL
                        ? "atelier"
                        : normalizeMode(raw);
                    if (!groups[key]) groups[key] = [];
                    groups[key].push(conv);
                  }

                  return MODE_ORDER.filter(
                    (modeKey) => (groups[modeKey]?.length ?? 0) > 0
                  ).map((modeKey) => {
                    const convs = groups[modeKey] || [];
                    const display = MODE_DISPLAY[modeKey];
                    const isOpen = openGroups.has(modeKey);
                    const GroupIcon =
                      modeKey === "atelier"
                        ? Compass
                        : MODE_META[modeKey as Mode].icon;

                    return (
                      <div key={modeKey}>
                        <button
                          type="button"
                          onClick={() => toggleGroup(modeKey)}
                          className="flex items-center justify-between w-full px-2 py-1 rounded-md hover:bg-muted/50 transition-colors group"
                        >
                          <div className="flex items-center gap-1.5 min-w-0">
                            <GroupIcon
                              size={12}
                              className={cn(
                                "shrink-0",
                                modeKey === "atelier"
                                  ? "text-primary"
                                  : display.color
                              )}
                            />
                            <span
                              className={`text-[10px] font-semibold uppercase tracking-wider ${display.color}`}
                            >
                              {display.label}
                            </span>
                            <span className="text-[10px] text-muted-foreground shrink-0">
                              ({convs.length})
                            </span>
                          </div>
                          <ChevronRight
                            size={12}
                            className={`text-muted-foreground shrink-0 transition-transform duration-200 ${
                              isOpen ? "rotate-90" : ""
                            }`}
                          />
                        </button>

                        {isOpen && (
                          <div className="ml-2 mt-0.5 space-y-0.5">
                            {convs.map((conv) => (
                              <ConversationRow
                                key={conv.id}
                                conv={conv}
                                currentConvId={currentConvId}
                                projectFolders={projectFolders}
                                onSelect={() =>
                                  nav(() => onSelectConversation(conv.id))
                                }
                                onMove={onMoveConversationToFolder}
                                onItemClick={onItemClick}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  });
                })()}
              </div>
            )}
          </div>
        ) : null}
      </div>

      <div className="space-y-0.5 border-t border-sidebar-border p-3">
        <Button
          type="button"
          variant="ghost"
          onClick={() => nav(() => onNavigate("dashboard"))}
          className="h-11 w-full justify-start gap-2 text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <History className="size-4 shrink-0" />
          Historique
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => nav(() => onNavigate("credits"))}
          className="h-11 w-full justify-start gap-2 text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <CreditCard className="size-4 shrink-0" />
          Crédits
          {user && (
            <span className="ml-auto rounded bg-sidebar-accent px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-sidebar-foreground/80">
              {user.credits_unlimited ? "∞" : user.credits}
            </span>
          )}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => nav(onLogout)}
          className="h-11 w-full justify-start gap-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
        >
          <LogOut className="size-4 shrink-0" />
          Déconnexion
        </Button>
      </div>
    </>
  );
}

export default function Sidebar({
  user,
  conversations,
  projectFolders,
  conversationsLoading = false,
  currentConvId,
  activeProjectFolderId,
  onNewChat,
  onSelectConversation,
  onSelectProjectFolder,
  onCreateProjectFolder,
  onRenameProjectFolder,
  onDeleteProjectFolder,
  onMoveConversationToFolder,
  onNavigate,
  onLogout,
  collapsed,
  onToggle,
  mobileOpen = false,
  onMobileClose,
}: Props) {
  useEffect(() => {
    if (!mobileOpen) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  const sharedProps = {
    user,
    conversations,
    projectFolders,
    conversationsLoading,
    currentConvId,
    activeProjectFolderId,
    onNewChat,
    onSelectConversation,
    onSelectProjectFolder,
    onCreateProjectFolder,
    onRenameProjectFolder,
    onDeleteProjectFolder,
    onMoveConversationToFolder,
    onNavigate,
    onLogout,
  };

  return (
    <TooltipProvider delayDuration={300}>
      {collapsed ? (
        <div className="hidden w-14 shrink-0 flex-col items-center gap-2 border-r border-sidebar-border bg-sidebar py-4 text-sidebar-foreground md:flex">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={onToggle}
                aria-label="Déplier la barre latérale"
              >
                <ChevronRight className="size-[18px]" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Déplier</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="secondary"
                size="icon"
                onClick={onNewChat}
                aria-label="Nouvelle recherche"
              >
                <MessageSquarePlus className="size-[18px]" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Nouvelle recherche</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="border-primary/30 text-primary"
                onClick={() => onNavigate("atelier")}
                aria-label="Agent Atelier"
              >
                <Compass className="size-[18px]" strokeWidth={2.25} />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Atelier</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => onNavigate("dashboard")}
                aria-label="Historique"
              >
                <History className="size-[18px]" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Historique</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => onNavigate("credits")}
                aria-label="Crédits"
              >
                <CreditCard className="size-[18px]" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Crédits</TooltipContent>
          </Tooltip>
          <div className="mt-auto">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={onLogout}
                  aria-label="Déconnexion"
                >
                  <LogOut className="size-[18px]" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Déconnexion</TooltipContent>
            </Tooltip>
          </div>
        </div>
      ) : (
        <div className="hidden h-full w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex">
          <div className="flex items-center justify-between border-b border-sidebar-border px-4 py-3">
            <span className="text-base font-bold tracking-tight">
              MONV
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onToggle}
              aria-label="Replier la barre latérale"
            >
              <ChevronLeft className="size-4" />
            </Button>
          </div>
          <SidebarContent {...sharedProps} />
        </div>
      )}

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm backdrop-enter"
            onClick={onMobileClose}
            aria-hidden
          />
          <div className="relative flex h-full w-[280px] max-w-[85vw] flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground drawer-enter">
            <div className="flex items-center justify-between border-b border-sidebar-border px-4 py-3">
              <span className="text-base font-bold tracking-tight">MONV</span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={onMobileClose}
                aria-label="Fermer le menu"
              >
                <X className="size-[18px]" />
              </Button>
            </div>
            <SidebarContent {...sharedProps} onItemClick={onMobileClose} />
          </div>
        </div>
      )}
    </TooltipProvider>
  );
}
