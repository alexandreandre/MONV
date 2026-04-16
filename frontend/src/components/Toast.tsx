"use client";

import { useEffect, useState } from "react";
import { X, AlertCircle, CheckCircle, Info } from "lucide-react";

export interface ToastData {
  id: string;
  type: "error" | "success" | "info";
  message: string;
  duration?: number;
}

interface Props {
  toasts: ToastData[];
  onRemove: (id: string) => void;
}

const ICONS = {
  error: AlertCircle,
  success: CheckCircle,
  info: Info,
};

const STYLES = {
  error: "border-red-500/20 bg-red-500/8 text-red-300",
  success: "border-green-500/20 bg-green-500/8 text-green-300",
  info: "border-white/[0.08] bg-surface-2 text-gray-300",
};

function ToastItem({
  toast,
  onRemove,
}: {
  toast: ToastData;
  onRemove: () => void;
}) {
  const [exiting, setExiting] = useState(false);
  const Icon = ICONS[toast.type];

  useEffect(() => {
    const duration = toast.duration ?? 5000;
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(onRemove, 200);
    }, duration);
    return () => clearTimeout(timer);
  }, [toast.duration, onRemove]);

  return (
    <div
      className={`${exiting ? "toast-exit" : "toast-enter"} flex items-start gap-3 rounded-xl border px-4 py-3 shadow-lg backdrop-blur-sm ${STYLES[toast.type]}`}
    >
      <Icon size={16} className="flex-shrink-0 mt-0.5" />
      <p className="text-sm flex-1">{toast.message}</p>
      <button
        onClick={() => {
          setExiting(true);
          setTimeout(onRemove, 200);
        }}
        className="flex-shrink-0 opacity-50 hover:opacity-100 transition-opacity"
      >
        <X size={13} />
      </button>
    </div>
  );
}

export default function ToastContainer({ toasts, onRemove }: Props) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-4 z-50 flex flex-col gap-2 sm:max-w-sm sm:w-full">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onRemove={() => onRemove(t.id)} />
      ))}
    </div>
  );
}
