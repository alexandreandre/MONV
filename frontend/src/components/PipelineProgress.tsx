"use client";

import { Shield, Brain, Search, CheckCircle } from "lucide-react";

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
    <div className="flex gap-3 animate-fade-in">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-white/[0.08] flex items-center justify-center mt-1 text-[11px] font-bold text-gray-400">
        M
      </div>
      <div className="bg-surface-2 border border-white/[0.06] rounded-2xl px-4 py-3 min-w-[260px]">
        <div className="space-y-2">
          {STEPS.filter((s) => s.key !== "done").map((step, i) => {
            const Icon = step.icon;
            const isActive = i === currentIndex;
            const isDone = i < currentIndex;

            return (
              <div key={step.key} className="flex items-center gap-2.5">
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                    isDone
                      ? "bg-green-500/15 text-green-400"
                      : isActive
                        ? "bg-white/[0.1] text-white step-active"
                        : "bg-white/[0.04] text-gray-700"
                  }`}
                >
                  {isDone ? (
                    <CheckCircle size={11} />
                  ) : (
                    <Icon size={11} />
                  )}
                </div>
                <span
                  className={`text-sm transition-colors duration-300 ${
                    isDone
                      ? "text-gray-600 line-through"
                      : isActive
                        ? "text-white font-medium"
                        : "text-gray-700"
                  }`}
                >
                  {step.label}
                </span>
                {isActive && (
                  <div className="flex gap-1 ml-1">
                    <div className="w-1 h-1 rounded-full bg-gray-400 typing-dot" />
                    <div className="w-1 h-1 rounded-full bg-gray-400 typing-dot" />
                    <div className="w-1 h-1 rounded-full bg-gray-400 typing-dot" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
