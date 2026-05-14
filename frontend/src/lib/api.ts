const API_BASE = "/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("monv_token");
}

function getHeaders(): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export type ApiFetchOptions = {
  signal?: AbortSignal;
};

/** Détail FastAPI : chaîne, liste de {msg}, ou autre — exploitable dans `new Error(...)`. */
function formatApiDetail(detail: unknown): string {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg?: unknown }).msg ?? "");
      }
      return typeof item === "string" ? item : JSON.stringify(item);
    });
    return parts.filter(Boolean).join(" — ");
  }
  if (typeof detail === "object") return JSON.stringify(detail).slice(0, 400);
  return String(detail);
}

function messageFromErrorBody(status: number, text: string): string {
  const trimmed = text.trim();
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    const msg = formatApiDetail(parsed?.detail);
    if (msg) return msg;
  } catch {
    /* corps non JSON */
  }
  if (trimmed.startsWith("<")) {
    return `Erreur ${status} (réponse HTML — vérifie le proxy /api et que le backend répond).`;
  }
  return trimmed ? trimmed.slice(0, 280) : `Erreur ${status}`;
}

function parseJsonBody<T>(text: string, okLabel: string): T {
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(okLabel);
  }
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  options?: ApiFetchOptions
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
    signal: options?.signal,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(messageFromErrorBody(res.status, text));
  }
  return parseJsonBody<T>(
    text,
    "Réponse JSON illisible du serveur (HTTP OK mais corps invalide)."
  );
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: getHeaders() });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(messageFromErrorBody(res.status, text));
  }
  return parseJsonBody<T>(
    text,
    "Réponse JSON illisible du serveur (HTTP OK mais corps invalide)."
  );
}

export async function apiPatch<T>(
  path: string,
  body: unknown,
  options?: ApiFetchOptions
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify(body),
    signal: options?.signal,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(messageFromErrorBody(res.status, text));
  }
  return parseJsonBody<T>(
    text,
    "Réponse JSON illisible du serveur (HTTP OK mais corps invalide)."
  );
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(messageFromErrorBody(res.status, text));
  }
}

export function setToken(token: string) {
  localStorage.setItem("monv_token", token);
}

export function clearToken() {
  localStorage.removeItem("monv_token");
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

// --- Types ---

export interface User {
  id: string;
  email: string;
  name: string;
  credits: number;
  credits_unlimited?: boolean;
  created_at: string;
  is_admin?: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface QcmOption {
  id: string;
  label: string;
  free_text?: boolean;
}

export interface QcmQuestion {
  id: string;
  question: string;
  options: QcmOption[];
  multiple?: boolean;
}

export interface QcmPayload {
  intro: string;
  questions: QcmQuestion[];
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  message_type:
    | "text"
    | "results"
    | "clarification"
    | "qcm"
    | "error"
    | "agent_brief"
    | "business_dossier";
  metadata_json: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  mode?: string | null;
  /** Projet (PROJETS) — null = conversation dans Récents. */
  folder_id?: string | null;
  messages: Message[];
}

export interface ProjectFolder {
  id: string;
  name: string;
  sort_position: number;
  created_at: string;
  updated_at: string;
}

export interface ChatResponse {
  conversation_id: string;
  messages: Message[];
}

export interface Template {
  id: string;
  title: string;
  description: string;
  query: string;
  icon: string;
  mode?: string;
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  intent: string;
  results_count: number;
  credits_used: number;
  exported: boolean;
  created_at: string;
}

export interface CreditPack {
  id: string;
  name: string;
  credits: number;
  price_euros: number;
  price_per_credit: number;
}

export interface ExportResponse {
  download_url: string;
  filename: string;
  credits_used: number;
}

// --- Agent « Atelier » -------------------------------------------------------

export interface AgentSendRequest {
  conversation_id?: string | null;
  pitch?: string;
  answers?: string;
  /** Projet existant ; si absent au 1er tour, l’API crée un nouveau projet. */
  folder_id?: string | null;
}

export interface AgentSendResponse {
  conversation_id: string;
  messages: Message[];
  folder_id?: string | null;
}

export interface ProjectBrief {
  nom: string;
  tagline: string;
  secteur: string;
  localisation: string;
  cible: string;
  budget: string;
  modele_revenus: string;
  ambition: string;
  budget_min_eur?: number | null;
  budget_max_eur?: number | null;
  budget_hypotheses?: string[];
}

export interface BusinessCanvas {
  proposition_valeur: string[];
  segments_clients: string[];
  canaux: string[];
  relation_client: string[];
  sources_revenus: string[];
  ressources_cles: string[];
  activites_cles: string[];
  partenaires_cles: string[];
  structure_couts: string[];
}

export interface FlowEdge {
  origine: string;
  destination: string;
  label: string;
  detail?: string | null;
  pattern?: string | null;
}

/** Acteur du schéma ; `segment_key` relie au tableau MONV du même identifiant. */
export interface FlowActor {
  label: string;
  segment_key: string | null;
  actor_id?: string | null;
  role?: string | null;
  hint?: string | null;
  emphasis?: string | null;
}

export type FlowDiagramLayout = "radial" | "horizontal" | "vertical";

export interface FlowMap {
  /** Anciennes sessions : tableau de chaînes ; dossiers récents : objets `FlowActor`. */
  acteurs: FlowActor[] | string[];
  flux_valeur: FlowEdge[];
  flux_financiers: FlowEdge[];
  flux_information: FlowEdge[];
  diagram_title?: string | null;
  layout?: FlowDiagramLayout | string | null;
  flow_insight?: string | null;
}

export interface SegmentResult {
  key: string;
  label: string;
  description: string;
  mode: string;
  icon: string;
  query: string;
  search_id: string | null;
  total: number;
  credits_required: number;
  columns: string[];
  preview: Record<string, unknown>[];
  map_points: Record<string, unknown>[];
  error?: string | null;
  out_of_scope?: boolean;
  out_of_scope_note?: string | null;
  total_relevant?: number | null;
  relevance_threshold?: number | null;
}

export interface ChecklistItem {
  label: string;
  guide: string;
}

export interface ChecklistSection {
  title: string;
  subtitle?: string | null;
  items: ChecklistItem[];
}

export interface AtelierChecklist {
  headline: string;
  lede?: string | null;
  sections: ChecklistSection[];
  pitfalls_title?: string | null;
  pitfalls: ChecklistItem[];
}

export interface AgentSynthesis {
  forces: string[];
  risques: string[];
  prochaines_etapes: string[];
  kpis: string[];
  budget_estimatif: string | null;
  /** Dossiers générés avant extension : peut être absent. */
  ordres_grandeur?: string[];
  conseil_semaine?: string | null;
  checklist?: AtelierChecklist | null;
}

export interface BusinessDossierPayload {
  mode: "atelier";
  brief: ProjectBrief;
  canvas: BusinessCanvas;
  flows: FlowMap;
  segments: SegmentResult[];
  synthesis: AgentSynthesis;
  version?: number;
  generated_at?: string | null;
  total_raw?: number;
  total_unique?: number;
  total_relevant?: number;
  total_credits?: number;
}

/** Zones recalculées après édition du brief (Phase 3 — itération dossier). */
export type AtelierImpact = "canvas" | "flows" | "segments";

export interface AtelierGenerationStats {
  llm_calls: number;
  api_calls: number;
  credits_charged: number;
  relevance_removed_per_segment?: Record<string, number>;
}

/** GET /api/agent/dossier/:conversation_id */
export interface AtelierDossierGetResponse {
  message_id: string;
  dossier: BusinessDossierPayload;
}

/** Réponses POST de régénération / mise à jour du dernier dossier Atelier. */
export interface AtelierDossierMutationResponse {
  dossier: BusinessDossierPayload;
  generation_stats: AtelierGenerationStats;
  credits_remaining?: number | null;
}

export interface AtelierSegmentRegenerateBody {
  conversation_id: string;
  query_override?: string | null;
  mode_override?: string | null;
}

export interface AtelierCanvasRegenerateBody {
  conversation_id: string;
}

export interface AtelierChecklistRegenerateBody {
  conversation_id: string;
}

export interface AtelierBriefUpdateBody {
  conversation_id: string;
  brief: ProjectBrief;
  impacts: AtelierImpact[];
}

/** Dernier message dossier + payload JSON (Phase 3). */
export function getAtelierDossier(conversationId: string) {
  return apiGet<AtelierDossierGetResponse>(
    `/agent/dossier/${encodeURIComponent(conversationId)}`
  );
}

/** Relance le pipeline MONV pour un segment du dossier courant. */
export function regenerateAtelierSegment(
  segmentKey: string,
  body: AtelierSegmentRegenerateBody,
  options?: ApiFetchOptions
) {
  return apiPost<AtelierDossierMutationResponse>(
    `/agent/segments/${encodeURIComponent(segmentKey)}/regenerate`,
    body,
    options
  );
}

/** Régénère le canvas BMC à partir du pitch, QCM et brief courants. */
export function regenerateAtelierCanvas(
  body: AtelierCanvasRegenerateBody,
  options?: ApiFetchOptions
) {
  return apiPost<AtelierDossierMutationResponse>(
    "/agent/canvas/regenerate",
    body,
    options
  );
}

/** Régénère uniquement la checklist d’actions (pitch, QCM, brief et synthèse hors checklist). */
export function regenerateAtelierChecklist(
  body: AtelierChecklistRegenerateBody,
  options?: ApiFetchOptions
) {
  return apiPost<AtelierDossierMutationResponse>(
    "/agent/checklist/regenerate",
    body,
    options
  );
}

/** Met à jour le brief puis recalcule canvas / flux / segments selon `impacts`. */
export function updateAtelierBrief(
  body: AtelierBriefUpdateBody,
  options?: ApiFetchOptions
) {
  return apiPost<AtelierDossierMutationResponse>(
    "/agent/brief/update",
    body,
    options
  );
}

// --- Super Admin (graphes agents) ---

export interface AdminAgentSummary {
  agent_id: string;
  label: string;
  active_version_id: string | null;
  active_version_number: number | null;
  last_modified_at: string | null;
  primary_model: string;
  errors_24h: number;
  runs_7d: number;
}

export interface AdminAgentVersion {
  id: string;
  agent_id: string;
  version_number: number;
  label: string;
  overrides_json: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  is_active: boolean;
  parent_version_id?: string | null;
}

export interface AdminAgentGraph {
  agent_id: string;
  label: string;
  graph: {
    nodes: AdminGraphNode[];
    edges: AdminGraphEdge[];
  };
  active_version: AdminAgentVersion | null;
}

export interface AdminApiEndpoint {
  method: string;
  path: string;
  purpose?: string;
  params?: string[];
}

export interface AdminApiAuth {
  type: string;
  header?: string | null;
  env_var?: string | null;
}

export interface AdminApiMeta {
  provider?: string;
  base_url?: string;
  base_url_env?: string | null;
  endpoints?: AdminApiEndpoint[];
  auth?: AdminApiAuth | null;
  cost?: string;
  rate_limit?: string;
  timeout_s?: number;
  doc_url?: string;
  usage?: string;
  triggered_by?: string;
}

export interface AdminGraphNode {
  id: string;
  label: string;
  type: string;
  model_ref?: string;
  source_file?: string;
  default_params?: Record<string, unknown>;
  default_prompt_preview?: string;
  effective?: Record<string, unknown> | null;
  sub_blocks?: string[];
  fallback?: string;
  errors?: string[];
  inputs?: { name: string; type: string }[];
  outputs?: { name: string; type: string }[];
  api?: AdminApiMeta;
}

export interface AdminGraphEdge {
  from: string;
  to: string;
  kind?: string;
  condition?: string;
}

export interface AdminTestResponse {
  run_id: string;
  status: string;
  steps: { block_id: string; status: string; latency_ms?: number }[];
}

export interface AdminSettings {
  models: Record<string, string>;
  api_keys_present: Record<string, boolean>;
  flags: Record<string, boolean>;
}

export function adminMe(): Promise<{ is_admin: boolean; email: string }> {
  return apiGet("/admin/me");
}

export function adminListAgents(): Promise<AdminAgentSummary[]> {
  return apiGet("/admin/agents");
}

export function adminGetGraph(agentId: string): Promise<AdminAgentGraph> {
  return apiGet(`/admin/agents/${encodeURIComponent(agentId)}/graph`);
}

export function adminListVersions(agentId: string): Promise<AdminAgentVersion[]> {
  return apiGet(`/admin/agents/${encodeURIComponent(agentId)}/versions`);
}

export function adminCreateVersion(
  agentId: string,
  body: { label?: string; overrides: Record<string, Record<string, unknown>> }
): Promise<AdminAgentVersion> {
  return apiPost(`/admin/agents/${encodeURIComponent(agentId)}/versions`, body);
}

export function adminPublishVersion(agentId: string, versionId: string): Promise<AdminAgentVersion> {
  return apiPost(
    `/admin/agents/${encodeURIComponent(agentId)}/versions/${encodeURIComponent(versionId)}/publish`,
    {}
  );
}

export function adminRollbackVersion(agentId: string, versionId: string): Promise<AdminAgentVersion> {
  return apiPost(
    `/admin/agents/${encodeURIComponent(agentId)}/versions/${encodeURIComponent(versionId)}/rollback`,
    {}
  );
}

export function adminTestAgent(
  agentId: string,
  body: { message?: string; full_pipeline?: boolean }
): Promise<AdminTestResponse> {
  return apiPost(`/admin/agents/${encodeURIComponent(agentId)}/test`, body);
}

export function adminListRuns(params?: {
  agent_id?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: Record<string, unknown>[]; limit: number; offset: number }> {
  const q = new URLSearchParams();
  if (params?.agent_id) q.set("agent_id", params.agent_id);
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const s = q.toString();
  return apiGet(`/admin/runs${s ? `?${s}` : ""}`);
}

export function adminGetRun(runId: string): Promise<{
  run: Record<string, unknown>;
  steps: Record<string, unknown>[];
}> {
  return apiGet(`/admin/runs/${encodeURIComponent(runId)}`);
}

export function adminGetSettings(): Promise<AdminSettings> {
  return apiGet("/admin/settings");
}

export function adminExportAgent(agentId: string): Promise<Record<string, unknown>> {
  return apiGet(`/admin/agents/${encodeURIComponent(agentId)}/export`);
}

export function adminImportAgent(
  agentId: string,
  payload: Record<string, unknown>
): Promise<AdminAgentVersion> {
  return apiPost(`/admin/agents/${encodeURIComponent(agentId)}/import`, payload);
}

export function adminDiffVersions(
  agentId: string,
  fromVersion: string,
  toVersion: string
): Promise<{ blocks: { block_id: string; from: unknown; to: unknown }[] }> {
  return apiGet(
    `/admin/agents/${encodeURIComponent(agentId)}/diff?from_version=${encodeURIComponent(fromVersion)}&to_version=${encodeURIComponent(toVersion)}`
  );
}
