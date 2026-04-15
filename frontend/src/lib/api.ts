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

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
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
  message_type: "text" | "results" | "clarification" | "qcm" | "error";
  metadata_json: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
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
