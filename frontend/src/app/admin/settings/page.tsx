"use client";

import { useEffect, useState } from "react";
import { adminGetSettings, type AdminSettings } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminSettingsPage() {
  const [s, setS] = useState<AdminSettings | null>(null);

  useEffect(() => {
    adminGetSettings().then(setS).catch(() => setS(null));
  }, []);

  if (!s) {
    return <div className="p-6 text-sm text-muted-foreground">Chargement…</div>;
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-xl font-semibold">Paramètres (lecture seule)</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Modèles (.env)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 font-mono text-xs">
          {Object.entries(s.models).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4 border-b border-border/60 py-1 last:border-0">
              <span className="text-muted-foreground">{k}</span>
              <span className="text-right break-all">{v}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Clés API (présence)</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {Object.entries(s.api_keys_present).map(([k, v]) => (
            <div key={k} className="flex justify-between py-1">
              {k}
              <span className={v ? "text-emerald-600" : "text-destructive"}>{v ? "présente" : "absente"}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Feature flags</CardTitle>
        </CardHeader>
        <CardContent className="font-mono text-xs">
          <pre>{JSON.stringify(s.flags, null, 2)}</pre>
        </CardContent>
      </Card>
    </div>
  );
}
