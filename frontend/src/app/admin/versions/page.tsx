"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { adminDiffVersions, adminListAgents, adminListVersions, type AdminAgentVersion } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function VersionsInner() {
  const sp = useSearchParams();
  const [agents, setAgents] = useState<{ agent_id: string; label: string }[]>([]);
  const [agentId, setAgentId] = useState(sp.get("agent") || "prospection");
  const [versions, setVersions] = useState<AdminAgentVersion[]>([]);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [diff, setDiff] = useState<{ block_id: string; from: unknown; to: unknown }[] | null>(null);

  useEffect(() => {
    adminListAgents().then((rows) =>
      setAgents(rows.map((r) => ({ agent_id: r.agent_id, label: r.label })))
    );
  }, []);

  useEffect(() => {
    adminListVersions(agentId).then(setVersions);
  }, [agentId]);

  const compare = async () => {
    if (!a || !b) return;
    const d = await adminDiffVersions(agentId, a, b);
    setDiff(d.blocks);
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-xl font-semibold">Historique des versions</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Comparer deux versions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Agent</div>
            <Select value={agentId} onValueChange={setAgentId}>
              <SelectTrigger className="w-[220px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {agents.map((x) => (
                  <SelectItem key={x.agent_id} value={x.agent_id}>
                    {x.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Version A (id)</div>
            <Select value={a} onValueChange={setA}>
              <SelectTrigger className="w-[280px]">
                <SelectValue placeholder="Choisir…" />
              </SelectTrigger>
              <SelectContent>
                {versions.map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    v{v.version_number} — {v.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Version B (id)</div>
            <Select value={b} onValueChange={setB}>
              <SelectTrigger className="w-[280px]">
                <SelectValue placeholder="Choisir…" />
              </SelectTrigger>
              <SelectContent>
                {versions.map((v) => (
                  <SelectItem key={`b-${v.id}`} value={v.id}>
                    v{v.version_number} — {v.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="button" onClick={compare}>
            Comparer
          </Button>
        </CardContent>
      </Card>
      {diff ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Différences par bloc</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            {diff.map((row) => (
              <div key={row.block_id} className="rounded-md border border-border p-2">
                <div className="font-mono font-semibold">{row.block_id}</div>
                <div className="mt-1 grid gap-2 md:grid-cols-2">
                  <pre className="max-h-40 overflow-auto rounded bg-muted/40 p-2">
                    {JSON.stringify(row.from, null, 2)}
                  </pre>
                  <pre className="max-h-40 overflow-auto rounded bg-muted/40 p-2">
                    {JSON.stringify(row.to, null, 2)}
                  </pre>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

export default function AdminVersionsPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Chargement…</div>}>
      <VersionsInner />
    </Suspense>
  );
}
