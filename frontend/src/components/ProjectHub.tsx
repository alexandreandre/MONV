"use client";

import { useState } from "react";
import {
  FolderOpen,
  Compass,
  ArrowRight,
  ExternalLink,
} from "lucide-react";
import ChatInput from "@/components/ChatInput";
import ModeSelector from "@/components/ModeSelector";
import TemplateCards from "@/components/TemplateCards";
import type { Conversation, Template } from "@/lib/api";
import type { Mode } from "@/lib/modes";
import { MODE_META } from "@/lib/modes";
import {
  conversationUrl,
  MONV_CONV_DRAG_TYPE,
  readConversationIdFromDataTransfer,
} from "@/lib/conversationNav";

function HubConversationRow({
  conv,
  onSelect,
}: {
  conv: Conversation;
  onSelect: (id: string) => void;
}) {
  const href = conversationUrl(conv.id);
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData(MONV_CONV_DRAG_TYPE, conv.id);
        e.dataTransfer.setData("text/plain", conv.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      className="flex w-full items-stretch rounded-lg min-h-[44px] border border-transparent text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
    >
      <a
        href={href}
        draggable={false}
        onClick={(e) => {
          if (e.button !== 0) return;
          if (e.metaKey || e.ctrlKey || e.shiftKey) return;
          e.preventDefault();
          onSelect(conv.id);
        }}
        className="flex flex-1 min-w-0 items-center px-2 py-2.5 pr-1 text-left text-sm truncate text-inherit no-underline hover:text-inherit focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white/25 rounded-md"
      >
        {conv.title}
      </a>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center px-2 text-muted-foreground hover:text-teal-200/90 shrink-0"
        title="Ouvrir dans un nouvel onglet"
        aria-label="Ouvrir dans un nouvel onglet"
      >
        <ExternalLink size={15} />
      </a>
    </div>
  );
}

interface Props {
  projectFolderId: string;
  projectName: string;
  conversationsInProject: Conversation[];
  conversationsLoading: boolean;
  selectedMode: Mode;
  onModeChange: (mode: Mode) => void;
  templates: Template[];
  onTemplateSelect: (query: string) => void;
  sending: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  onSelectConversation: (id: string) => void;
  onLeaveProject: () => void;
  onOpenAtelier: () => void;
  onMoveConversationToFolder: (
    conversationId: string,
    folderId: string | null
  ) => Promise<boolean>;
}

export default function ProjectHub({
  projectFolderId,
  projectName,
  conversationsInProject,
  conversationsLoading,
  selectedMode,
  onModeChange,
  templates,
  onTemplateSelect,
  sending,
  onSend,
  onStop,
  onSelectConversation,
  onLeaveProject,
  onOpenAtelier,
  onMoveConversationToFolder,
}: Props) {
  const placeholder = `+ Nouvelle recherche dans ${projectName}`;
  const [hubDrop, setHubDrop] = useState(false);

  const handleDragLeaveHub = (e: React.DragEvent<HTMLDivElement>) => {
    const rel = e.relatedTarget as Node | null;
    if (rel && e.currentTarget.contains(rel)) return;
    setHubDrop(false);
  };

  const handleDropOnHub = async (e: React.DragEvent) => {
    e.preventDefault();
    setHubDrop(false);
    const cid = readConversationIdFromDataTransfer(e.dataTransfer);
    if (!cid) return;
    await onMoveConversationToFolder(cid, projectFolderId);
  };

  return (
    <div className="flex-1 flex flex-col overflow-y-auto scrollbar-thin">
      <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-10 flex flex-col flex-1 min-h-0">
        <button
          type="button"
          onClick={onLeaveProject}
          className="self-start mb-6 text-xs text-muted-foreground hover:text-muted-foreground transition-colors"
        >
          ← Toutes les recherches
        </button>

        <header className="flex gap-4 items-start mb-8 text-left">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-border bg-white/[0.04] text-muted-foreground"
            aria-hidden
          >
            <FolderOpen size={22} strokeWidth={1.75} />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-muted-foreground">Projet</p>
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground text-balance mt-0.5">
              {projectName}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground leading-relaxed max-w-xl">
              Les recherches lancées ici restent dans ce dossier.
            </p>
          </div>
        </header>

        <div className="w-full rounded-xl border border-border bg-card/70 p-4 sm:p-5 mb-6">
          <div className="mb-4">
            <h2 className="text-xs font-medium text-muted-foreground">Nouvelle recherche</h2>
            <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
              Même flux que l&apos;accueil, avec le projet présélectionné.
            </p>
          </div>
          <ModeSelector
            value={selectedMode}
            onChange={onModeChange}
            disabled={sending}
          />
          <div className="mt-4 pt-4 border-t border-border">
            <ChatInput
              onSend={onSend}
              disabled={sending}
              loading={sending}
              onStop={onStop}
              placeholder={placeholder}
            />
          </div>
          {templates.length > 0 && (
            <div className="mt-5 pt-5 border-t border-border">
              <p className="text-xs font-medium text-muted-foreground mb-3">
                Exemples · {MODE_META[selectedMode].label}
              </p>
              <TemplateCards
                nested
                templates={templates}
                onSelect={onTemplateSelect}
              />
            </div>
          )}
        </div>

        <div className="w-full mb-8">
          <p className="text-xs font-medium text-muted-foreground mb-2">Atelier</p>
          <button
            type="button"
            onClick={onOpenAtelier}
            disabled={sending}
            className="group relative w-full overflow-hidden rounded-xl border border-border bg-card text-left hover:border-border disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-teal-500/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <div
              className="pointer-events-none absolute inset-y-0 left-0 w-[3px] bg-teal-700/90"
              aria-hidden
            />
            <div className="relative flex items-center gap-3 pl-4 pr-3 py-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-teal-950/45 text-teal-200/95">
                <Compass size={18} strokeWidth={2} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground leading-snug">
                  Ouvrir l&apos;Atelier (rattaché à ce projet)
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
                  Nouveau dossier par défaut ; tu peux aussi rattacher à un projet
                  existant depuis l&apos;écran Atelier.
                </p>
              </div>
              <ArrowRight
                size={16}
                className="shrink-0 text-muted-foreground group-hover:text-muted-foreground"
                aria-hidden
              />
            </div>
          </button>
        </div>

        <h2 className="text-xs font-medium text-muted-foreground mb-3">Conversations</h2>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            setHubDrop(true);
          }}
          onDragLeave={handleDragLeaveHub}
          onDrop={handleDropOnHub}
          className={`flex-1 min-h-[120px] rounded-xl border bg-card/40 p-3 sm:p-4 transition-shadow ${
            hubDrop
              ? "border-teal-400/40 ring-2 ring-teal-400/35"
              : "border-border"
          }`}
        >
          <p className="text-[10px] text-muted-foreground mb-2 px-0.5">
            Glisse une conversation ici pour la ranger dans ce projet — ou vers
            Récents / un autre projet dans la barre latérale.
          </p>
          {conversationsLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-10 rounded-lg bg-white/[0.04] animate-pulse"
                />
              ))}
            </div>
          ) : conversationsInProject.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center py-10 px-4">
              <p className="text-base font-semibold text-muted-foreground">
                Aucune conversation pour le moment
              </p>
              <p className="mt-2 text-sm text-muted-foreground max-w-sm leading-relaxed">
                {
                  "Les recherches de ce projet apparaîtront ici. Utilise le champ ci-dessus pour commencer."
                }
              </p>
            </div>
          ) : (
            <ul className="space-y-0.5">
              {conversationsInProject.map((c) => (
                <li key={c.id}>
                  <HubConversationRow
                    conv={c}
                    onSelect={onSelectConversation}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
