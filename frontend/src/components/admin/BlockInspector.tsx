"use client";

import { useMemo } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AdminApiMeta, AdminGraphNode } from "@/lib/api";

const TYPE_BADGES: Record<string, { label: string; bg: string; fg: string; border: string }> = {
  llm: { label: "LLM", bg: "#ede9fe", fg: "#5b21b6", border: "#c4b5fd" },
  tool: { label: "Outil", bg: "#dbeafe", fg: "#1d4ed8", border: "#93c5fd" },
  api: { label: "API externe", bg: "#cffafe", fg: "#0e7490", border: "#67e8f9" },
  output: { label: "Sortie", bg: "#dcfce7", fg: "#15803d", border: "#86efac" },
  condition: { label: "Condition", bg: "#fef3c7", fg: "#a16207", border: "#fcd34d" },
  fallback: { label: "Fallback", bg: "#fee2e2", fg: "#b91c1c", border: "#fca5a5" },
  default: { label: "Bloc", bg: "#f1f5f9", fg: "#475569", border: "#cbd5e1" },
};

export type BlockOverrideDraft = {
  enabled?: boolean;
  model?: string;
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
};

type Props = {
  node: AdminGraphNode | null;
  draft: BlockOverrideDraft;
  onChange: (patch: BlockOverrideDraft) => void;
  onReset: () => void;
  readOnly?: boolean;
};

export function BlockInspector({ node, draft, onChange, onReset, readOnly }: Props) {
  const isLlm = useMemo(
    () => node && ["llm"].includes(node.type) && Boolean(node.model_ref),
    [node]
  );
  const isApi = node?.type === "api";

  if (!node) {
    return (
      <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
        Sélectionnez un bloc sur le graphe pour voir sa configuration.
      </div>
    );
  }

  const typeBadge = TYPE_BADGES[node.type] ?? TYPE_BADGES.default;

  return (
    <ScrollArea className="h-[min(72vh,640px)] pr-3">
      <div className="space-y-4 pb-6">
        <div className="space-y-1.5">
          <div className="flex items-start gap-2">
            <span
              className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
              style={{
                background: typeBadge.bg,
                color: typeBadge.fg,
                border: `1px solid ${typeBadge.border}`,
              }}
            >
              {typeBadge.label}
            </span>
            <h3 className="text-sm font-semibold leading-tight">{node.label}</h3>
          </div>
          <p className="text-xs text-muted-foreground">
            <code className="rounded bg-muted px-1 py-0.5 text-[10px]">{node.id}</code>{" "}
            ·{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-[10px]">{node.source_file}</code>
          </p>
        </div>

        {isApi && node.api ? <ApiDetailsPanel api={node.api} /> : null}

        <Tabs defaultValue="apercu">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="apercu">Aperçu</TabsTrigger>
            <TabsTrigger value="prompt" disabled={!isLlm}>Prompt</TabsTrigger>
            <TabsTrigger value="modele" disabled={!isLlm}>Modèle</TabsTrigger>
          </TabsList>
          <TabsContent value="apercu" className="space-y-3 pt-3 text-xs">
            {node.model_ref ? (
              <div>
                <span className="text-muted-foreground">Modèle (.env) :</span>{" "}
                <code className="rounded bg-muted px-1">{node.model_ref}</code>
              </div>
            ) : null}
            {node.default_prompt_preview ? (
              <p className="text-muted-foreground">{node.default_prompt_preview}</p>
            ) : null}
            {node.inputs && node.inputs.length ? (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Entrées
                </div>
                <ul className="space-y-0.5">
                  {node.inputs.map((i) => (
                    <li key={i.name} className="font-mono">
                      {i.name}
                      <span className="text-muted-foreground"> : {i.type}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {node.outputs && node.outputs.length ? (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Sorties
                </div>
                <ul className="space-y-0.5">
                  {node.outputs.map((o) => (
                    <li key={o.name} className="font-mono">
                      {o.name}
                      <span className="text-muted-foreground"> : {o.type}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {node.fallback ? (
              <div className="rounded-md border border-amber-300/50 bg-amber-50 p-2 text-[11px] dark:border-amber-900/40 dark:bg-amber-950/30">
                <div className="font-medium text-amber-900 dark:text-amber-200">Fallback</div>
                <div className="text-amber-800 dark:text-amber-300">{node.fallback}</div>
              </div>
            ) : null}
            {node.errors && node.errors.length ? (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Erreurs gérées
                </div>
                <div className="flex flex-wrap gap-1">
                  {node.errors.map((e) => (
                    <span
                      key={e}
                      className="rounded-full border border-destructive/30 bg-destructive/10 px-2 py-0.5 font-mono text-[10px] text-destructive"
                    >
                      {e}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
            {node.effective ? (
              <div className="rounded-md bg-muted/50 p-2">
                <div className="font-medium text-foreground">Override actif</div>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-[10px]">
                  {JSON.stringify(node.effective, null, 2)}
                </pre>
              </div>
            ) : isLlm ? (
              <p className="text-muted-foreground">Aucun override publié — paramètres par défaut du code.</p>
            ) : null}
          </TabsContent>
          <TabsContent value="prompt" className="space-y-2 pt-3">
            <Label htmlFor="sys-prompt">Prompt système (remplace le défaut si renseigné)</Label>
            <Textarea
              id="sys-prompt"
              disabled={readOnly || !isLlm}
              rows={12}
              className="font-mono text-xs"
              value={draft.system_prompt ?? ""}
              onChange={(e) => onChange({ ...draft, system_prompt: e.target.value })}
              placeholder={isLlm ? "Laisser vide pour garder le prompt du code…" : "Bloc non-LLM : pas de prompt système."}
            />
          </TabsContent>
          <TabsContent value="modele" className="space-y-3 pt-3">
            <div className="space-y-1">
              <Label htmlFor="model-id">Identifiant modèle OpenRouter</Label>
              <Input
                id="model-id"
                disabled={readOnly || !isLlm}
                className="font-mono text-xs"
                value={draft.model ?? ""}
                onChange={(e) => onChange({ ...draft, model: e.target.value })}
                placeholder="ex. openai/gpt-4o-mini"
              />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label className="text-xs">Température</Label>
                <Input
                  type="number"
                  step="0.05"
                  min={0}
                  max={2}
                  disabled={readOnly || !isLlm}
                  value={draft.temperature ?? ""}
                  onChange={(e) =>
                    onChange({
                      ...draft,
                      temperature: e.target.value === "" ? undefined : Number(e.target.value),
                    })
                  }
                />
              </div>
              <div>
                <Label className="text-xs">max_tokens</Label>
                <Input
                  type="number"
                  disabled={readOnly || !isLlm}
                  value={draft.max_tokens ?? ""}
                  onChange={(e) =>
                    onChange({
                      ...draft,
                      max_tokens: e.target.value === "" ? undefined : parseInt(e.target.value, 10),
                    })
                  }
                />
              </div>
              <div>
                <Label className="text-xs">top_p</Label>
                <Input
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  disabled={readOnly || !isLlm}
                  value={draft.top_p ?? ""}
                  onChange={(e) =>
                    onChange({
                      ...draft,
                      top_p: e.target.value === "" ? undefined : Number(e.target.value),
                    })
                  }
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={onReset} disabled={readOnly}>
                Réinitialiser le brouillon
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </ScrollArea>
  );
}

function ApiDetailsPanel({ api }: { api: AdminApiMeta }) {
  const authLabel = (() => {
    const t = api.auth?.type;
    if (!t || t === "none") return "Aucune (API publique)";
    if (t === "api_key_header") return `Clé API en en-tête (${api.auth?.header})`;
    if (t === "api_key_param_or_header") return `Clé API en paramètre / en-tête (${api.auth?.header})`;
    if (t === "bearer_token") return `Bearer token (${api.auth?.header})`;
    return t;
  })();

  return (
    <div className="space-y-3 rounded-xl border border-cyan-300/60 bg-cyan-50/50 p-3 text-xs dark:border-cyan-800/50 dark:bg-cyan-950/20">
      {api.provider ? (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Fournisseur
          </div>
          <div className="font-medium">{api.provider}</div>
        </div>
      ) : null}

      {api.base_url ? (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Base URL
            {api.base_url_env ? (
              <span className="ml-1 font-normal normal-case tracking-normal">
                (env <code className="rounded bg-muted px-1">{api.base_url_env}</code>)
              </span>
            ) : null}
          </div>
          <code className="block break-all rounded bg-muted/70 p-1.5 font-mono text-[10.5px]">
            {api.base_url}
          </code>
        </div>
      ) : null}

      {api.endpoints && api.endpoints.length ? (
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Endpoints utilisés
          </div>
          <ul className="space-y-1.5">
            {api.endpoints.map((ep, i) => (
              <li
                key={i}
                className="rounded-md border border-border bg-background/70 p-2"
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <span
                    className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold"
                    style={methodStyle(ep.method)}
                  >
                    {ep.method}
                  </span>
                  <code className="font-mono text-[10.5px]">{ep.path || "/"}</code>
                </div>
                {ep.purpose ? (
                  <div className="mt-1 text-muted-foreground">{ep.purpose}</div>
                ) : null}
                {ep.params && ep.params.length ? (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {ep.params.map((p) => (
                      <span
                        key={p}
                        className="rounded-full bg-muted px-1.5 py-0.5 font-mono text-[10px]"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Authentification
          </div>
          <div className="leading-tight">{authLabel}</div>
          {api.auth?.env_var ? (
            <code className="mt-0.5 inline-block rounded bg-muted px-1 py-0.5 text-[10px]">
              {api.auth.env_var}
            </code>
          ) : null}
        </div>
        {api.cost ? (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Coût
            </div>
            <div className="leading-tight">{api.cost}</div>
          </div>
        ) : null}
        {api.rate_limit ? (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Rate-limit
            </div>
            <div className="leading-tight">{api.rate_limit}</div>
          </div>
        ) : null}
        {typeof api.timeout_s === "number" ? (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Timeout
            </div>
            <div className="leading-tight">{api.timeout_s} s</div>
          </div>
        ) : null}
      </div>

      {api.usage ? (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Comment elle est utilisée
          </div>
          <p className="leading-snug">{api.usage}</p>
        </div>
      ) : null}

      {api.triggered_by ? (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Déclenchée par
          </div>
          <p className="leading-snug">{api.triggered_by}</p>
        </div>
      ) : null}

      {api.doc_url ? (
        <a
          href={api.doc_url}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-1 text-cyan-700 hover:underline dark:text-cyan-300"
        >
          Documentation officielle ↗
        </a>
      ) : null}
    </div>
  );
}

function methodStyle(method: string): React.CSSProperties {
  const m = (method || "").toUpperCase();
  if (m === "GET") return { background: "#dcfce7", color: "#166534" };
  if (m === "POST") return { background: "#dbeafe", color: "#1d4ed8" };
  if (m === "PUT") return { background: "#fef3c7", color: "#a16207" };
  if (m === "DELETE") return { background: "#fee2e2", color: "#b91c1c" };
  return { background: "#f1f5f9", color: "#475569" };
}
