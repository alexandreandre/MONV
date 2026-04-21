"use client";

import ReactMarkdown from "react-markdown";
import ResultsTable from "./ResultsTable";
import QcmCard from "./QcmCard";
import AtelierDossier from "./AtelierDossier";
import { AlertCircle, Compass } from "lucide-react";
import type { Message, QcmPayload, BusinessDossierPayload } from "@/lib/api";
import {
  DEFAULT_MODE,
  MODE_META,
  normalizeMode,
  type Mode,
} from "@/lib/modes";
import { stripEmojis } from "@/lib/stripEmojis";
import { AGENT_META, ATELIER_MODE_LABEL } from "@/lib/agents";

interface Props {
  message: Message;
  userCredits: number;
  creditsUnlimited?: boolean;
  onExport: (searchId: string, format: "xlsx" | "csv") => void;
  /** Export séquentiel de tous les segments Atelier disposant d'un search_id. */
  onExportAllAtelier?: (
    items: { search_id: string; credits_required: number }[],
    format: "xlsx" | "csv"
  ) => void;
  exporting: boolean;
  onQcmSubmit?: (answers: string) => void;
  /** Mode de la conversation — affiché en badge sur les messages utilisateur. */
  conversationMode?: Mode | null;
  /** True si la conversation appartient à l'agent Atelier (mode="atelier"). */
  isAtelierConversation?: boolean;
  conversationId?: string | null;
  onAtelierDossierReplaced?: (dossier: BusinessDossierPayload) => void;
  onAtelierNotify?: (kind: "success" | "error", message: string) => void;
  onAtelierCreditsRemaining?: (credits: number) => void;
}

export default function ChatMessage({
  message,
  userCredits,
  creditsUnlimited = false,
  onExport,
  onExportAllAtelier,
  exporting,
  onQcmSubmit,
  conversationMode = null,
  isAtelierConversation = false,
  conversationId = null,
  onAtelierDossierReplaced,
  onAtelierNotify,
  onAtelierCreditsRemaining,
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
  const isAtelierBrief = message.message_type === "agent_brief";
  const isClassicQcm = message.message_type === "qcm";
  const hasAtelierQcmPayload =
    isAtelierBrief && meta && Array.isArray(meta.questions);
  const hasClassicQcmPayload =
    isClassicQcm &&
    meta &&
    Array.isArray(meta.questions) &&
    meta.questions.length > 0;
  const showQcmCard = Boolean(
    (hasAtelierQcmPayload || hasClassicQcmPayload) && onQcmSubmit
  );

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
          className={`mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${AGENT_META.atelier.badgeBg} ${AGENT_META.atelier.accentText}`}
        >
          <Compass size={13} className={AGENT_META.atelier.accentText} />
        </div>
        <div className="flex-1 min-w-0 w-full shrink-0">
          {message.content && (
            <div className="inline-block max-w-full rounded-2xl border border-border bg-card px-4 py-3 text-card-foreground">
              <div className="prose prose-sm prose-neutral max-w-none dark:prose-invert [&>p]:leading-relaxed">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            </div>
          )}
          <AtelierDossier
            dossier={dossier}
            conversationId={conversationId ?? undefined}
            userCredits={userCredits}
            creditsUnlimited={creditsUnlimited}
            onExport={onExport}
            onExportAllAtelier={onExportAllAtelier}
            exporting={exporting}
            onDossierReplaced={onAtelierDossierReplaced}
            onNotify={onAtelierNotify}
            onCreditsRemaining={onAtelierCreditsRemaining}
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
                : "bg-muted text-muted-foreground"
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
              ? "bg-primary text-primary-foreground"
              : isError
                ? "border border-destructive/30 bg-destructive/10 text-destructive"
                : "border border-border bg-card text-card-foreground"
          }`}
        >
          <div
            className={
              isUser
                ? "prose prose-sm prose-invert max-w-none [&>p]:leading-relaxed"
                : "prose prose-sm prose-neutral max-w-none dark:prose-invert [&>p]:leading-relaxed"
            }
          >
            <ReactMarkdown>
              {isUser ? message.content : stripEmojis(message.content)}
            </ReactMarkdown>
          </div>

          {showQcmCard && (
            <QcmCard
              payload={meta as QcmPayload}
              onSubmit={onQcmSubmit!}
              submitLabel={
                isAtelierBrief ? "Générer le dossier" : "Valider mes choix"
              }
              helperText={
                isAtelierBrief
                  ? (meta as QcmPayload).questions?.length
                    ? "Une ou plusieurs réponses par question selon les cases ; tu pourras affiner ensuite dans la conversation."
                    : "Aucune question complémentaire n’est nécessaire : tu peux enchaîner sur le dossier."
                  : undefined
              }
            />
          )}
        </div>

        {meta && meta.preview && !showQcmCard && !isDossier && (
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
            resultsMode={
              typeof meta.mode === "string"
                ? normalizeMode(meta.mode)
                : DEFAULT_MODE
            }
          />
        )}
      </div>

      {isUser && (
        <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-bold text-muted-foreground">
          V
        </div>
      )}
    </div>
  );
}
