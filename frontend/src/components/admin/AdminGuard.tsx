"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { adminMe, isLoggedIn } from "@/lib/api";

export function AdminGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!isLoggedIn()) {
        toast.error("Connexion requise pour l’administration.");
        router.replace("/");
        return;
      }
      try {
        await adminMe();
        if (!cancelled) setOk(true);
      } catch {
        if (!cancelled) {
          setOk(false);
          toast.error("Accès administrateur refusé.");
          router.replace("/");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (ok === null) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        Vérification des droits…
      </div>
    );
  }
  if (!ok) return null;
  return <>{children}</>;
}
