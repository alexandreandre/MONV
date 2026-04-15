"use client";

import {
  MessageSquarePlus,
  History,
  CreditCard,
  LogOut,
  ChevronLeft,
  ChevronRight,
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
}: Props) {
  if (collapsed) {
    return (
      <div className="flex flex-col items-center w-14 bg-surface-1 border-r border-white/[0.06] py-4 gap-2">
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
    );
  }

  return (
    <div className="flex flex-col w-64 bg-surface-1 border-r border-white/[0.06] h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <span className="text-base font-bold tracking-tight text-white">MONV</span>
        <button
          onClick={onToggle}
          className="p-1 rounded-md hover:bg-white/[0.06] text-gray-500 transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      <div className="p-3">
        <button
          onClick={onNewChat}
          className="flex items-center gap-2 w-full rounded-lg bg-white text-gray-950 px-3.5 py-2 text-sm font-semibold hover:bg-gray-200 transition-colors"
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
                className="h-8 rounded-lg bg-white/[0.04] animate-pulse"
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
                onClick={() => onSelectConversation(c.id)}
                className={`w-full text-left rounded-lg px-3 py-1.5 text-sm truncate transition-colors ${
                  currentConvId === c.id
                    ? "bg-white/[0.08] text-white"
                    : "text-gray-500 hover:bg-white/[0.04] hover:text-gray-300"
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
          onClick={() => onNavigate("dashboard")}
          className="flex items-center gap-2 w-full rounded-lg px-3 py-1.5 text-sm text-gray-500 hover:bg-white/[0.04] hover:text-gray-300 transition-colors"
        >
          <History size={15} />
          Historique
        </button>
        <button
          onClick={() => onNavigate("credits")}
          className="flex items-center gap-2 w-full rounded-lg px-3 py-1.5 text-sm text-gray-500 hover:bg-white/[0.04] hover:text-gray-300 transition-colors"
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
          onClick={onLogout}
          className="flex items-center gap-2 w-full rounded-lg px-3 py-1.5 text-sm text-gray-500 hover:bg-white/[0.04] hover:text-red-400 transition-colors"
        >
          <LogOut size={15} />
          Déconnexion
        </button>
      </div>
    </div>
  );
}
