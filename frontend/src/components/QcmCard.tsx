"use client";

import { useState } from "react";
import { Check, ChevronRight, PenLine } from "lucide-react";
import type { QcmPayload } from "@/lib/api";
import { stripEmojis } from "@/lib/stripEmojis";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

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

/** Aligné sur `backend/services/conversationalist.py` — exclusif avec les autres options en multi. */
const NEUTRAL_OPTION_IDS = new Set([
  "any",
  "peu_importe",
  "pas_de_preference",
  "non_defini",
  "indetermine",
  "incertain",
  "nsp",
  "tout",
  "toutes",
  "indifferent",
  "peu_importe_zone",
]);

function isNeutralOptionId(id: string): boolean {
  return NEUTRAL_OPTION_IDS.has(id.toLowerCase());
}

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
      if (!multiple) {
        next = cur.selected.includes(optId) ? [] : [optId];
      } else if (isNeutralOptionId(optId)) {
        next = cur.selected.includes(optId) ? [] : [optId];
      } else {
        const base = cur.selected.filter((s) => !isNeutralOptionId(s));
        next = base.includes(optId)
          ? base.filter((s) => s !== optId)
          : [...base, optId];
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
    <div className="mt-3 space-y-4">
      {payload.questions.map((q) => {
        const a = answers[q.id];
        const showFreeInput = a?.selected.some((s) => {
          const opt = q.options.find((o) => o.id === s);
          return opt?.free_text;
        });

        return (
          <Card key={q.id} className="border-border/80 shadow-sm">
            <CardContent className="space-y-3 p-4 sm:p-5">
              <div>
                <Label className="text-sm font-medium leading-snug text-foreground">
                  {stripEmojis(q.question)}
                </Label>
                {q.multiple ? (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Plusieurs réponses possibles (sauf option « peu importe » /
                    équivalent, seule).
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {q.options.map((opt) => {
                  const isSelected = a?.selected.includes(opt.id);
                  return (
                    <Button
                      key={opt.id}
                      type="button"
                      variant={isSelected ? "default" : "outline"}
                      size="sm"
                      disabled={submitted || disabled}
                      onClick={() => toggle(q.id, opt.id, q.multiple ?? false)}
                      className={cn(
                        "min-h-[44px] h-auto whitespace-normal py-2 text-left font-normal",
                        submitted && "cursor-default opacity-50"
                      )}
                    >
                      {isSelected && <Check className="size-3.5 shrink-0" />}
                      {opt.free_text && !isSelected && (
                        <PenLine className="size-3.5 shrink-0" />
                      )}
                      {stripEmojis(opt.label)}
                    </Button>
                  );
                })}
              </div>

              {showFreeInput && (
                <Input
                  type="text"
                  value={a?.freeText || ""}
                  onChange={(e) => setFreeText(q.id, e.target.value)}
                  disabled={submitted || disabled}
                  placeholder="Précisez ici..."
                  className="mt-1"
                />
              )}
            </CardContent>
          </Card>
        );
      })}

      {helperText && (
        <p className="text-xs leading-relaxed text-muted-foreground">{helperText}</p>
      )}

      <Button
        type="button"
        onClick={handleSubmit}
        disabled={!canSubmit || submitted || disabled}
        title={
          !canSubmit && !submitted
            ? "Sélectionne au moins une réponse par question (plusieurs choix quand indiqué) ; si tu choisis « Autre », précise dans le champ texte."
            : undefined
        }
        className="min-h-[44px] w-full justify-center gap-2 sm:w-auto"
      >
        {submitted ? (
          <>
            <Check className="size-4" />
            Envoyé
          </>
        ) : (
          <>
            {submitLabel}
            <ChevronRight className="size-4" />
          </>
        )}
      </Button>
    </div>
  );
}
