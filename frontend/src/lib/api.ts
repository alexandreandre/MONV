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
  messages: Message[];
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
}

export interface AgentSendResponse {
  conversation_id: string;
  messages: Message[];
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
}

export interface FlowMap {
  acteurs: string[];
  flux_valeur: FlowEdge[];
  flux_financiers: FlowEdge[];
  flux_information: FlowEdge[];
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
}

export interface AgentSynthesis {
  forces: string[];
  risques: string[];
  prochaines_etapes: string[];
  kpis: string[];
  budget_estimatif: string | null;
}

export interface BusinessDossierPayload {
  mode: "atelier";
  brief: ProjectBrief;
  canvas: BusinessCanvas;
  flows: FlowMap;
  segments: SegmentResult[];
  synthesis: AgentSynthesis;
}
