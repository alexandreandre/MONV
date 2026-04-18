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
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erreur serveur" }));
    throw new Error(err.detail || `Erreur ${res.status}`);
  }
  return res.json();
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: getHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erreur serveur" }));
    throw new Error(err.detail || `Erreur ${res.status}`);
  }
  return res.json();
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
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erreur serveur" }));
    throw new Error(err.detail || `Erreur ${res.status}`);
  }
  return res.json();
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erreur serveur" }));
    throw new Error(err.detail || `Erreur ${res.status}`);
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
