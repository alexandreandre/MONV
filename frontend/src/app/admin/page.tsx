"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminListAgents, type AdminAgentSummary } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function AdminDashboardPage() {
  const [agents, setAgents] = useState<AdminAgentSummary[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    adminListAgents()
      .then(setAgents)
      .catch((e) => setErr(e instanceof Error ? e.message : "Erreur"));
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Administration MONV</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Visualisez les pipelines IA, versionnez les prompts et modèles, testez et consultez les exécutions.
        </p>
      </div>
      {err ? (
        <p className="text-sm text-destructive">{err}</p>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((a) => (
          <Card key={a.agent_id} className="flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-base">{a.label}</CardTitle>
                <Badge variant={a.errors_24h > 0 ? "destructive" : "secondary"}>
                  {a.errors_24h} err. 24h
                </Badge>
              </div>
              <CardDescription className="line-clamp-2 font-mono text-[11px]">
                {a.primary_model}
              </CardDescription>
            </CardHeader>
            <CardContent className="mt-auto flex flex-1 flex-col justify-end gap-2 text-xs text-muted-foreground">
              <div>
                Version active :{" "}
                <span className="text-foreground">
                  {a.active_version_number != null ? `v${a.active_version_number}` : "—"}
                </span>
              </div>
              <div>Runs 7j : {a.runs_7d}</div>
              <Button asChild size="sm" className="mt-2 w-full">
                <Link href={`/admin/modes/${a.agent_id}`}>Ouvrir l’éditeur</Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
