"use client";

import { useState, useRef, useEffect } from "react";
import { ArrowUp, Loader2 } from "lucide-react";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
  placeholder?: string;
}

export default function ChatInput({
  onSend,
  disabled,
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
    if (!trimmed || disabled) return;
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
    <div className="flex items-end gap-2 bg-surface-2 border border-white/[0.08] rounded-xl p-2 focus-within:border-white/[0.16] transition-colors">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none bg-transparent text-white placeholder-gray-600 outline-none px-2 py-1.5 text-sm leading-relaxed max-h-[200px]"
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !hasContent}
        className={`flex-shrink-0 p-2 rounded-lg transition-all ${
          hasContent && !disabled
            ? "bg-white text-gray-950 hover:bg-gray-200"
            : "bg-white/[0.06] text-gray-600 cursor-not-allowed"
        }`}
      >
        {disabled ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <ArrowUp size={16} />
        )}
      </button>
    </div>
  );
}
