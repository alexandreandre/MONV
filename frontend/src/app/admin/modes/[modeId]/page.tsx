"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  adminCreateVersion,
  adminExportAgent,
  adminGetGraph,
  adminImportAgent,
  adminListVersions,
  adminPublishVersion,
  adminRollbackVersion,
  adminTestAgent,
  type AdminAgentGraph,
  type AdminAgentVersion,
  type AdminGraphNode,
} from "@/lib/api";
import { AgentGraphCanvas } from "@/components/admin/AgentGraphCanvas";
import { BlockInspector, type BlockOverrideDraft } from "@/components/admin/BlockInspector";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ArrowLeft, Braces, Copy, Download, Play, Save, Upload } from "lucide-react";

const IDS = ["prospection", "sous_traitant", "benchmark", "rachat", "atelier"] as const;

export default function AdminModeEditorPage() {
  const params = useParams<{ modeId: string }>();
  const router = useRouter();
  const modeId = params.modeId;

  const [graph, setGraph] = useState<AdminAgentGraph | null>(null);
  const [versions, setVersions] = useState<AdminAgentVersion[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draftOverrides, setDraftOverrides] = useState<Record<string, BlockOverrideDraft>>({});
  const [versionLabel, setVersionLabel] = useState("");
  const [testOpen, setTestOpen] = useState(false);
  const [testMsg, setTestMsg] = useState("Je cherche des PME du BTP à Lyon");
  const [testFull, setTestFull] = useState(false);
  const [stepMap, setStepMap] = useState<Record<string, "idle" | "running" | "ok" | "error">>({});
  const [jsonOpen, setJsonOpen] = useState(false);

  const valid = IDS.includes(modeId as (typeof IDS)[number]);

  const graphJsonFull = useMemo(
    () => (graph ? JSON.stringify(graph, null, 2) : ""),
    [graph]
  );
  const graphJsonTopology = useMemo(
    () =>
      graph
        ? JSON.stringify(
            { agent_id: graph.agent_id, label: graph.label, graph: graph.graph },
            null,
            2
          )
        : "",
    [graph]
  );

  const load = useCallback(async () => {
    if (!valid) return;
    try {
      const [g, v] = await Promise.all([adminGetGraph(modeId), adminListVersions(modeId)]);
      setGraph(g);
      setVersions(v);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Chargement impossible");
    }
  }, [modeId, valid]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!valid) return;
    try {
      const raw = localStorage.getItem(`admin_draft_${modeId}`);
      if (raw) {
        const parsed = JSON.parse(raw) as Record<string, BlockOverrideDraft>;
        setDraftOverrides(parsed);
      }
    } catch {
      /* ignore */
    }
  }, [modeId, valid]);

  useEffect(() => {
    if (!valid) return;
    localStorage.setItem(`admin_draft_${modeId}`, JSON.stringify(draftOverrides));
  }, [draftOverrides, modeId, valid]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        toast.message("Utilisez le bouton « Enregistrer brouillon » pour créer une version.");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const selectedNode: AdminGraphNode | null = useMemo(() => {
    if (!graph || !selectedId) return null;
    return graph.graph.nodes.find((n) => n.id === selectedId) ?? null;
  }, [graph, selectedId]);

  const draftForSelected = useMemo(() => {
    if (!selectedId) return {};
    return draftOverrides[selectedId] ?? {};
  }, [draftOverrides, selectedId]);

  const patchDraft = useCallback(
    (patch: BlockOverrideDraft) => {
      if (!selectedId) return;
      setDraftOverrides((prev) => ({
        ...prev,
        [selectedId]: { ...(prev[selectedId] ?? {}), ...patch },
      }));
    },
    [selectedId]
  );

  const resetDraft = useCallback(() => {
    if (!selectedId) return;
    setDraftOverrides((prev) => {
      const next = { ...prev };
      delete next[selectedId];
      return next;
    });
  }, [selectedId]);

  const saveDraftVersion = async () => {
    if (!valid) return;
    try {
      const cleaned: Record<string, Record<string, unknown>> = {};
      for (const [bid, o] of Object.entries(draftOverrides)) {
        const row: Record<string, unknown> = {};
        if (o.model) row.model = o.model;
        if (o.system_prompt) row.system_prompt = o.system_prompt;
        if (o.temperature !== undefined) row.temperature = o.temperature;
        if (o.max_tokens !== undefined) row.max_tokens = o.max_tokens;
        if (o.top_p !== undefined) row.top_p = o.top_p;
        row.enabled = o.enabled !== false;
        if (Object.keys(row).length) cleaned[bid] = row;
      }
      await adminCreateVersion(modeId, { label: versionLabel || "Brouillon", overrides: cleaned });
      toast.success("Version enregistrée (non publiée).");
      setVersionLabel("");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Échec enregistrement");
    }
  };

  const publish = async (vid: string) => {
    if (!valid) return;
    try {
      await adminPublishVersion(modeId, vid);
      toast.success("Version publiée.");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Échec publication");
    }
  };

  const rollback = async (vid: string) => {
    if (!valid) return;
    try {
      await adminRollbackVersion(modeId, vid);
      toast.success("Version restaurée et publiée.");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Échec rollback");
    }
  };

  const runTest = async () => {
    if (!valid) return;
    setStepMap({});
    try {
      const res = await adminTestAgent(modeId, { message: testMsg, full_pipeline: testFull });
      const m: Record<string, "idle" | "running" | "ok" | "error"> = {};
      for (const s of res.steps) {
        const st = (s as { block_id?: string; status?: string }).status;
        const bid = (s as { block_id?: string }).block_id;
        if (!bid) continue;
        m[bid] = st === "failed" ? "error" : st === "completed" ? "ok" : "idle";
      }
      setStepMap(m);
      toast.success(`Test terminé — run ${res.run_id}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Test échoué");
    }
  };

  const doExport = async () => {
    if (!valid) return;
    try {
      const data = await adminExportAgent(modeId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `monv-agent-${modeId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export téléchargé.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export impossible");
    }
  };

  const copyJson = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("JSON copié dans le presse-papiers.");
    } catch {
      toast.error("Copie impossible (permissions navigateur).");
    }
  };

  const downloadJson = (text: string, suffix: string) => {
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `monv-graph-${modeId}-${suffix}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Fichier JSON téléchargé.");
  };

  const doImport = () => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = "application/json,.json";
    inp.onchange = async () => {
      const f = inp.files?.[0];
      if (!f || !valid) return;
      try {
        const text = await f.text();
        const payload = JSON.parse(text) as Record<string, unknown>;
        await adminImportAgent(modeId, payload);
        toast.success("Import appliqué — nouvelle version créée.");
        await load();
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Import invalide");
      }
    };
    inp.click();
  };

  if (!valid) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">Agent inconnu.</p>
        <Button variant="link" className="px-0" onClick={() => router.push("/admin/modes")}>
          Retour à la liste
        </Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-border bg-background/95 px-4 py-3 backdrop-blur">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/admin/modes" className="gap-1">
            <ArrowLeft className="size-4" />
            Modes
          </Link>
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold">{graph?.label ?? modeId}</h1>
          <p className="text-xs text-muted-foreground">
            v{graph?.active_version?.version_number ?? "—"} active · graphe lecture seule, overrides versionnés
          </p>
        </div>
        <Input
          className="hidden w-52 md:block"
          placeholder="Libellé de version…"
          value={versionLabel}
          onChange={(e) => setVersionLabel(e.target.value)}
        />
        <Button size="sm" variant="secondary" onClick={saveDraftVersion}>
          <Save className="size-4" />
          Enregistrer
        </Button>
        <Sheet open={jsonOpen} onOpenChange={setJsonOpen}>
          <SheetTrigger asChild>
            <Button size="sm" variant="outline" title="Voir le graphe en JSON brut">
              <Braces className="size-4" />
              JSON
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="flex w-full flex-col gap-0 p-0 sm:max-w-xl lg:max-w-2xl">
            <SheetHeader className="border-b border-border px-6 py-4 text-left">
              <SheetTitle className="flex items-center gap-2">
                <Braces className="size-5 shrink-0" />
                Graphe brut — {graph?.label ?? modeId}
              </SheetTitle>
              <p className="text-xs font-normal text-muted-foreground">
                Données renvoyées par{" "}
                <code className="rounded bg-muted px-1 py-0.5">
                  GET /api/admin/agents/{encodeURIComponent(modeId)}/graph
                </code>
                . Lecture seule ; les overrides actifs sont inclus dans chaque nœud LLM (
                <code className="rounded bg-muted px-1">effective</code>).
              </p>
            </SheetHeader>
            <Tabs defaultValue="topology" className="flex min-h-0 flex-1 flex-col px-6 pt-3">
              <TabsList className="grid w-full shrink-0 grid-cols-2">
                <TabsTrigger value="topology">Topologie (nœuds + arêtes)</TabsTrigger>
                <TabsTrigger value="full">Réponse API complète</TabsTrigger>
              </TabsList>
              <TabsContent value="topology" className="mt-3 flex min-h-0 flex-1 flex-col gap-2">
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button type="button" size="sm" variant="secondary" onClick={() => copyJson(graphJsonTopology)}>
                    <Copy className="size-3.5" />
                    Copier
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => downloadJson(graphJsonTopology, "topology")}
                  >
                    <Download className="size-3.5" />
                    Télécharger
                  </Button>
                </div>
                <Textarea
                  readOnly
                  spellCheck={false}
                  className="min-h-[55vh] flex-1 resize-none font-mono text-[11px] leading-relaxed"
                  value={graphJsonTopology || "Chargement…"}
                />
              </TabsContent>
              <TabsContent value="full" className="mt-3 flex min-h-0 flex-1 flex-col gap-2">
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button type="button" size="sm" variant="secondary" onClick={() => copyJson(graphJsonFull)}>
                    <Copy className="size-3.5" />
                    Copier
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => downloadJson(graphJsonFull, "full")}
                  >
                    <Download className="size-3.5" />
                    Télécharger
                  </Button>
                </div>
                <Textarea
                  readOnly
                  spellCheck={false}
                  className="min-h-[55vh] flex-1 resize-none font-mono text-[11px] leading-relaxed"
                  value={graphJsonFull || "Chargement…"}
                />
              </TabsContent>
            </Tabs>
          </SheetContent>
        </Sheet>
        <Sheet open={testOpen} onOpenChange={setTestOpen}>
          <SheetTrigger asChild>
            <Button size="sm" variant="outline">
              <Play className="size-4" />
              Tester
            </Button>
          </SheetTrigger>
          <SheetContent side="bottom" className="h-[50vh]">
            <SheetHeader>
              <SheetTitle>Test rapide (filter + guard{testFull ? " + orchestrateur" : ""})</SheetTitle>
            </SheetHeader>
            <div className="mt-4 space-y-3">
              <Input value={testMsg} onChange={(e) => setTestMsg(e.target.value)} />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={testFull} onChange={(e) => setTestFull(e.target.checked)} />
                Inclure l’orchestrateur (appel LLM supplémentaire)
              </label>
              <Button onClick={runTest}>Lancer</Button>
            </div>
          </SheetContent>
        </Sheet>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline">
              Version
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
            {versions.map((v) =>
              v.is_active ? (
                <DropdownMenuItem key={v.id} disabled className="text-muted-foreground">
                  v{v.version_number} — déjà active
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem key={v.id} onClick={() => publish(v.id)}>
                  Publier v{v.version_number} — {v.label || "sans titre"}
                </DropdownMenuItem>
              )
            )}
            {versions.length === 0 ? (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">Aucune version en base</div>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
        <Button size="sm" variant="ghost" onClick={doExport}>
          <Download className="size-4" />
        </Button>
        <Button size="sm" variant="ghost" onClick={doImport}>
          <Upload className="size-4" />
        </Button>
      </header>

      <div className="grid flex-1 gap-4 p-4 lg:grid-cols-[1fr_320px]">
        <div className="min-h-0 space-y-2">
          {graph ? (
            <AgentGraphCanvas
              graphNodes={graph.graph.nodes}
              graphEdges={graph.graph.edges}
              selectedId={selectedId}
              onSelect={setSelectedId}
              stepStatus={stepMap}
            />
          ) : (
            <div className="flex h-96 items-center justify-center text-muted-foreground">Chargement…</div>
          )}
        </div>
        <aside className="space-y-4">
          <BlockInspector
            node={selectedNode}
            draft={draftForSelected}
            onChange={patchDraft}
            onReset={resetDraft}
          />
          <div className="rounded-lg border border-border p-3 text-xs">
            <div className="font-medium">Versions récentes</div>
            <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto">
              {versions.slice(0, 8).map((v) => (
                <li key={v.id} className="flex justify-between gap-2">
                  <span>
                    v{v.version_number} {v.is_active ? "●" : ""}
                  </span>
                  <button
                    type="button"
                    className="text-primary underline-offset-2 hover:underline"
                    onClick={() => rollback(v.id)}
                  >
                    restaurer
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
