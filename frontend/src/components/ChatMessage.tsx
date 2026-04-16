"use client";

import ReactMarkdown from "react-markdown";
import ResultsTable from "./ResultsTable";
import QcmCard from "./QcmCard";
import BusinessDossier from "./BusinessDossier";
import { AlertCircle, Compass } from "lucide-react";
import type { Message, QcmPayload, BusinessDossierPayload } from "@/lib/api";
import { MODE_META, normalizeMode, type Mode } from "@/lib/modes";
import { AGENT_META, ATELIER_MODE_LABEL } from "@/lib/agents";

interface Props {
  message: Message;
  userCredits: number;
  creditsUnlimited?: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
  onQcmSubmit?: (answers: string) => void;
  /** Mode de la conversation — affiché en badge sur les messages utilisateur. */
  conversationMode?: Mode | null;
  /** True si la conversation appartient à l'agent Atelier (mode="atelier"). */
  isAtelierConversation?: boolean;
}

export default function ChatMessage({
  message,
  userCredits,
  creditsUnlimited = false,
  onExport,
  exporting,
  onQcmSubmit,
  conversationMode = null,
  isAtelierConversation = false,
}: Props) {
  const isUser = message.role === "user";
  const isError = message.message_type === "error";
  const meta = message.metadata_json
    ? (() => {
        try {
          return JSON.parse(message.metadata_json!);
        } catch {
          return null;
        }
      })()
    : null;

  const isDossier =
    message.message_type === "business_dossier" && meta?.brief && meta?.canvas;
  const isAtelierBrief =
    message.message_type === "agent_brief" && meta?.questions;
  const isQcm =
    (message.message_type === "qcm" || isAtelierBrief) && meta?.questions;

  // Badge affiché sur les messages utilisateur — priorité à Atelier s'il s'agit
  // d'une conversation Atelier, sinon badge de mode classique.
  const metaMode = typeof meta?.mode === "string" ? meta.mode : null;
  const isAtelierMessage =
    metaMode === ATELIER_MODE_LABEL || isAtelierConversation;

  const messageMode: Mode | null = (() => {
    if (isAtelierMessage) return null;
    const raw = metaMode ?? conversationMode;
    if (raw == null || raw === "") return null;
    const m = normalizeMode(raw);
    return m === "prospection" ? null : m;
  })();

  // ── Cas spécial : dossier Atelier → rendu pleine largeur, pas de bulle ────
  if (isDossier && !isUser) {
    const dossier = meta as BusinessDossierPayload;
    return (
      <div className="flex gap-3 animate-fade-in">
        <div
          className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-1 text-white ${AGENT_META.atelier.badgeBg}`}
        >
          <Compass size={13} className={AGENT_META.atelier.accentText} />
        </div>
        <div className="flex-1 min-w-0">
          {message.content && (
            <div className="rounded-2xl px-4 py-3 bg-surface-2 text-gray-200 border border-white/[0.06] inline-block max-w-full">
              <div className="prose prose-invert prose-sm max-w-none [&>p]:leading-relaxed">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            </div>
          )}
          <BusinessDossier
            dossier={dossier}
            userCredits={userCredits}
            creditsUnlimited={creditsUnlimited}
            onExport={onExport}
            exporting={exporting}
          />
        </div>
      </div>
    );
  }

  const showUserBadge = isUser && (messageMode != null || isAtelierMessage);
  const atelierMeta = AGENT_META.atelier;

  return (
    <div
      className={`flex gap-3 animate-fade-in ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <div
          className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-1 text-[11px] font-bold ${
            isError
              ? "bg-red-500/15 text-red-400"
              : isAtelierMessage
                ? atelierMeta.badgeBg
                : "bg-white/[0.08] text-gray-400"
          }`}
        >
          {isError ? (
            <AlertCircle size={14} />
          ) : isAtelierMessage ? (
            <Compass size={13} className={atelierMeta.accentText} />
          ) : (
            "M"
          )}
        </div>
      )}

      <div className={`max-w-[92%] sm:max-w-[80%] ${isUser ? "order-first" : ""}`}>
        {showUserBadge && (
          <div className="flex justify-end mb-1">
            {isAtelierMessage ? (
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${atelierMeta.badgeBg} ${atelierMeta.badgeText}`}
              >
                <Compass size={10} />
                {atelierMeta.label}
              </span>
            ) : messageMode != null ? (
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${MODE_META[messageMode].badgeBg} ${MODE_META[messageMode].badgeText}`}
              >
                {(() => {
                  const Icon = MODE_META[messageMode].icon;
                  return <Icon size={10} />;
                })()}
                {MODE_META[messageMode].label}
              </span>
            ) : null}
          </div>
        )}

        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? "bg-brand-600 text-white"
              : isError
                ? "bg-red-500/8 text-red-300 border border-red-500/15"
                : "bg-surface-2 text-gray-200 border border-white/[0.06]"
          }`}
        >
          <div className="prose prose-invert prose-sm max-w-none [&>p]:leading-relaxed">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>

          {isQcm && onQcmSubmit && (
            <QcmCard
              payload={meta as QcmPayload}
              onSubmit={onQcmSubmit}
            />
          )}
        </div>

        {meta && meta.preview && !isQcm && !isDossier && (
          <ResultsTable
            data={meta.preview}
            columns={meta.columns || []}
            total={meta.total || 0}
            searchId={meta.search_id || ""}
            creditsRequired={meta.credits_required || 0}
            userCredits={userCredits}
            creditsUnlimited={creditsUnlimited}
            onExport={onExport}
            exporting={exporting}
            mapPoints={meta.map_points || []}
          />
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-white/[0.08] flex items-center justify-center mt-1 text-[11px] font-bold text-gray-400">
          V
        </div>
      )}
    </div>
  );
}
