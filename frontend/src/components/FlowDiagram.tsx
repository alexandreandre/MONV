"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type KeyboardEvent,
} from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import {
  Banknote,
  ExternalLink,
  Info,
  Layers,
  MousePointerClick,
  Package,
  Sparkles,
  Star,
} from "lucide-react";
import type { FlowActor, FlowEdge, FlowMap, SegmentResult } from "@/lib/api";

interface Props {
  flows: FlowMap;
  segments?: SegmentResult[];
  /** Clic sur une carte liée à un segment : ex. bascule vers l’onglet Tableaux + scroll (fourni par le parent). */
  onSegmentActivate?: (segmentKey: string) => void;
  /** Hauteur du canevas (ex. vue colonne + sidebar). */
  graphHeightClassName?: string;
}

type FlowLayer = "valeur" | "financier" | "information" | "all";

const LAYER_META: Record<
  Exclude<FlowLayer, "all">,
  { label: string; color: string; icon: typeof Package }
> = {
  valeur: { label: "Valeur", color: "#34d399", icon: Package },
  financier: { label: "Cash", color: "#fbbf24", icon: Banknote },
  information: { label: "Info", color: "#38bdf8", icon: Info },
};

type ActorNodeData = {
  actor: FlowActor;
  segmentKey: string | null;
  segmentLabel: string | null;
  onNavigate: (key: string) => void;
};

function normalizeActors(acteurs: FlowMap["acteurs"]): FlowActor[] {
  if (!acteurs?.length) return [];
  const first = acteurs[0];
  if (typeof first === "string") {
    return (acteurs as string[]).map((label) => ({ label, segment_key: null }));
  }
  return acteurs as FlowActor[];
}

function normLabel(s: string): string {
  return s.trim().toLowerCase();
}

function findActor(label: string, actors: FlowActor[]): FlowActor | null {
  const t = normLabel(label);
  const exact = actors.find((a) => normLabel(a.label) === t);
  if (exact) return exact;
  return (
    actors.find((a) => {
      const al = normLabel(a.label);
      return t.includes(al) || al.includes(t);
    }) ?? null
  );
}

function segmentKeyForActor(
  actor: FlowActor | null,
  segments: SegmentResult[],
): string | null {
  if (!actor) return null;
  if (actor.segment_key) return actor.segment_key;
  const al = normLabel(actor.label);
  return segments.find((s) => normLabel(s.label) === al)?.key ?? null;
}

/* ---------- Node custom ---------- */

const NODE_WIDTH = 210;
const NODE_HEIGHT = 76;

function ActorNode({ data }: NodeProps) {
  const { actor, segmentKey, segmentLabel, onNavigate } = data as unknown as ActorNodeData;
  const primary = actor.emphasis === "primary";
  const clickable = Boolean(segmentKey);

  const go = () => {
    if (clickable && segmentKey) onNavigate(segmentKey);
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (!clickable) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      go();
    }
  };

  return (
    <div
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      aria-label={
        clickable && segmentLabel
          ? `Ouvrir le tableau du segment ${segmentLabel}`
          : undefined
      }
      className={`relative flex h-[76px] w-[210px] flex-col justify-center rounded-xl border px-3 py-2 text-left shadow-[0_4px_14px_-4px_rgba(0,0,0,0.7)] transition-all ${
        primary
          ? "border-teal-400/60 bg-teal-500/[0.12]"
          : "border-white/[0.14] bg-[#18181b]"
      } ${
        clickable
          ? "cursor-pointer hover:border-teal-300/80 hover:bg-teal-500/[0.14] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-500/50"
          : "cursor-default"
      }`}
      onClick={go}
      onKeyDown={onKeyDown}
      title={
        actor.hint?.trim() ||
        (clickable && segmentLabel
          ? `Ouvrir le tableau : ${segmentLabel}`
          : undefined)
      }
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-0 !bg-white/20"
      />
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2 !w-2 !border-0 !bg-white/20"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-0 !bg-white/20"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !border-0 !bg-white/20"
      />

      <div className="flex items-center gap-1.5">
        {primary && (
          <Star
            size={11}
            className="shrink-0 text-teal-300"
            aria-hidden
            fill="currentColor"
          />
        )}
        <span className="truncate text-[12.5px] font-semibold text-gray-50">
          {actor.label}
        </span>
        {clickable && (
          <ExternalLink
            size={10}
            className="ml-auto shrink-0 text-teal-300/80"
            aria-hidden
          />
        )}
      </div>
      {actor.role?.trim() && (
        <span className="mt-0.5 truncate text-[10px] text-gray-400">
          {actor.role}
        </span>
      )}
      {clickable && segmentLabel && (
        <span className="mt-1 inline-flex w-fit items-center gap-1 rounded-md bg-teal-500/15 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider text-teal-200/90">
          Segment · {segmentLabel}
        </span>
      )}
    </div>
  );
}

const nodeTypes = { actor: ActorNode };

/* ---------- Layout dagre ---------- */

function layoutWithDagre(
  nodes: Node[],
  edges: Edge[],
  rankdir: "LR" | "TB",
): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir,
    nodesep: rankdir === "LR" ? 40 : 28,
    ranksep: rankdir === "LR" ? 90 : 56,
    marginx: 24,
    marginy: 24,
  });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  for (const e of edges) g.setEdge(e.source, e.target);
  dagre.layout(g);

  const flowLR = rankdir === "LR";
  return nodes.map((n) => {
    const { x, y } = g.node(n.id);
    return {
      ...n,
      position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
      sourcePosition: flowLR ? Position.Right : Position.Bottom,
      targetPosition: flowLR ? Position.Left : Position.Top,
    };
  });
}

/* ---------- Graph inner (needs ReactFlowProvider) ---------- */

function FlowGraph({
  actors,
  layeredEdges,
  segments,
  onNavigate,
  rankdir,
}: {
  actors: FlowActor[];
  layeredEdges: (FlowEdge & { layer: Exclude<FlowLayer, "all"> })[];
  segments: SegmentResult[];
  onNavigate: (key: string) => void;
  rankdir: "LR" | "TB";
}) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    const rawNodes: Node[] = actors.map((actor) => {
      const sk = segmentKeyForActor(actor, segments);
      const sl = sk ? segments.find((s) => s.key === sk)?.label ?? null : null;
      return {
        id: `a-${normLabel(actor.label)}`,
        type: "actor",
        position: { x: 0, y: 0 },
        data: {
          actor,
          segmentKey: sk,
          segmentLabel: sl,
          onNavigate,
        } satisfies ActorNodeData,
      };
    });

    const rawEdges: Edge[] = [];
    const seen = new Set<string>();
    layeredEdges.forEach((e, idx) => {
      const origin = findActor(e.origine, actors);
      const dest = findActor(e.destination, actors);
      if (!origin || !dest || origin.label === dest.label) return;
      const sid = `a-${normLabel(origin.label)}`;
      const tid = `a-${normLabel(dest.label)}`;
      const meta = LAYER_META[e.layer];
      const key = `${sid}->${tid}:${e.layer}:${idx}`;
      if (seen.has(key)) return;
      seen.add(key);
      const dashed = (e.pattern || "").toLowerCase() === "dashed";
      rawEdges.push({
        id: key,
        source: sid,
        target: tid,
        type: "smoothstep",
        animated: false,
        label: e.label?.trim() || undefined,
        labelStyle: {
          fill: "#e5e7eb",
          fontSize: 10,
          fontWeight: 600,
        },
        labelBgStyle: { fill: "#0b0b0c", fillOpacity: 0.85 },
        labelBgPadding: [4, 2],
        labelBgBorderRadius: 4,
        style: {
          stroke: meta.color,
          strokeWidth: 1.8,
          strokeDasharray: dashed ? "6 4" : undefined,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: meta.color,
          width: 18,
          height: 18,
        },
        data: { detail: e.detail ?? null, layer: e.layer },
      });
    });

    setNodes(layoutWithDagre(rawNodes, rawEdges, rankdir));
    setEdges(rawEdges);
  }, [actors, layeredEdges, segments, onNavigate, rankdir, setNodes, setEdges]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      minZoom={0.4}
      maxZoom={1.6}
      proOptions={{ hideAttribution: true }}
      nodesDraggable
      nodesConnectable={false}
      elementsSelectable
      panOnDrag
      zoomOnScroll={false}
      zoomOnPinch
      className="!bg-transparent"
    >
      <Background
        variant={BackgroundVariant.Dots}
        gap={18}
        size={1}
        color="rgba(255,255,255,0.06)"
      />
      <Controls
        showInteractive={false}
        className="!bg-[#0b0b0c]/90 !border !border-white/[0.08] !rounded-lg overflow-hidden [&>button]:!bg-transparent [&>button]:!border-white/[0.08] [&>button]:!text-gray-200 [&>button:hover]:!bg-white/[0.06]"
      />
    </ReactFlow>
  );
}

/* ---------- Composant principal ---------- */

export default function FlowDiagram({
  flows,
  segments = [],
  onSegmentActivate,
  graphHeightClassName = "h-[520px]",
}: Props) {
  const [active, setActive] = useState<FlowLayer>("all");

  const actors = useMemo(() => normalizeActors(flows.acteurs), [flows.acteurs]);

  const actorsSorted = useMemo(() => {
    const copy = [...actors];
    copy.sort((a, b) => {
      const skA = segmentKeyForActor(a, segments) ?? "\uffff";
      const skB = segmentKeyForActor(b, segments) ?? "\uffff";
      if (skA !== skB) return skA.localeCompare(skB);
      return normLabel(a.label).localeCompare(normLabel(b.label));
    });
    return copy;
  }, [actors, segments]);

  const rankdir: "LR" | "TB" =
    (flows.layout || "").toString().trim().toLowerCase() === "vertical"
      ? "TB"
      : "LR";

  const allEdges = useMemo<(FlowEdge & { layer: Exclude<FlowLayer, "all"> })[]>(
    () => [
      ...(flows.flux_valeur ?? []).map((e) => ({ ...e, layer: "valeur" as const })),
      ...(flows.flux_financiers ?? []).map((e) => ({
        ...e,
        layer: "financier" as const,
      })),
      ...(flows.flux_information ?? []).map((e) => ({
        ...e,
        layer: "information" as const,
      })),
    ],
    [flows],
  );

  const counts = useMemo<Record<FlowLayer, number>>(
    () => ({
      all: allEdges.length,
      valeur: (flows.flux_valeur ?? []).length,
      financier: (flows.flux_financiers ?? []).length,
      information: (flows.flux_information ?? []).length,
    }),
    [allEdges, flows],
  );

  const layeredEdges = useMemo(() => {
    if (active === "all") return allEdges;
    return allEdges.filter((e) => e.layer === active);
  }, [active, allEdges]);

  const scrollToSegment = useCallback((key: string) => {
    const el = document.getElementById(`atelier-segment-${key}`);
    const reducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el?.scrollIntoView({
      behavior: reducedMotion ? "auto" : "smooth",
      block: "start",
    });
    el?.classList.add(
      "ring-2",
      "ring-teal-500/50",
      "transition-shadow",
      "duration-500",
    );
    window.setTimeout(() => {
      el?.classList.remove("ring-2", "ring-teal-500/50");
    }, 1600);
  }, []);

  const handleActorNavigate = useCallback(
    (key: string) => {
      if (onSegmentActivate) onSegmentActivate(key);
      else scrollToSegment(key);
    },
    [onSegmentActivate, scrollToSegment],
  );

  const linkedActors = useMemo(
    () => actorsSorted.filter((a) => Boolean(segmentKeyForActor(a, segments))).length,
    [actorsSorted, segments],
  );

  const title = (flows.diagram_title || "").trim();
  const insight = (flows.flow_insight || "").trim();

  const tabs: { id: FlowLayer; label: string; color: string; icon: typeof Package }[] = [
    { id: "all", label: "Tous", color: "#9ca3af", icon: Layers },
    { id: "valeur", label: "Valeur", color: LAYER_META.valeur.color, icon: Package },
    { id: "financier", label: "Cash", color: LAYER_META.financier.color, icon: Banknote },
    {
      id: "information",
      label: "Info",
      color: LAYER_META.information.color,
      icon: Info,
    },
  ];

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-surface-1 p-4 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)]">
      {(title || insight) && (
        <div className="mb-4 flex flex-col gap-1.5 border-b border-white/[0.06] pb-3">
          {title && (
            <div className="flex items-start gap-2">
              <Sparkles
                size={15}
                className="mt-0.5 shrink-0 text-teal-400/90"
                aria-hidden
              />
              <h4 className="text-sm font-semibold text-gray-100 leading-snug">
                {title}
              </h4>
            </div>
          )}
          {insight && (
            <p className="text-[11px] leading-relaxed text-gray-400 pl-[1.35rem]">
              {insight}
            </p>
          )}
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 text-[10px] text-gray-500 uppercase tracking-wider">
          <span className="inline-flex items-center gap-1 rounded-md border border-white/[0.08] bg-white/[0.03] px-2 py-0.5">
            <Layers size={11} className="text-gray-400" aria-hidden />
            {actorsSorted.length} acteurs
          </span>
          <span className="inline-flex items-center gap-1 rounded-md border border-white/[0.08] bg-white/[0.03] px-2 py-0.5">
            {layeredEdges.length} liaisons
          </span>
        </div>
        {segments.length > 0 && linkedActors > 0 && (
          <span className="inline-flex items-center gap-1 text-[10px] text-gray-500">
            <MousePointerClick
              size={11}
              className="text-teal-400/90"
              aria-hidden
            />
            {linkedActors} lien{linkedActors > 1 ? "s" : ""} vers le tableau
          </span>
        )}
      </div>

      <div
        className="mb-3 flex flex-wrap gap-1.5"
        role="tablist"
        aria-label="Type de flux"
      >
        {tabs.map((t) => {
          const Icon = t.icon;
          const isActive = t.id === active;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActive(t.id)}
              style={
                isActive
                  ? {
                      borderColor: `${t.color}66`,
                      backgroundColor: `${t.color}1a`,
                      color: t.color,
                    }
                  : undefined
              }
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? ""
                  : "border-white/[0.06] bg-transparent text-gray-500 hover:border-white/[0.1] hover:text-gray-300"
              }`}
            >
              <Icon size={12} aria-hidden />
              {t.label}
              <span
                className={`ml-0.5 rounded-full px-1.5 py-0.5 text-[9.5px] font-semibold ${
                  isActive ? "bg-black/30" : "bg-white/[0.05] text-gray-500"
                }`}
              >
                {counts[t.id] ?? 0}
              </span>
            </button>
          );
        })}
      </div>

      {/* ---- Légende ---- */}
      <div className="mb-2 flex flex-wrap gap-2 text-[10px] text-gray-500">
        {(["valeur", "financier", "information"] as const).map((k) => {
          const m = LAYER_META[k];
          return (
            <span key={k} className="inline-flex items-center gap-1">
              <span
                className="inline-block h-2 w-4 rounded-sm"
                style={{ backgroundColor: m.color }}
              />
              {m.label}
            </span>
          );
        })}
      </div>

      {/* ---- Graphe ---- */}
      {actorsSorted.length === 0 ? (
        <p className="rounded-lg border border-white/[0.06] bg-surface-2/60 py-8 text-center text-xs italic text-gray-500">
          Aucun acteur identifié.
        </p>
      ) : (
        <div
          className={`${graphHeightClassName} w-full overflow-hidden rounded-xl border border-white/[0.06] bg-[#0a0a0b]`}
        >
          <ReactFlowProvider>
            <FlowGraph
              actors={actorsSorted}
              layeredEdges={layeredEdges}
              segments={segments}
              onNavigate={handleActorNavigate}
              rankdir={rankdir}
            />
          </ReactFlowProvider>
        </div>
      )}

      <p className="mt-2 text-[10px] text-gray-600">
        Glisser-déposer pour réorganiser · pincer ou contrôles pour zoomer ·
        {onSegmentActivate
          ? " Acteur relié à un segment : fait défiler vers le tableau correspondant (colonne de droite si visible)."
          : " Acteur relié à un segment : fait défiler jusqu’au bloc correspondant."}
      </p>
    </div>
  );
}
