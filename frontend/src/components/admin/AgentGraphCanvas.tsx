"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import mermaid from "mermaid";
import { useTheme } from "next-themes";
import {
  Maximize2,
  Minimize2,
  Minus,
  Plus,
  RotateCcw,
  ScanLine,
} from "lucide-react";
import type { AdminGraphEdge, AdminGraphNode } from "@/lib/api";

type Status = "idle" | "running" | "ok" | "error";

type Props = {
  graphNodes: AdminGraphNode[];
  graphEdges: AdminGraphEdge[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  stepStatus?: Record<string, Status>;
};

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 4;
const DRAG_CLICK_THRESHOLD = 4;

const TYPE_CLASS_DEFS: Record<string, { fill: string; stroke: string; color: string }> = {
  llm: { fill: "#ede9fe", stroke: "#7c3aed", color: "#1e1b4b" },
  tool: { fill: "#dbeafe", stroke: "#2563eb", color: "#1e3a8a" },
  api: { fill: "#cffafe", stroke: "#0891b2", color: "#164e63" },
  output: { fill: "#dcfce7", stroke: "#16a34a", color: "#14532d" },
  condition: { fill: "#fef3c7", stroke: "#d97706", color: "#7c2d12" },
  fallback: { fill: "#fee2e2", stroke: "#dc2626", color: "#7f1d1d" },
  default: { fill: "#f1f5f9", stroke: "#64748b", color: "#0f172a" },
};

const TYPE_CLASS_DEFS_DARK: Record<string, { fill: string; stroke: string; color: string }> = {
  llm: { fill: "#3b1d75", stroke: "#a78bfa", color: "#ede9fe" },
  tool: { fill: "#1d3a73", stroke: "#60a5fa", color: "#dbeafe" },
  api: { fill: "#155e75", stroke: "#22d3ee", color: "#cffafe" },
  output: { fill: "#14532d", stroke: "#4ade80", color: "#dcfce7" },
  condition: { fill: "#78350f", stroke: "#fbbf24", color: "#fef3c7" },
  fallback: { fill: "#7f1d1d", stroke: "#f87171", color: "#fee2e2" },
  default: { fill: "#1e293b", stroke: "#94a3b8", color: "#e2e8f0" },
};

function safeMermaidId(id: string): string {
  return id.replace(/[^a-zA-Z0-9_]/g, "_");
}

function escapeLabel(s: string): string {
  return s.replace(/"/g, "'").replace(/\n/g, " ");
}

function nodeTypeFor(n: AdminGraphNode): string {
  const t = (n.type || "").toLowerCase();
  if (t in TYPE_CLASS_DEFS) return t;
  return "default";
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function buildMermaid(
  nodes: AdminGraphNode[],
  edges: AdminGraphEdge[],
  selectedId: string | null,
  stepStatus: Record<string, Status>,
  isDark: boolean
): string {
  const palette = isDark ? TYPE_CLASS_DEFS_DARK : TYPE_CLASS_DEFS;
  const lines: string[] = [];
  lines.push("flowchart LR");
  const pushClass = (name: keyof typeof TYPE_CLASS_DEFS, extra = "") => {
    const c = palette[name];
    lines.push(
      `  classDef ${name} fill:${c.fill},stroke:${c.stroke},color:${c.color},stroke-width:1.5px,rx:10,ry:10${extra};`
    );
  };
  pushClass("llm");
  pushClass("tool");
  pushClass("api", ",stroke-width:2px");
  pushClass("output");
  pushClass("condition");
  pushClass("fallback");
  pushClass("default");

  for (const n of nodes) {
    const safeId = safeMermaidId(n.id);
    const subLines: string[] = [];
    if (n.model_ref) {
      subLines.push(
        `<span style='font-family:ui-monospace,monospace;font-size:10px;opacity:0.78'>${escapeLabel(
          n.model_ref
        )}</span>`
      );
    }
    if (n.type === "api" && n.api) {
      const ep = (n.api.endpoints && n.api.endpoints[0]) || null;
      if (ep) {
        subLines.push(
          `<span style='font-family:ui-monospace,monospace;font-size:10px;opacity:0.85'>${escapeLabel(
            `${ep.method} ${ep.path || ""}`.trim()
          )}</span>`
        );
      }
      if (n.api.provider) {
        subLines.push(
          `<span style='font-size:10px;opacity:0.7'>${escapeLabel(n.api.provider)}</span>`
        );
      }
      const authType = n.api.auth?.type || "";
      if (authType && authType !== "none") {
        subLines.push(
          `<span style='font-size:9.5px;opacity:0.65'>auth: ${escapeLabel(authType)}</span>`
        );
      } else if (authType === "none") {
        subLines.push(`<span style='font-size:9.5px;opacity:0.65'>auth: aucune</span>`);
      }
    }
    const sub = subLines.length ? `<br/>${subLines.join("<br/>")}` : "";
    const label = `<b>${escapeLabel(n.label)}</b>${sub}`;
    if (n.type === "api") {
      lines.push(`  ${safeId}(["${label}"]):::api`);
    } else {
      lines.push(`  ${safeId}["${label}"]:::${nodeTypeFor(n)}`);
    }
  }

  edges.forEach((e) => {
    const from = safeMermaidId(e.from);
    const to = safeMermaidId(e.to);
    const arrow = e.kind === "branch" ? "-.->" : "-->";
    if (e.condition) {
      lines.push(`  ${from} ${arrow}|"${escapeLabel(e.condition)}"| ${to}`);
    } else {
      lines.push(`  ${from} ${arrow} ${to}`);
    }
  });

  if (selectedId) {
    lines.push(`  style ${safeMermaidId(selectedId)} stroke:#0ea5e9,stroke-width:3px;`);
  }
  for (const [bid, status] of Object.entries(stepStatus)) {
    const safe = safeMermaidId(bid);
    if (status === "ok") lines.push(`  style ${safe} fill:#bbf7d0,stroke:#15803d,stroke-width:3px;`);
    else if (status === "error") lines.push(`  style ${safe} fill:#fecaca,stroke:#b91c1c,stroke-width:3px;`);
    else if (status === "running") lines.push(`  style ${safe} fill:#fde68a,stroke:#a16207,stroke-width:3px;`);
  }

  return lines.join("\n");
}

export function AgentGraphCanvas({ graphNodes, graphEdges, selectedId, onSelect, stepStatus }: Props) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const viewportRef = useRef<HTMLDivElement | null>(null);
  const innerRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const onSelectRef = useRef(onSelect);
  const draggingRef = useRef<{ x: number; y: number; dist: number } | null>(null);
  const renderSeqRef = useRef(0);
  const fitOnNextRenderRef = useRef(true);

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [grabbing, setGrabbing] = useState(false);

  const uniqueId = useId();
  const idBase = useMemo(() => `mmd-${uniqueId.replace(/[^a-zA-Z0-9_-]/g, "")}`, [uniqueId]);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      theme: isDark ? "dark" : "base",
      fontFamily: "var(--font-sans), system-ui, -apple-system, sans-serif",
      themeVariables: {
        fontSize: "13px",
        primaryColor: isDark ? "#1e293b" : "#f8fafc",
        primaryBorderColor: isDark ? "#475569" : "#cbd5e1",
        primaryTextColor: isDark ? "#e2e8f0" : "#0f172a",
        lineColor: isDark ? "#64748b" : "#94a3b8",
        edgeLabelBackground: isDark ? "#0f172a" : "#ffffff",
      },
      flowchart: {
        curve: "basis",
        htmlLabels: true,
        nodeSpacing: 50,
        rankSpacing: 80,
        padding: 12,
      },
    });
  }, [isDark]);

  const fitToView = useCallback(() => {
    const viewport = viewportRef.current;
    const inner = innerRef.current;
    if (!viewport || !inner) return;
    const svg = inner.querySelector("svg");
    if (!svg) return;

    inner.style.transform = "translate(0px, 0px) scale(1)";
    const svgBox = svg.getBoundingClientRect();
    const vw = viewport.clientWidth;
    const vh = viewport.clientHeight;
    if (!svgBox.width || !svgBox.height || !vw || !vh) {
      setZoom(1);
      setPan({ x: 0, y: 0 });
      return;
    }
    const PADDING = 32;
    const zx = (vw - PADDING * 2) / svgBox.width;
    const zy = (vh - PADDING * 2) / svgBox.height;
    const newZoom = clamp(Math.min(zx, zy, 1.5), MIN_ZOOM, MAX_ZOOM);
    const targetW = svgBox.width * newZoom;
    const targetH = svgBox.height * newZoom;
    setZoom(newZoom);
    setPan({ x: (vw - targetW) / 2, y: (vh - targetH) / 2 });
  }, []);

  const focusOnNode = useCallback((nodeId: string) => {
    const viewport = viewportRef.current;
    const inner = innerRef.current;
    if (!viewport || !inner) return;
    const safe = safeMermaidId(nodeId);
    const nodeEl = inner.querySelector<SVGGElement>(`g.node[id^='flowchart-${safe}-']`);
    if (!nodeEl) return;

    const vw = viewport.clientWidth;
    const vh = viewport.clientHeight;
    const innerRect = inner.getBoundingClientRect();
    const nodeRect = nodeEl.getBoundingClientRect();

    const currentZoom = zoom;
    const offsetX = (nodeRect.left - innerRect.left) / currentZoom;
    const offsetY = (nodeRect.top - innerRect.top) / currentZoom;
    const nodeW = nodeRect.width / currentZoom;
    const nodeH = nodeRect.height / currentZoom;

    const targetZoom = clamp(1.6, MIN_ZOOM, MAX_ZOOM);
    setZoom(targetZoom);
    setPan({
      x: vw / 2 - (offsetX + nodeW / 2) * targetZoom,
      y: vh / 2 - (offsetY + nodeH / 2) * targetZoom,
    });
  }, [zoom]);

  useEffect(() => {
    const container = containerRef.current;
    const inner = innerRef.current;
    if (!container || !inner) return;

    let cancelled = false;
    const code = buildMermaid(graphNodes, graphEdges, selectedId, stepStatus ?? {}, isDark);

    renderSeqRef.current += 1;
    const renderId = `${idBase}-${renderSeqRef.current}`;

    mermaid
      .render(renderId, code)
      .then(({ svg }) => {
        if (cancelled || !innerRef.current) return;
        innerRef.current.innerHTML = svg;

        const svgEl = innerRef.current.querySelector("svg");
        if (!svgEl) return;
        svgEl.removeAttribute("style");
        svgEl.removeAttribute("height");
        svgEl.removeAttribute("width");
        svgEl.style.display = "block";
        svgEl.style.maxWidth = "none";
        svgEl.style.pointerEvents = "auto";

        const nodeEls = svgEl.querySelectorAll<SVGGElement>("g.node");
        nodeEls.forEach((g) => {
          const idAttr = g.id || "";
          const match = idAttr.match(/^flowchart-(.+)-\d+$/);
          if (!match) return;
          const safe = match[1];
          const original = graphNodes.find((n) => safeMermaidId(n.id) === safe)?.id;
          if (!original) return;
          g.style.cursor = "pointer";
          g.addEventListener("click", (ev) => {
            ev.stopPropagation();
            if (draggingRef.current && draggingRef.current.dist > DRAG_CLICK_THRESHOLD) return;
            onSelectRef.current(original);
          });
          g.addEventListener("dblclick", (ev) => {
            ev.stopPropagation();
            ev.preventDefault();
            focusOnNode(original);
          });
        });

        if (fitOnNextRenderRef.current) {
          fitOnNextRenderRef.current = false;
          requestAnimationFrame(fitToView);
        }
      })
      .catch(() => {
        if (!cancelled && innerRef.current) {
          innerRef.current.innerHTML =
            '<div class="p-4 text-sm text-destructive">Erreur de rendu du graphe.</div>';
        }
      });

    return () => {
      cancelled = true;
    };
  }, [graphNodes, graphEdges, selectedId, stepStatus, isDark, idBase, fitToView, focusOnNode]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey && Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        return;
      }
      e.preventDefault();
      const rect = viewport.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      setZoom((z) => {
        const newZoom = clamp(z * factor, MIN_ZOOM, MAX_ZOOM);
        const ratio = newZoom / z;
        setPan((p) => ({
          x: mx - (mx - p.x) * ratio,
          y: my - (my - p.y) * ratio,
        }));
        return newZoom;
      });
    };

    viewport.addEventListener("wheel", onWheel, { passive: false });
    return () => viewport.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (target?.isContentEditable) return;
      if (!containerRef.current) return;
      if (!containerRef.current.matches(":hover") && !isFullscreen) return;
      if (e.key === "+" || (e.key === "=" && e.shiftKey)) {
        e.preventDefault();
        setZoom((z) => clamp(z * 1.2, MIN_ZOOM, MAX_ZOOM));
      } else if (e.key === "-" || e.key === "_") {
        e.preventDefault();
        setZoom((z) => clamp(z / 1.2, MIN_ZOOM, MAX_ZOOM));
      } else if (e.key === "0") {
        e.preventDefault();
        setZoom(1);
        setPan({ x: 0, y: 0 });
      } else if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        fitToView();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fitToView, isFullscreen]);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest("g.node")) {
      draggingRef.current = { x: e.clientX, y: e.clientY, dist: 0 };
      return;
    }
    e.currentTarget.setPointerCapture(e.pointerId);
    draggingRef.current = { x: e.clientX, y: e.clientY, dist: 0 };
    setGrabbing(true);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const drag = draggingRef.current;
    if (!drag) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    drag.dist = Math.max(drag.dist, Math.hypot(dx, dy));
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
      drag.x = e.clientX;
      drag.y = e.clientY;
    }
  };
  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    setGrabbing(false);
    const drag = draggingRef.current;
    if (drag && drag.dist <= DRAG_CLICK_THRESHOLD) {
      if (!(e.target as HTMLElement).closest("g.node")) {
        onSelectRef.current(null);
      }
    }
    setTimeout(() => {
      draggingRef.current = null;
    }, 0);
  };

  const zoomIn = useCallback(
    () => setZoom((z) => clamp(z * 1.2, MIN_ZOOM, MAX_ZOOM)),
    []
  );
  const zoomOut = useCallback(
    () => setZoom((z) => clamp(z / 1.2, MIN_ZOOM, MAX_ZOOM)),
    []
  );
  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  return (
    <div
      ref={containerRef}
      className={
        "relative w-full overflow-hidden rounded-2xl border border-border bg-card " +
        (isFullscreen ? "fixed inset-2 z-50 shadow-2xl" : "")
      }
    >
      <div className="flex flex-wrap items-center gap-3 border-b border-border bg-muted/30 px-4 py-2 text-[11px]">
        <LegendDot color="#7c3aed" label="LLM" />
        <LegendDot color="#2563eb" label="Outil interne" />
        <LegendDot color="#0891b2" label="API externe" shape="pill" />
        <LegendDot color="#16a34a" label="Sortie" />
        <LegendDot color="#d97706" label="Condition" />
        <LegendDot color="#dc2626" label="Fallback" />
        <span className="ml-auto hidden text-muted-foreground sm:inline">
          Molette = zoom · clic-glisser = déplacer · double-clic sur un bloc = zoom dessus
        </span>
      </div>
      <div
        ref={viewportRef}
        className="relative overflow-hidden bg-background select-none"
        style={{
          height: isFullscreen ? "calc(100vh - 100px)" : "min(72vh, 700px)",
          minHeight: 420,
          cursor: grabbing ? "grabbing" : "grab",
          touchAction: "none",
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div
          ref={innerRef}
          className="mermaid-wrapper origin-top-left"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "0 0",
            willChange: "transform",
            transition: draggingRef.current ? "none" : "transform 80ms linear",
          }}
        />

        <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
          <div className="pointer-events-auto inline-flex items-center gap-1 rounded-full border border-border bg-card/95 px-1 py-1 shadow-md backdrop-blur">
            <ToolbarBtn onClick={zoomOut} title="Zoom −  (touche −)" aria-label="Zoom out">
              <Minus className="size-3.5" />
            </ToolbarBtn>
            <button
              type="button"
              onClick={resetView}
              className="px-2 py-1 font-mono text-[11px] text-muted-foreground hover:text-foreground"
              title="Réinitialiser (touche 0)"
            >
              {Math.round(zoom * 100)}%
            </button>
            <ToolbarBtn onClick={zoomIn} title="Zoom +  (touche +)" aria-label="Zoom in">
              <Plus className="size-3.5" />
            </ToolbarBtn>
            <span className="mx-1 h-4 w-px bg-border" />
            <ToolbarBtn onClick={fitToView} title="Ajuster à l'écran (touche F)" aria-label="Fit to screen">
              <ScanLine className="size-3.5" />
            </ToolbarBtn>
            <ToolbarBtn onClick={resetView} title="Recentrer (touche 0)" aria-label="Reset view">
              <RotateCcw className="size-3.5" />
            </ToolbarBtn>
            <span className="mx-1 h-4 w-px bg-border" />
            <ToolbarBtn
              onClick={() => setIsFullscreen((v) => !v)}
              title={isFullscreen ? "Quitter plein écran" : "Plein écran"}
              aria-label="Toggle fullscreen"
            >
              {isFullscreen ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
            </ToolbarBtn>
          </div>
        </div>
      </div>
    </div>
  );
}

function ToolbarBtn({
  children,
  onClick,
  title,
  "aria-label": ariaLabel,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
  "aria-label": string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={ariaLabel}
      className="inline-flex size-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      {children}
    </button>
  );
}

function LegendDot({ color, label, shape = "dot" }: { color: string; label: string; shape?: "dot" | "pill" }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
      <span
        className={shape === "pill" ? "inline-block h-2.5 w-5 rounded-full" : "inline-block size-2.5 rounded-full"}
        style={{ background: color, boxShadow: `0 0 0 2px ${color}33` }}
        aria-hidden
      />
      <span>{label}</span>
    </span>
  );
}
