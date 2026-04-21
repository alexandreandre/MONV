"use client";

import { Shield, Brain, Search, CheckCircle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type PipelineStep = "filtering" | "analyzing" | "searching" | "done";

const STEPS: { key: PipelineStep; label: string; icon: typeof Shield }[] = [
  { key: "filtering", label: "Analyse de la demande", icon: Shield },
  { key: "analyzing", label: "Extraction des critères", icon: Brain },
  { key: "searching", label: "Recherche en cours", icon: Search },
  { key: "done", label: "Terminé", icon: CheckCircle },
];

interface Props {
  currentStep: PipelineStep;
}

export default function PipelineProgress({ currentStep }: Props) {
  const currentIndex = STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="flex animate-fade-in gap-3">
      <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-bold text-muted-foreground">
        M
      </div>
      <Card className="min-w-[260px] border-border/80 shadow-sm">
        <CardContent className="px-4 py-3">
          <div className="space-y-2">
            {STEPS.filter((s) => s.key !== "done").map((step, i) => {
              const Icon = step.icon;
              const isActive = i === currentIndex;
              const isDone = i < currentIndex;

              return (
                <div key={step.key} className="flex items-center gap-2.5">
                  <div
                    className={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-all duration-300",
                      isDone
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                        : isActive
                          ? "bg-primary/15 text-primary step-active"
                          : "bg-muted text-muted-foreground"
                    )}
                  >
                    {isDone ? (
                      <CheckCircle className="size-[11px]" />
                    ) : (
                      <Icon className="size-[11px]" />
                    )}
                  </div>
                  <span
                    className={cn(
                      "text-sm transition-colors duration-300",
                      isDone
                        ? "text-muted-foreground line-through"
                        : isActive
                          ? "font-medium text-foreground"
                          : "text-muted-foreground"
                    )}
                  >
                    {step.label}
                  </span>
                  {isActive && (
                    <div className="ml-1 flex gap-1">
                      <div className="typing-dot h-1 w-1 rounded-full bg-muted-foreground" />
                      <div className="typing-dot h-1 w-1 rounded-full bg-muted-foreground" />
                      <div className="typing-dot h-1 w-1 rounded-full bg-muted-foreground" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
