"use client";

import { useState, useRef, useEffect } from "react";
import { ArrowUp, Loader2, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
  /** Requête en cours : affiche le bouton d’arrêt au lieu de l’envoi. */
  loading?: boolean;
  onStop?: () => void;
  placeholder?: string;
}

export default function ChatInput({
  onSend,
  disabled,
  loading = false,
  onStop,
  placeholder = "Décrivez l'entreprise que vous cherchez...",
}: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 200) + "px";
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled || loading) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const hasContent = value.trim().length > 0;

  return (
    <div className="flex items-end gap-2 rounded-xl border border-input bg-muted/30 p-2 transition-colors focus-within:border-ring focus-within:ring-1 focus-within:ring-ring/30">
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        className="max-h-[200px] min-h-0 flex-1 resize-none border-0 bg-transparent px-2 py-1.5 text-sm leading-relaxed shadow-none focus-visible:ring-0"
      />
      {loading ? (
        <Button
          type="button"
          variant="secondary"
          size="icon"
          onClick={() => onStop?.()}
          title="Arrêter la requête"
          className="shrink-0"
        >
          <Square className="size-4" fill="currentColor" />
        </Button>
      ) : (
        <Button
          type="button"
          size="icon"
          onClick={handleSubmit}
          disabled={disabled || !hasContent}
          className={cn("shrink-0", !hasContent || disabled ? "opacity-50" : "")}
        >
          {disabled ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <ArrowUp className="size-4" />
          )}
        </Button>
      )}
    </div>
  );
}
