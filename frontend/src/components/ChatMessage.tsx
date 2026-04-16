"use client";

import ReactMarkdown from "react-markdown";
import ResultsTable from "./ResultsTable";
import QcmCard from "./QcmCard";
import { AlertCircle } from "lucide-react";
import type { Message, QcmPayload } from "@/lib/api";
import { MODE_META, normalizeMode, type Mode } from "@/lib/modes";

interface Props {
  message: Message;
  userCredits: number;
  creditsUnlimited?: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
  onQcmSubmit?: (answers: string) => void;
  /** Mode de la conversation — affiché en badge sur les messages utilisateur. */
  conversationMode?: Mode | null;
}

export default function ChatMessage({
  message,
  userCredits,
  creditsUnlimited = false,
  onExport,
  exporting,
  onQcmSubmit,
  conversationMode = null,
}: Props) {
  const isUser = message.role === "user";
  const isError = message.message_type === "error";
  const meta = message.metadata_json
    ? JSON.parse(message.metadata_json)
    : null;

  const isQcm = message.message_type === "qcm" && meta?.questions;

  const messageMode: Mode | null = (() => {
    const raw = meta?.mode ?? conversationMode;
    if (raw == null || raw === "") return null;
    const m = normalizeMode(raw);
    return m === "prospection" ? null : m;
  })();
  const showUserBadge = isUser && messageMode != null;

  return (
    <div
      className={`flex gap-3 animate-fade-in ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <div
          className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-1 text-[11px] font-bold ${
            isError
              ? "bg-red-500/15 text-red-400"
              : "bg-white/[0.08] text-gray-400"
          }`}
        >
          {isError ? (
            <AlertCircle size={14} />
          ) : (
            "M"
          )}
        </div>
      )}

      <div className={`max-w-[92%] sm:max-w-[80%] ${isUser ? "order-first" : ""}`}>
        {showUserBadge && messageMode && (
          <div className="flex justify-end mb-1">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${MODE_META[messageMode].badgeBg} ${MODE_META[messageMode].badgeText}`}
            >
              {(() => {
                const Icon = MODE_META[messageMode].icon;
                return <Icon size={10} />;
              })()}
              {MODE_META[messageMode].label}
            </span>
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

        {meta && meta.preview && !isQcm && (
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
