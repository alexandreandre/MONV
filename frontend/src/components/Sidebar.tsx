"use client";

import { useEffect } from "react";
import {
  MessageSquarePlus,
  History,
  CreditCard,
  LogOut,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react";
import type { Conversation, User } from "@/lib/api";

interface Props {
  user: User | null;
  conversations: Conversation[];
  conversationsLoading?: boolean;
  currentConvId: string | null;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onNavigate: (page: "chat" | "dashboard" | "credits") => void;
  onLogout: () => void;
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

function SidebarContent({
  user,
  conversations,
  conversationsLoading = false,
  currentConvId,
  onNewChat,
  onSelectConversation,
  onNavigate,
  onLogout,
  onItemClick,
}: Omit<Props, "collapsed" | "onToggle" | "mobileOpen" | "onMobileClose"> & {
  onItemClick?: () => void;
}) {
  const nav = (action: () => void) => {
    action();
    onItemClick?.();
  };

  return (
    <>
      <div className="p-3">
        <button
          onClick={() => nav(onNewChat)}
          className="flex items-center gap-2 w-full rounded-lg bg-white text-gray-950 px-3.5 py-2 text-sm font-semibold hover:bg-gray-200 active:bg-gray-300 transition-colors min-h-[44px]"
        >
          <MessageSquarePlus size={16} />
          Nouvelle recherche
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 pb-3">
        <p className="text-[11px] font-medium text-gray-600 uppercase tracking-wider mb-2 px-1">
          Conversations
        </p>
        {conversationsLoading ? (
          <div className="space-y-1.5 px-1">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-9 rounded-lg bg-white/[0.04] animate-pulse"
              />
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <p className="text-sm text-gray-600 px-1">Aucune conversation</p>
        ) : (
          <div className="space-y-0.5">
            {conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => nav(() => onSelectConversation(c.id))}
                className={`w-full text-left rounded-lg px-3 py-2 text-sm truncate transition-colors min-h-[44px] flex items-center ${
                  currentConvId === c.id
                    ? "bg-white/[0.08] text-white"
                    : "text-gray-500 hover:bg-white/[0.04] hover:text-gray-300 active:bg-white/[0.06]"
                }`}
              >
                {c.title}
              </button>
            ))}
          </div>
        )}
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
  conversationsLoading = false,
  currentConvId,
  onNewChat,
  onSelectConversation,
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
    conversationsLoading,
    currentConvId,
    onNewChat,
    onSelectConversation,
    onNavigate,
    onLogout,
  };

  return (
    <>
      {/* ── Desktop sidebar ── */}
      {collapsed ? (
        <div className="hidden md:flex flex-col items-center w-14 bg-surface-1 border-r border-white/[0.06] py-4 gap-2">
          <button
            onClick={onToggle}
            className="p-2 rounded-lg hover:bg-white/[0.06] text-gray-500 transition-colors"
          >
            <ChevronRight size={18} />
          </button>
          <button
            onClick={onNewChat}
            className="p-2 rounded-lg hover:bg-white/[0.06] text-gray-500 transition-colors"
            title="Nouvelle recherche"
          >
            <MessageSquarePlus size={18} />
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

      {/* ── Mobile drawer ── */}
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
