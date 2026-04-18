"use client";

import { useState } from "react";
import { Check, ChevronRight, PenLine } from "lucide-react";
import type { QcmPayload } from "@/lib/api";

interface Props {
  payload: QcmPayload;
  onSubmit: (answers: string) => void;
  disabled?: boolean;
  /** Libellé du bouton principal (ex. Atelier vs chat prospection). */
  submitLabel?: string;
  /** Texte d'aide sous les questions, avant le bouton. */
  helperText?: string;
}

type Answers = Record<string, { selected: string[]; freeText: string }>;

export default function QcmCard({
  payload,
  onSubmit,
  disabled,
  submitLabel = "Valider mes choix",
  helperText,
}: Props) {
  const [answers, setAnswers] = useState<Answers>(() => {
    const init: Answers = {};
    for (const q of payload.questions) {
      init[q.id] = { selected: [], freeText: "" };
    }
    return init;
  });

  const [submitted, setSubmitted] = useState(false);

  const toggle = (qId: string, optId: string, multiple: boolean) => {
    setAnswers((prev) => {
      const cur = prev[qId];
      let next: string[];
      if (multiple) {
        next = cur.selected.includes(optId)
          ? cur.selected.filter((s) => s !== optId)
          : [...cur.selected, optId];
      } else {
        next = cur.selected.includes(optId) ? [] : [optId];
      }
      return { ...prev, [qId]: { ...cur, selected: next } };
    });
  };

  const setFreeText = (qId: string, text: string) => {
    setAnswers((prev) => ({
      ...prev,
      [qId]: { ...prev[qId], freeText: text },
    }));
  };

  const canSubmit = payload.questions.every((q) => {
    const a = answers[q.id];
    if (!a) return false;
    if (a.selected.length === 0) return false;
    const hasFreeTextSelected = a.selected.some((s) => {
      const opt = q.options.find((o) => o.id === s);
      return opt?.free_text;
    });
    if (hasFreeTextSelected && !a.freeText.trim()) return false;
    return true;
  });

  const handleSubmit = () => {
    if (!canSubmit || disabled || submitted) return;
    setSubmitted(true);

    const lines: string[] = [];
    for (const q of payload.questions) {
      const a = answers[q.id];
      const labels: string[] = [];
      for (const optId of a.selected) {
        const opt = q.options.find((o) => o.id === optId);
        if (opt?.free_text && a.freeText.trim()) {
          labels.push(a.freeText.trim());
        } else if (opt) {
          labels.push(opt.label);
        }
      }
      if (labels.length > 0) {
        lines.push(`${q.question} ${labels.join(", ")}`);
      }
    }

    onSubmit(lines.join("\n"));
  };

  return (
    <div className="space-y-4 mt-3">
      {payload.questions.map((q) => {
        const a = answers[q.id];
        const showFreeInput = a?.selected.some((s) => {
          const opt = q.options.find((o) => o.id === s);
          return opt?.free_text;
        });

        return (
          <div key={q.id}>
            <p className="text-sm font-medium text-gray-200 mb-2">
              {q.question}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {q.options.map((opt) => {
                const isSelected = a?.selected.includes(opt.id);
                return (
                  <button
                    key={opt.id}
                    disabled={submitted || disabled}
                    onClick={() => toggle(q.id, opt.id, q.multiple ?? false)}
                    className={`
                      inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm min-h-[44px]
                      border transition-all duration-150
                      ${
                        isSelected
                          ? "bg-white text-gray-950 border-white"
                          : "bg-transparent border-white/[0.12] text-gray-400 hover:border-white/[0.25] hover:text-white active:bg-white/[0.06]"
                      }
                      ${submitted ? "opacity-50 cursor-default" : "cursor-pointer"}
                    `}
                  >
                    {isSelected && <Check size={13} />}
                    {opt.free_text && !isSelected && <PenLine size={13} />}
                    {opt.label}
                  </button>
                );
              })}
            </div>

            {showFreeInput && (
              <input
                type="text"
                value={a?.freeText || ""}
                onChange={(e) => setFreeText(q.id, e.target.value)}
                disabled={submitted || disabled}
                placeholder="Précisez ici..."
                className="mt-2 w-full bg-surface-2 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-white/[0.2]"
              />
            )}
          </div>
        );
      })}

      {helperText && (
        <p className="text-xs text-gray-500 leading-relaxed">{helperText}</p>
      )}

      <button
        type="button"
        onClick={handleSubmit}
        disabled={!canSubmit || submitted || disabled}
        title={
          !canSubmit && !submitted
            ? "Sélectionne au moins une réponse par question ; si tu choisis « Autre », précise dans le champ texte."
            : undefined
        }
        className={`
          inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all min-h-[44px] w-full sm:w-auto justify-center
          ${
            canSubmit && !submitted
              ? "bg-white text-gray-950 hover:bg-gray-200 active:bg-gray-300"
              : "bg-white/[0.06] text-gray-600 cursor-not-allowed"
          }
        `}
      >
        {submitted ? (
          <>
            <Check size={15} />
            Envoyé
          </>
        ) : (
          <>
            {submitLabel}
            <ChevronRight size={15} />
          </>
        )}
      </button>
    </div>
  );
}
