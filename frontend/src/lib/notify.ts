import { toast } from "sonner";

export type NotifyKind = "success" | "error" | "info";

export function notify(
  kind: NotifyKind,
  message: string,
  duration?: number
): void {
  const opts = duration != null ? { duration } : undefined;
  if (kind === "success") toast.success(message, opts);
  else if (kind === "error") toast.error(message, opts);
  else toast.message(message, opts);
}
