"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
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
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const closeMenu = () => detailsRef.current?.removeAttribute("open");

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
      className={`flex w-full items-stretch rounded-lg min-h-[44px] border border-transparent ${
        currentConvId === conv.id
          ? "bg-white/[0.08] text-white border-white/[0.06]"
          : "text-gray-500 hover:bg-white/[0.04] hover:text-gray-300"
      }`}
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
        className="flex flex-1 min-w-0 items-center px-2 py-2 pr-1 text-left text-sm truncate text-inherit no-underline hover:text-inherit focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white/25 rounded-md"
      >
        {conv.title}
      </a>
      <details
        ref={detailsRef}
        className="relative flex items-center shrink-0 group/details"
      >
        <summary
          className="list-none flex h-full items-center justify-center px-2 rounded-r-lg cursor-pointer text-gray-500 hover:text-gray-300 outline-none focus-visible:ring-2 focus-visible:ring-white/30 [&::-webkit-details-marker]:hidden"
          onPointerDown={(e) => e.stopPropagation()}
          aria-label="Options de la conversation"
        >
          <MoreHorizontal size={16} />
        </summary>
        <div
          className="absolute right-0 top-full z-40 mt-0.5 w-[min(240px,calc(100vw-4rem))] rounded-xl border border-white/[0.08] bg-surface-0 py-1 shadow-xl"
          onPointerDown={(e) => e.stopPropagation()}
        >
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-200 hover:bg-white/[0.06]"
            onClick={() => closeMenu()}
          >
            <ExternalLink size={14} />
            Ouvrir dans un nouvel onglet
          </a>
          <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500 border-t border-white/[0.06] mt-1 pt-2">
            Déplacer vers
          </p>
          <button
            type="button"
            disabled={!inFolder}
            onClick={() => {
              void onMove(conv.id, null)
                .then((moved) => {
                  if (moved) onItemClick?.();
                })
                .finally(closeMenu);
            }}
            className="w-full px-3 py-2 text-left text-sm text-gray-200 hover:bg-white/[0.06] disabled:opacity-35 disabled:pointer-events-none"
          >
            Récents
          </button>
          {projectFolders.map((f) => (
            <button
              key={f.id}
              type="button"
              disabled={conv.folder_id === f.id}
              onClick={() => {
                void onMove(conv.id, f.id)
                  .then((moved) => {
                    if (moved) onItemClick?.();
                  })
                  .finally(closeMenu);
              }}
              className="w-full px-3 py-2 text-left text-sm text-gray-200 hover:bg-white/[0.06] truncate disabled:opacity-35 disabled:pointer-events-none"
            >
              {f.name}
            </button>
          ))}
        </div>
      </details>
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
      <div className="p-3 space-y-2">
        <button
          type="button"
          onClick={() => nav(onNewChat)}
          className="flex items-center gap-2 w-full rounded-lg bg-white text-gray-950 px-3.5 py-2 text-sm font-semibold hover:bg-gray-200 active:bg-gray-300 transition-colors min-h-[44px] focus-visible:ring-2 focus-visible:ring-white/40 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-1"
        >
          <MessageSquarePlus size={16} />
          Nouvelle recherche
        </button>
        <button
          type="button"
          onClick={() => nav(() => onNavigate("atelier"))}
          className="flex items-center gap-2.5 w-full rounded-xl border border-teal-500/30 bg-teal-950/20 text-teal-100 px-3.5 py-2.5 text-sm font-medium hover:bg-teal-950/35 hover:border-teal-400/35 active:bg-teal-950/45 transition-colors min-h-[44px] focus-visible:ring-2 focus-visible:ring-teal-400/45 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-1"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-500/20 text-teal-200">
            <Compass size={17} strokeWidth={2.25} />
          </span>
          <span className="flex flex-col items-start gap-0.5 min-w-0 text-left">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-teal-300/90 leading-none">
              Agent
            </span>
            <span className="text-[13px] font-semibold leading-tight truncate w-full text-white">
              Créé ton entreprise
            </span>
          </span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 pb-3">
        <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-[0.12em] mb-2 px-1">
          PROJETS
        </p>
        <button
          type="button"
          onClick={() => {
            setCreatingFolder((v) => !v);
            setNewFolderName("Nouveau projet");
          }}
          className="flex w-full items-center gap-2 rounded-lg border border-dashed border-white/[0.12] bg-white/[0.02] px-3 py-2.5 text-sm text-gray-300 hover:bg-white/[0.05] hover:border-white/[0.18] transition-colors min-h-[44px] mb-2"
        >
          <FolderPlus size={17} strokeWidth={2.25} className="shrink-0 text-teal-300/85" />
          <span className="font-medium">Nouveau projet</span>
        </button>

        {creatingFolder && (
          <form
            onSubmit={handleCreateSubmit}
            className="mb-3 rounded-lg border border-white/[0.08] bg-white/[0.03] p-2 space-y-2"
          >
            <label className="block text-[10px] font-medium uppercase tracking-wide text-gray-500">
              Nom du projet
            </label>
            <input
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              className="w-full rounded-md border border-white/[0.08] bg-surface-0 px-2.5 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              placeholder="Ex. Rachat hôtel, Prospection Q2…"
              maxLength={160}
              autoFocus
              disabled={savingFolder}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCreatingFolder(false)}
                className="px-2.5 py-1.5 text-xs text-gray-500 hover:text-gray-300"
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
              <p className="text-xs text-gray-600 px-1 py-2">
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
                        ? "border-white/[0.12] bg-white/[0.08]"
                        : "border-transparent hover:bg-white/[0.04]"
                    } ${
                      dropTarget === f.id
                        ? "ring-2 ring-teal-400/50 ring-offset-2 ring-offset-surface-1"
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
                      className="flex flex-1 min-w-0 items-center gap-2 px-2.5 py-2 text-left text-sm text-gray-200"
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
                          className="min-w-0 flex-1 rounded border border-teal-500/30 bg-surface-0 px-1.5 py-0.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-teal-400/50"
                          maxLength={160}
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span className="truncate font-medium">{f.name}</span>
                      )}
                    </button>
                    <details className="relative flex items-center shrink-0 border-l border-white/[0.06]">
                      <summary
                        className="list-none flex h-full items-center px-2 text-gray-500 hover:text-gray-300 cursor-pointer [&::-webkit-details-marker]:hidden outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal-400/40"
                        aria-label={`Actions projet ${f.name}`}
                      >
                        <MoreHorizontal size={15} />
                      </summary>
                      <div className="absolute right-0 top-full z-40 mt-0.5 w-44 rounded-lg border border-white/[0.08] bg-surface-0 py-1 shadow-xl">
                        <button
                          type="button"
                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-200 hover:bg-white/[0.06]"
                          onClick={(e) => {
                            (
                              e.currentTarget.closest(
                                "details"
                              ) as HTMLDetailsElement | null
                            )?.removeAttribute("open");
                            startRenameFolder(f);
                          }}
                        >
                          <Pencil size={14} />
                          Renommer
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-400/90 hover:bg-red-500/10 disabled:opacity-40"
                          onClick={(e) => {
                            (
                              e.currentTarget.closest(
                                "details"
                              ) as HTMLDetailsElement | null
                            )?.removeAttribute("open");
                            void askDeleteFolder(f.id, f.name);
                          }}
                        >
                          <Trash2 size={14} />
                          Supprimer
                        </button>
                      </div>
                    </details>
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
          <p className="text-xs text-gray-600 px-1 py-1 mt-3">
            Aucune conversation dans Récents.
          </p>
        ) : showTree ? (
          <div className="mt-3">
            <button
              type="button"
              onClick={() => setRecentsOpen((o) => !o)}
              className="flex w-full items-center gap-1.5 rounded-lg px-1 py-1.5 text-left text-xs font-semibold text-gray-400 hover:bg-white/[0.04] hover:text-gray-200 transition-colors mb-0.5"
            >
              <ChevronDown
                size={14}
                className={`shrink-0 transition-transform ${recentsOpen ? "" : "-rotate-90"}`}
              />
              <span className="truncate">
                <span className="font-semibold text-gray-300 tracking-wide">
                  Récents
                </span>
                <span className="ml-1.5 tabular-nums text-gray-500 font-normal">
                  ({inboxConversations.length})
                </span>
              </span>
            </button>
            {recentsOpen && (
              <div
                onDragOver={handleDragOverRecents}
                onDragLeave={handleDragLeaveZone}
                onDrop={handleDropOnRecents}
                className={`space-y-0.5 pl-0.5 rounded-lg min-h-[44px] py-0.5 ${
                  dropTarget === "recents"
                    ? "ring-2 ring-white/25 ring-offset-2 ring-offset-surface-1"
                    : ""
                }`}
              >
                {inboxConversations.map((c) => (
                  <ConversationRow
                    key={c.id}
                    conv={c}
                    currentConvId={currentConvId}
                    projectFolders={projectFolders}
                    onSelect={() => nav(() => onSelectConversation(c.id))}
                    onMove={onMoveConversationToFolder}
                    onItemClick={onItemClick}
                  />
                ))}
              </div>
            )}
          </div>
        ) : null}
      </div>

      <div className="border-t border-white/[0.06] p-3 space-y-0.5">
        <button
          onClick={() => nav(() => onNavigate("dashboard"))}
          className="flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm text-gray-500 hover:bg-white/[0.04] hover:text-gray-300 active:bg-white/[0.06] transition-colors min-h-[44px]"
        >
          <History size={15} />
          Historique
        </button>
        <button
          onClick={() => nav(() => onNavigate("credits"))}
          className="flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm text-gray-500 hover:bg-white/[0.04] hover:text-gray-300 active:bg-white/[0.06] transition-colors min-h-[44px]"
        >
          <CreditCard size={15} />
          Crédits
          {user && (
            <span className="ml-auto text-[11px] tabular-nums text-gray-500 bg-white/[0.06] px-1.5 py-0.5 rounded">
              {user.credits_unlimited ? "∞" : user.credits}
            </span>
          )}
        </button>
        <button
          onClick={() => nav(onLogout)}
          className="flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm text-gray-500 hover:bg-white/[0.04] hover:text-red-400 active:bg-red-500/10 transition-colors min-h-[44px]"
        >
          <LogOut size={15} />
          Déconnexion
        </button>
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
    <>
      {collapsed ? (
        <div className="hidden md:flex flex-col items-center w-14 bg-surface-1 border-r border-white/[0.06] py-4 gap-2">
          <button
            onClick={onToggle}
            className="p-2 rounded-lg hover:bg-white/[0.06] text-gray-500 transition-colors"
          >
            <ChevronRight size={18} />
          </button>
          <button
            type="button"
            onClick={onNewChat}
            className="p-2 rounded-lg bg-white/[0.08] text-white hover:bg-white/[0.12] transition-colors"
            title="Nouvelle recherche"
          >
            <MessageSquarePlus size={18} />
          </button>
          <button
            type="button"
            onClick={() => onNavigate("atelier")}
            className="p-2 rounded-lg bg-teal-600/25 text-teal-200 hover:bg-teal-600/40 transition-colors"
            title="Agent Atelier"
          >
            <Compass size={18} strokeWidth={2.25} />
          </button>
          <button
            onClick={() => onNavigate("dashboard")}
            className="p-2 rounded-lg hover:bg-white/[0.06] text-gray-500 transition-colors"
            title="Historique"
          >
            <History size={18} />
          </button>
          <button
            onClick={() => onNavigate("credits")}
            className="p-2 rounded-lg hover:bg-white/[0.06] text-gray-500 transition-colors"
            title="Crédits"
          >
            <CreditCard size={18} />
          </button>
          <div className="mt-auto">
            <button
              onClick={onLogout}
              className="p-2 rounded-lg hover:bg-white/[0.06] text-gray-500 transition-colors"
              title="Déconnexion"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      ) : (
        <div className="hidden md:flex flex-col w-64 bg-surface-1 border-r border-white/[0.06] h-full">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
            <span className="text-base font-bold tracking-tight text-white">
              MONV
            </span>
            <button
              onClick={onToggle}
              className="p-1 rounded-md hover:bg-white/[0.06] text-gray-500 transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
          </div>
          <SidebarContent {...sharedProps} />
        </div>
      )}

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm backdrop-enter"
            onClick={onMobileClose}
          />
          <div className="relative flex flex-col w-[280px] max-w-[85vw] h-full bg-surface-1 drawer-enter">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
              <span className="text-base font-bold tracking-tight text-white">
                MONV
              </span>
              <button
                onClick={onMobileClose}
                className="p-2 -mr-1 rounded-lg hover:bg-white/[0.06] text-gray-500 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <SidebarContent {...sharedProps} onItemClick={onMobileClose} />
          </div>
        </div>
      )}
    </>
  );
}
