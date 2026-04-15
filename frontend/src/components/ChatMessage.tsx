"use client";

import ReactMarkdown from "react-markdown";
import ResultsTable from "./ResultsTable";
import QcmCard from "./QcmCard";
import { AlertCircle } from "lucide-react";
import type { Message, QcmPayload } from "@/lib/api";

interface Props {
  message: Message;
  userCredits: number;
  creditsUnlimited?: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  exporting: boolean;
  onQcmSubmit?: (answers: string) => void;
}

export default function ChatMessage({
  message,
  userCredits,
  creditsUnlimited = false,
  onExport,
  exporting,
  onQcmSubmit,
}: Props) {
  const isUser = message.role === "user";
  const isError = message.message_type === "error";
  const meta = message.metadata_json
    ? JSON.parse(message.metadata_json)
    : null;

  const isQcm = message.message_type === "qcm" && meta?.questions;

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

      <div className={`max-w-[80%] ${isUser ? "order-first" : ""}`}>
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
