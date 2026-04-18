import { NextRequest, NextResponse } from "next/server";

/**
 * Relais `/api/*` → backend FastAPI (même rôle que l’ancien `rewrites` de next.config).
 *
 * Les rewrites Next utilisent un client HTTP avec timeout court (~30s en dev) :
 * `POST /api/agent/send` (Atelier) peut dépasser ce délai → `net::ERR_CONNECTION_CLOSED`.
 * Ce handler utilise `fetch` côté serveur sans cette limite.
 */
export const runtime = "nodejs";

/** Déploiement serverless (ex. Vercel) — ignoré en `next dev` / Node classique. */
export const maxDuration = 300;

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
]);

function backendBase(): string {
  return (process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );
}

function buildTarget(segments: string[], search: string): string {
  const base = backendBase();
  const suffix = segments.length ? segments.join("/") : "";
  const pathPart = suffix ? `/${suffix}` : "";
  return `${base}/api${pathPart}${search}`;
}

function copyHeaders(src: Headers): Headers {
  const out = new Headers();
  src.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return;
    out.append(key, value);
  });
  return out;
}

async function proxy(
  req: NextRequest,
  segments: string[],
): Promise<Response> {
  const target = buildTarget(segments, req.nextUrl.search);
  const headers = copyHeaders(req.headers);
  const method = req.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";

  const init: RequestInit & { duplex?: "half" } = {
    method,
    headers,
    redirect: "manual",
  };
  if (hasBody && req.body) {
    init.body = req.body;
    init.duplex = "half";
  }

  const upstream = await fetch(target, init);
  const outHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return;
    outHeaders.append(key, value);
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: outHeaders,
  });
}

type RouteCtx = { params: Promise<{ path?: string[] }> };

export async function GET(req: NextRequest, ctx: RouteCtx) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export async function POST(req: NextRequest, ctx: RouteCtx) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export async function PATCH(req: NextRequest, ctx: RouteCtx) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export async function DELETE(req: NextRequest, ctx: RouteCtx) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}

export async function PUT(req: NextRequest, ctx: RouteCtx) {
  const { path } = await ctx.params;
  return proxy(req, path ?? []);
}
