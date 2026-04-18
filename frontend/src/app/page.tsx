"use client";

import {
  useState,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useCallback,
  Suspense,
} from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
  apiPost,
  apiGet,
  apiPatch,
  apiDelete,
  clearToken,
  isLoggedIn,
  type User,
  type Message,
  type Conversation,
  type ChatResponse,
  type ExportResponse,
  type AgentSendResponse,
  type BusinessDossierPayload,
  type ProjectFolder,
} from "@/lib/api";
import { LANDING_TEMPLATES } from "@/lib/landingTemplates";
import {
  DEFAULT_MODE,
  MODE_META,
  normalizeMode,
  type Mode,
} from "@/lib/modes";
import { ATELIER_MODE_LABEL } from "@/lib/agents";
import AuthModal from "@/components/AuthModal";
import Sidebar from "@/components/Sidebar";
import ProjectHub from "@/components/ProjectHub";
import ChatInput from "@/components/ChatInput";
import ChatMessage from "@/components/ChatMessage";
import TemplateCards from "@/components/TemplateCards";
import ModeSelector from "@/components/ModeSelector";
import AgentWelcome from "@/components/AgentWelcome";
import Dashboard from "@/components/Dashboard";
import CreditsPage from "@/components/CreditsPage";
import ToastContainer, { type ToastData } from "@/components/Toast";
import MobileHeader from "@/components/MobileHeader";
import PipelineProgress, { type PipelineStep } from "@/components/PipelineProgress";
import { CONV_SEARCH_PARAM } from "@/lib/conversationNav";
import { ArrowRight, Compass } from "lucide-react";

type Page = "chat" | "dashboard" | "credits" | "atelier";

function isAbortError(e: unknown): boolean {
  return (
    (typeof DOMException !== "undefined" &&
      e instanceof DOMException &&
      e.name === "AbortError") ||
    (e instanceof Error && e.name === "AbortError")
  );
}

/** Premier mot du nom affiché comme prénom (donnée actuelle côté API : un seul champ `name`). */
function displayFirstName(fullName: string): string | null {
  const w = fullName.trim().split(/\s+/)[0];
  if (!w) return null;
  return (
    w.charAt(0).toLocaleUpperCase("fr-FR") +
    w.slice(1).toLocaleLowerCase("fr-FR")
  );
}

function HomeInner() {
  const [user, setUser] = useState<User | null>(null);
  /** Jeton présent : afficher sidebar / header tout de suite, avant /auth/me */
  const [sessionHint, setSessionHint] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [authInitialMode, setAuthInitialMode] = useState<"login" | "register">(
    "register"
  );

  const openAuth = useCallback((mode: "login" | "register" = "register") => {
    setAuthInitialMode(mode);
    setShowAuth(true);
  }, []);
  const router = useRouter();
  const pathname = usePathname() || "/";
  const searchParams = useSearchParams();
  const lastSyncedConvParamRef = useRef<string | null>(null);

  const [page, setPage] = useState<Page>("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [projectFolders, setProjectFolders] = useState<ProjectFolder[]>([]);
  /** Projet sélectionné (vue type ChatGPT) — null = accueil recherche global. */
  const [activeProjectFolderId, setActiveProjectFolderId] = useState<string | null>(
    null
  );
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [currentConvId, setCurrentConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  /** Mode pour les NOUVELLES recherches (landing). Une conversation existante
   *  garde le mode avec lequel elle a été créée — déduit côté serveur. */
  const [selectedMode, setSelectedMode] = useState<Mode>(DEFAULT_MODE);
  /** Mode de la conversation actuellement chargée (utilisé pour le badge des messages). */
  const [activeConversationMode, setActiveConversationMode] = useState<Mode | null>(null);
  /** True si la conversation chargée a été créée par l'agent Atelier
   *  (mode="atelier" côté DB). Priorité sur `activeConversationMode`. */
  const [isAtelierConversation, setIsAtelierConversation] = useState(false);
  const templates = useMemo(
    () => LANDING_TEMPLATES.filter((t) => normalizeMode(t.mode) === selectedMode),
    [selectedMode]
  );

  const activeProjectFolder = useMemo(
    () => projectFolders.find((f) => f.id === activeProjectFolderId) ?? null,
    [projectFolders, activeProjectFolderId]
  );

  const showProjectHub = Boolean(
    user &&
      activeProjectFolder &&
      !currentConvId &&
      messages.length === 0
  );

  const [sending, setSending] = useState(false);
  const [pipelineStep, setPipelineStep] = useState<PipelineStep>("filtering");
  const [exporting, setExporting] = useState(false);
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sendAbortRef = useRef<AbortController | null>(null);

  const addToast = useCallback(
    (type: ToastData["type"], message: string, duration?: number) => {
      const id = "toast-" + Date.now() + "-" + Math.random();
      setToasts((prev) => [...prev, { id, type, message, duration }]);
    },
    []
  );

  const handleAtelierDossierReplaced = useCallback(
    (dossier: BusinessDossierPayload) => {
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].message_type === "business_dossier") {
            next[i] = {
              ...next[i],
              metadata_json: JSON.stringify(dossier),
            };
            break;
          }
        }
        return next;
      });
    },
    []
  );

  const handleAtelierNotify = useCallback(
    (kind: "success" | "error", message: string) => {
      addToast(kind, message);
    },
    [addToast]
  );

  const handleAtelierCreditsRemaining = useCallback((credits: number) => {
    setUser((u) => (u ? { ...u, credits } : u));
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const replaceConversationInUrl = useCallback(
    (conversationId: string | null) => {
      const next = new URLSearchParams(searchParams.toString());
      if (conversationId) {
        next.set(CONV_SEARCH_PARAM, conversationId);
      } else {
        next.delete(CONV_SEARCH_PARAM);
      }
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams]
  );

  const applyConversationState = useCallback((conv: Conversation) => {
    setCurrentConvId(conv.id);
    setMessages(conv.messages);
    setActiveProjectFolderId(conv.folder_id ?? null);
    const rawMode = conv.mode != null ? String(conv.mode).trim() : "";
    const atelier = rawMode === ATELIER_MODE_LABEL;
    setIsAtelierConversation(atelier);
    setActiveConversationMode(
      atelier || rawMode === "" ? null : normalizeMode(rawMode)
    );
  }, []);

  const loadConversations = useCallback(async () => {
    setConversationsLoading(true);
    try {
      const [convRes, folderRes] = await Promise.allSettled([
        apiGet<Conversation[]>("/chat/conversations"),
        apiGet<ProjectFolder[]>("/chat/project-folders"),
      ]);
      if (convRes.status === "fulfilled") {
        setConversations(convRes.value);
      }
      if (folderRes.status === "fulfilled") {
        setProjectFolders(folderRes.value);
      } else {
        setProjectFolders([]);
      }
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  useLayoutEffect(() => {
    if (isLoggedIn()) setSessionHint(true);
  }, []);

  useEffect(() => {
    if (!isLoggedIn()) {
      setSessionHint(false);
      return;
    }

    let cancelled = false;
    setConversationsLoading(true);
    const token = localStorage.getItem("monv_token");
    if (!token) {
      setConversationsLoading(false);
      setSessionHint(false);
      return;
    }

    (async () => {
      try {
        const [meRes, convRes, folderRes] = await Promise.allSettled([
          apiGet<User>("/auth/me?token=" + token),
          apiGet<Conversation[]>("/chat/conversations"),
          apiGet<ProjectFolder[]>("/chat/project-folders"),
        ]);
        if (cancelled) return;
        if (meRes.status === "rejected") {
          clearToken();
          setUser(null);
          setSessionHint(false);
          setConversations([]);
          setProjectFolders([]);
          return;
        }
        setUser(meRes.value);
        if (convRes.status === "fulfilled") {
          setConversations(convRes.value);
        } else {
          setConversations([]);
        }
        if (folderRes.status === "fulfilled") {
          setProjectFolders(folderRes.value);
        } else {
          setProjectFolders([]);
        }
      } finally {
        if (!cancelled) setConversationsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const handleAuth = (u: User) => {
    setUser(u);
    setShowAuth(false);
    addToast(
      "success",
      u.credits_unlimited
        ? `Bienvenue ${u.name}\u202f! Vous avez des crédits illimités.`
        : `Bienvenue ${u.name}\u202f! Vous avez ${u.credits} crédits.`
    );
    void loadConversations();
  };

  const handleLogout = () => {
    clearToken();
    setSessionHint(false);
    setUser(null);
    setMessages([]);
    setCurrentConvId(null);
    lastSyncedConvParamRef.current = null;
    replaceConversationInUrl(null);
    setActiveProjectFolderId(null);
    setConversations([]);
    setProjectFolders([]);
    setConversationsLoading(false);
  };

  const handleCreateProjectFolder = useCallback(
    async (name: string) => {
      try {
        const created = await apiPost<ProjectFolder>("/chat/project-folders", {
          name,
        });
        await loadConversations();
        setActiveProjectFolderId(created.id);
        setCurrentConvId(null);
        setMessages([]);
        setPage("chat");
        addToast("success", "Projet créé.");
      } catch (e) {
        addToast(
          "error",
          e instanceof Error ? e.message : "Impossible de créer le projet."
        );
        throw e;
      }
    },
    [loadConversations, addToast]
  );

  const handleRenameProjectFolder = useCallback(
    async (id: string, name: string) => {
      try {
        await apiPatch<ProjectFolder>(`/chat/project-folders/${id}`, { name });
        await loadConversations();
        addToast("success", "Projet renommé.");
      } catch (e) {
        addToast(
          "error",
          e instanceof Error ? e.message : "Impossible de renommer le projet."
        );
        throw e;
      }
    },
    [loadConversations, addToast]
  );

  const handleDeleteProjectFolder = useCallback(
    async (id: string) => {
      try {
        await apiDelete(`/chat/project-folders/${id}`);
        await loadConversations();
        if (id === activeProjectFolderId) {
          setActiveProjectFolderId(null);
          setCurrentConvId(null);
          setMessages([]);
        }
        addToast("success", "Projet supprimé.");
      } catch (e) {
        addToast(
          "error",
          e instanceof Error ? e.message : "Impossible de supprimer le projet."
        );
        throw e;
      }
    },
    [loadConversations, addToast, activeProjectFolderId]
  );

  const handleMoveConversationToFolder = useCallback(
    async (conversationId: string, folderId: string | null): Promise<boolean> => {
      const conv = conversations.find((c) => c.id === conversationId);
      const currentFolder = conv?.folder_id ?? null;
      const targetFolder = folderId ?? null;
      if (currentFolder === targetFolder) return false;

      try {
        await apiPatch<Conversation>(
          `/chat/conversations/${conversationId}/folder`,
          { folder_id: folderId }
        );
        await loadConversations();
        addToast(
          "success",
          folderId
            ? "Conversation déplacée dans le projet."
            : "Conversation rangée dans Récents."
        );
        return true;
      } catch (e) {
        addToast(
          "error",
          e instanceof Error ? e.message : "Impossible de déplacer la conversation."
        );
        throw e;
      }
    },
    [conversations, loadConversations, addToast]
  );

  const handleNewChat = () => {
    lastSyncedConvParamRef.current = null;
    replaceConversationInUrl(null);
    setActiveProjectFolderId(null);
    setCurrentConvId(null);
    setMessages([]);
    setActiveConversationMode(null);
    setIsAtelierConversation(false);
    setPage("chat");
  };

  const handleSelectProjectFolder = useCallback(
    (folderId: string) => {
      lastSyncedConvParamRef.current = null;
      replaceConversationInUrl(null);
      setActiveProjectFolderId(folderId);
      setCurrentConvId(null);
      setMessages([]);
      setActiveConversationMode(null);
      setIsAtelierConversation(false);
      setPage("chat");
    },
    [replaceConversationInUrl]
  );

  const handleOpenAtelier = () => {
    if (!user) {
      if (sessionHint) return;
      openAuth("register");
      return;
    }
    lastSyncedConvParamRef.current = null;
    replaceConversationInUrl(null);
    setActiveProjectFolderId(null);
    setCurrentConvId(null);
    setMessages([]);
    setActiveConversationMode(null);
    setIsAtelierConversation(false);
    setPage("atelier");
  };

  /** Retour Atelier → chat sans vider le projet ouvert (ex. vue PROJETS). */
  const handleAtelierBack = useCallback(() => {
    lastSyncedConvParamRef.current = null;
    replaceConversationInUrl(null);
    setPage("chat");
    setMessages([]);
    setCurrentConvId(null);
    setIsAtelierConversation(false);
  }, [replaceConversationInUrl]);

  const handleSelectConversation = useCallback(
    async (id: string) => {
      setPage("chat");
      try {
        const conv = await apiGet<Conversation>(`/chat/conversations/${id}`);
        applyConversationState(conv);
        lastSyncedConvParamRef.current = conv.id;
        replaceConversationInUrl(conv.id);
      } catch {
        addToast("error", "Impossible de charger la conversation.");
      }
    },
    [addToast, applyConversationState, replaceConversationInUrl]
  );

  useEffect(() => {
    const param = searchParams.get(CONV_SEARCH_PARAM)?.trim() || null;
    if (!param) {
      lastSyncedConvParamRef.current = null;
      return;
    }
    if (!isLoggedIn()) return;
    if (!user && !sessionHint) return;
    if (lastSyncedConvParamRef.current === param) return;

    let cancelled = false;
    (async () => {
      try {
        const conv = await apiGet<Conversation>(`/chat/conversations/${param}`);
        if (cancelled) return;
        applyConversationState(conv);
        lastSyncedConvParamRef.current = conv.id;
        setPage("chat");
      } catch {
        if (!cancelled) {
          addToast("error", "Impossible de charger la conversation.");
          lastSyncedConvParamRef.current = null;
          replaceConversationInUrl(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    searchParams,
    user,
    sessionHint,
    addToast,
    applyConversationState,
    replaceConversationInUrl,
  ]);

  const simulatePipelineProgress = () => {
    setPipelineStep("filtering");
    const timers: ReturnType<typeof setTimeout>[] = [];
    timers.push(setTimeout(() => setPipelineStep("analyzing"), 1200));
    timers.push(setTimeout(() => setPipelineStep("searching"), 3000));
    return () => timers.forEach(clearTimeout);
  };

  const handleStopSend = useCallback(() => {
    sendAbortRef.current?.abort();
  }, []);

  const handleSend = useCallback(
    async (text: string) => {
      if (!user) {
        if (sessionHint) return;
        openAuth("register");
        return;
      }

      const optimisticMsg: Message = {
        id: "temp-" + Date.now(),
        role: "user",
        content: text,
        message_type: "text",
        metadata_json: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimisticMsg]);
      setSending(true);
      const cleanupProgress = simulatePipelineProgress();

      sendAbortRef.current?.abort();
      const controller = new AbortController();
      sendAbortRef.current = controller;

      const atelierFollowUp =
        isAtelierConversation &&
        messages.some((m) => m.message_type === "business_dossier");
      const modeForRequest: Mode = atelierFollowUp
        ? "prospection"
        : (activeConversationMode ?? selectedMode);

      try {
        const res = await apiPost<ChatResponse>(
          "/chat/send",
          {
            conversation_id: currentConvId,
            message: text,
            mode: modeForRequest,
            ...(!currentConvId && activeProjectFolderId
              ? { folder_id: activeProjectFolderId }
              : {}),
          },
          { signal: controller.signal }
        );

        if (controller.signal.aborted) return;

        if (!currentConvId) {
          setCurrentConvId(res.conversation_id);
          setActiveConversationMode(modeForRequest);
          setIsAtelierConversation(false);
          lastSyncedConvParamRef.current = res.conversation_id;
          replaceConversationInUrl(res.conversation_id);
        }

        setMessages((prev) => {
          const filtered = prev.filter((m) => m.id !== optimisticMsg.id);
          return [
            ...filtered,
            { ...optimisticMsg, id: "user-" + Date.now() },
            ...res.messages,
          ];
        });

        const updatedUser = await apiGet<User>(
          "/auth/me?token=" + localStorage.getItem("monv_token")
        );
        setUser(updatedUser);

        await loadConversations();
      } catch (err: any) {
        if (isAbortError(err)) {
          setMessages((prev) => prev.filter((m) => m.id !== optimisticMsg.id));
          addToast("info", "Requête annulée.");
          return;
        }
        const errorMsg: Message = {
          id: "err-" + Date.now(),
          role: "assistant",
          content: `Une erreur est survenue. Veuillez réessayer.`,
          message_type: "error",
          metadata_json: null,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
        addToast("error", err.message || "Erreur de communication avec le serveur.");
      } finally {
        if (sendAbortRef.current === controller) {
          sendAbortRef.current = null;
        }
        cleanupProgress();
        setSending(false);
      }
    },
    [
      user,
      sessionHint,
      currentConvId,
      loadConversations,
      addToast,
      openAuth,
      selectedMode,
      activeConversationMode,
      activeProjectFolderId,
      replaceConversationInUrl,
      isAtelierConversation,
      messages,
    ]
  );

  const handleQcmSubmit = useCallback(
    async (text: string) => {
      if (!user) return;

      // ── Cas Atelier : le QCM → /agent/send avec { conversation_id, answers }
      //    Produit un dossier (business_dossier) plutôt qu'un results classique.
      if (isAtelierConversation && currentConvId) {
        setSending(true);
        const cleanupProgress = simulatePipelineProgress();

        sendAbortRef.current?.abort();
        const controller = new AbortController();
        sendAbortRef.current = controller;

        try {
          const res = await apiPost<AgentSendResponse>(
            "/agent/send",
            {
              conversation_id: currentConvId,
              answers: text,
            },
            { signal: controller.signal }
          );
          if (controller.signal.aborted) return;

          setMessages((prev) => [...prev, ...res.messages]);
          if (res.folder_id) {
            setActiveProjectFolderId(res.folder_id);
          }

          const updatedUser = await apiGet<User>(
            "/auth/me?token=" + localStorage.getItem("monv_token")
          );
          setUser(updatedUser);
          await loadConversations();
        } catch (err: any) {
          if (isAbortError(err)) {
            addToast("info", "Requête annulée.");
            return;
          }
          const errorMsg: Message = {
            id: "err-" + Date.now(),
            role: "assistant",
            content:
              "L'Atelier n'a pas pu générer le dossier. Réessaie dans quelques instants.",
            message_type: "error",
            metadata_json: null,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, errorMsg]);
          addToast(
            "error",
            err.message || "Erreur de communication avec l'Atelier."
          );
        } finally {
          if (sendAbortRef.current === controller) {
            sendAbortRef.current = null;
          }
          cleanupProgress();
          setSending(false);
        }
        return;
      }

      // ── Cas modes classiques : /chat/send ─────────────────────────────────
      setSending(true);
      const cleanupProgress = simulatePipelineProgress();

      sendAbortRef.current?.abort();
      const controller = new AbortController();
      sendAbortRef.current = controller;

      const modeForRequest: Mode = activeConversationMode ?? selectedMode;

      try {
        const res = await apiPost<ChatResponse>(
          "/chat/send",
          {
            conversation_id: currentConvId,
            message: text,
            mode: modeForRequest,
            ...(!currentConvId && activeProjectFolderId
              ? { folder_id: activeProjectFolderId }
              : {}),
          },
          { signal: controller.signal }
        );

        if (controller.signal.aborted) return;

        if (!currentConvId) {
          setCurrentConvId(res.conversation_id);
          setActiveConversationMode(modeForRequest);
          setIsAtelierConversation(false);
        }

        setMessages((prev) => [...prev, ...res.messages]);

        const updatedUser = await apiGet<User>(
          "/auth/me?token=" + localStorage.getItem("monv_token")
        );
        setUser(updatedUser);
        await loadConversations();
      } catch (err: any) {
        if (isAbortError(err)) {
          addToast("info", "Requête annulée.");
          return;
        }
        const errorMsg: Message = {
          id: "err-" + Date.now(),
          role: "assistant",
          content: `Une erreur est survenue. Veuillez réessayer.`,
          message_type: "error",
          metadata_json: null,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
        addToast("error", err.message || "Erreur de communication avec le serveur.");
      } finally {
        if (sendAbortRef.current === controller) {
          sendAbortRef.current = null;
        }
        cleanupProgress();
        setSending(false);
      }
    },
    [
      user,
      currentConvId,
      loadConversations,
      addToast,
      selectedMode,
      activeConversationMode,
      isAtelierConversation,
      activeProjectFolderId,
    ]
  );

  const handleAgentStart = useCallback(
    async (pitch: string, attachFolderId: string | null = null) => {
      if (!user) {
        if (sessionHint) return;
        openAuth("register");
        return;
      }
      setSending(true);
      const cleanupProgress = simulatePipelineProgress();

      sendAbortRef.current?.abort();
      const controller = new AbortController();
      sendAbortRef.current = controller;

      const optimisticMsg: Message = {
        id: "temp-" + Date.now(),
        role: "user",
        content: pitch,
        message_type: "text",
        metadata_json: JSON.stringify({ mode: ATELIER_MODE_LABEL }),
        created_at: new Date().toISOString(),
      };

      // Bascule immédiate vers la vue chat avec le pitch affiché, sans
      // attendre le retour serveur pour une perception de réactivité.
      setMessages([optimisticMsg]);
      setIsAtelierConversation(true);
      setActiveConversationMode(null);
      setCurrentConvId(null);
      setPage("chat");

      try {
        const res = await apiPost<AgentSendResponse>(
          "/agent/send",
          {
            pitch,
            ...(attachFolderId ? { folder_id: attachFolderId } : {}),
          },
          { signal: controller.signal }
        );
        if (controller.signal.aborted) return;

        setCurrentConvId(res.conversation_id);
        if (res.folder_id) {
          setActiveProjectFolderId(res.folder_id);
        }
        lastSyncedConvParamRef.current = res.conversation_id;
        replaceConversationInUrl(res.conversation_id);
        setMessages((prev) => {
          const filtered = prev.filter((m) => m.id !== optimisticMsg.id);
          return [
            ...filtered,
            { ...optimisticMsg, id: "user-" + Date.now() },
            ...res.messages,
          ];
        });
        await loadConversations();
      } catch (err: any) {
        if (isAbortError(err)) {
          addToast("info", "Requête annulée.");
          setMessages([]);
          setIsAtelierConversation(false);
          setPage("atelier");
          lastSyncedConvParamRef.current = null;
          replaceConversationInUrl(null);
          return;
        }
        const errorMsg: Message = {
          id: "err-" + Date.now(),
          role: "assistant",
          content:
            "L'Atelier n'a pas pu démarrer. Réessaie dans quelques instants.",
          message_type: "error",
          metadata_json: null,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
        addToast(
          "error",
          err.message || "Erreur de communication avec l'Atelier."
        );
      } finally {
        if (sendAbortRef.current === controller) {
          sendAbortRef.current = null;
        }
        cleanupProgress();
        setSending(false);
      }
    },
    [user, sessionHint, openAuth, addToast, loadConversations, replaceConversationInUrl]
  );

  const handleExport = async (searchId: string, format: "xlsx" | "csv") => {
    setExporting(true);
    try {
      const res = await apiPost<ExportResponse>("/search/export", {
        search_id: searchId,
        format,
      });
      window.open(res.download_url, "_blank");
      const updatedUser = await apiGet<User>(
        "/auth/me?token=" + localStorage.getItem("monv_token")
      );
      setUser(updatedUser);
      addToast(
        "success",
        res.credits_used > 0
          ? `Export ${format.toUpperCase()} téléchargé\u202f! ${res.credits_used} crédit(s) utilisé(s).`
          : `Export ${format.toUpperCase()} téléchargé\u202f!`
      );
    } catch (err: any) {
      addToast("error", err.message || "Erreur lors de l'export.");
    }
    setExporting(false);
  };

  const handleExportAllAtelier = async (
    items: { search_id: string; credits_required: number }[],
    format: "xlsx" | "csv"
  ) => {
    if (items.length === 0) return;
    setExporting(true);
    try {
      let totalCredits = 0;
      for (const item of items) {
        const res = await apiPost<ExportResponse>("/search/export", {
          search_id: item.search_id,
          format,
        });
        totalCredits += res.credits_used;
        window.open(res.download_url, "_blank");
      }
      const updatedUser = await apiGet<User>(
        "/auth/me?token=" + localStorage.getItem("monv_token")
      );
      setUser(updatedUser);
      addToast(
        "success",
        totalCredits > 0
          ? `${items.length} export(s) ${format.toUpperCase()} lancé(s). ${totalCredits} crédit(s) utilisé(s) au total.`
          : `${items.length} export(s) ${format.toUpperCase()} lancé(s).`
      );
    } catch (err: any) {
      addToast("error", err.message || "Erreur lors d'un export du dossier.");
    }
    setExporting(false);
  };

  const handleTemplateSelect = (query: string) => {
    if (!user) {
      if (sessionHint) return;
      openAuth("register");
      return;
    }
    handleSend(query);
  };

  const showAuthenticatedChrome = Boolean(user || sessionHint);

  const chatLandingHeadline = (() => {
    if (!user) return "MONV";
    const first = displayFirstName(user.name);
    return first ? `Bonjour ${first}` : "MONV";
  })();

  const chatLandingSubline = user
    ? "Commençons à travailler."
    : null;

  const sidebarProps = {
    user,
    conversations,
    projectFolders,
    conversationsLoading,
    currentConvId,
    activeProjectFolderId,
    onNewChat: handleNewChat,
    onSelectConversation: handleSelectConversation,
    onSelectProjectFolder: handleSelectProjectFolder,
    onCreateProjectFolder: handleCreateProjectFolder,
    onRenameProjectFolder: handleRenameProjectFolder,
    onDeleteProjectFolder: handleDeleteProjectFolder,
    onMoveConversationToFolder: handleMoveConversationToFolder,
    onNavigate: (p: Page) => {
      if (p === "atelier") {
        handleOpenAtelier();
        return;
      }
      if (!user && p !== "chat") return;
      if (p !== "chat") {
        lastSyncedConvParamRef.current = null;
        replaceConversationInUrl(null);
        setActiveProjectFolderId(null);
      }
      setPage(p);
    },
    onLogout: handleLogout,
    collapsed: sidebarCollapsed,
    onToggle: () => setSidebarCollapsed(!sidebarCollapsed),
    mobileOpen: sidebarMobileOpen,
    onMobileClose: () => setSidebarMobileOpen(false),
  };

  if (page === "dashboard" && user) {
    return (
      <div className="flex h-screen bg-surface-0">
        <Sidebar {...sidebarProps} />
        <div className="flex-1 flex flex-col overflow-hidden">
          <MobileHeader
            user={user}
            onMenuOpen={() => setSidebarMobileOpen(true)}
            onNavigateCredits={() => setPage("credits")}
            onOpenAtelier={handleOpenAtelier}
          />
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            <Dashboard onBack={handleNewChat} />
          </div>
        </div>
        <ToastContainer toasts={toasts} onRemove={removeToast} />
      </div>
    );
  }

  if (page === "atelier" && (user || sessionHint)) {
    return (
      <div className="flex h-screen bg-surface-0">
        {showAuthenticatedChrome && <Sidebar {...sidebarProps} />}
        <div className="flex-1 flex flex-col overflow-hidden">
          {showAuthenticatedChrome && (
            <MobileHeader
              user={user}
              onMenuOpen={() => setSidebarMobileOpen(true)}
              onNavigateCredits={() => setPage("credits")}
              onOpenAtelier={handleOpenAtelier}
            />
          )}
          <AgentWelcome
            onBack={handleAtelierBack}
            onSubmit={handleAgentStart}
            projectFolders={projectFolders}
            disabled={!user || sending}
            loading={sending}
          />
        </div>
        <ToastContainer toasts={toasts} onRemove={removeToast} />
      </div>
    );
  }

  if (page === "credits" && user) {
    return (
      <div className="flex h-screen bg-surface-0">
        <Sidebar {...sidebarProps} />
        <div className="flex-1 flex flex-col overflow-hidden">
          <MobileHeader
            user={user}
            onMenuOpen={() => setSidebarMobileOpen(true)}
            onNavigateCredits={() => setPage("credits")}
            onOpenAtelier={handleOpenAtelier}
          />
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            <CreditsPage
              user={user}
              onCreditsUpdated={(n) =>
                setUser(user ? { ...user, credits: n, credits_unlimited: user.credits_unlimited } : null)
              }
              onBack={handleNewChat}
            />
          </div>
        </div>
        <ToastContainer toasts={toasts} onRemove={removeToast} />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-surface-0">
      {showAuthenticatedChrome && <Sidebar {...sidebarProps} />}

      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {showAuthenticatedChrome && (
          <MobileHeader
            user={user}
            onMenuOpen={() => setSidebarMobileOpen(true)}
            onNavigateCredits={() => setPage("credits")}
            onOpenAtelier={handleOpenAtelier}
          />
        )}
        {showProjectHub && activeProjectFolder ? (
          <ProjectHub
            projectFolderId={activeProjectFolder.id}
            projectName={activeProjectFolder.name}
            conversationsInProject={conversations.filter(
              (c) => c.folder_id === activeProjectFolder.id
            )}
            conversationsLoading={conversationsLoading}
            selectedMode={selectedMode}
            onModeChange={setSelectedMode}
            templates={templates}
            onTemplateSelect={handleTemplateSelect}
            sending={sending}
            onSend={handleSend}
            onStop={handleStopSend}
            onSelectConversation={handleSelectConversation}
            onLeaveProject={handleNewChat}
            onOpenAtelier={() => setPage("atelier")}
            onMoveConversationToFolder={handleMoveConversationToFolder}
          />
        ) : messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center px-4 sm:px-6 overflow-y-auto">
            <div className="my-auto w-full flex flex-col items-center py-6 sm:py-10 max-w-3xl mx-auto">
              <div
                className={`w-full mb-6 sm:mb-8 ${
                  user || sessionHint ? "text-center" : "text-center max-w-2xl mx-auto"
                }`}
              >
                <h1
                  className={`tracking-tight text-white text-balance ${
                    user
                      ? "text-2xl sm:text-3xl font-semibold leading-snug"
                      : "text-3xl sm:text-5xl font-extrabold leading-tight"
                  }`}
                >
                  {chatLandingHeadline}
                </h1>
                {chatLandingSubline && (
                  <p className="mt-2 text-sm text-gray-500 max-w-lg mx-auto leading-relaxed">
                    {chatLandingSubline}
                  </p>
                )}

                {!user && !sessionHint && (
                  <>
                    <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3 px-2 sm:px-0">
                      <button
                        type="button"
                        onClick={() => openAuth("register")}
                        className="inline-flex items-center justify-center gap-2 bg-white text-gray-950 px-6 py-3 rounded-lg font-semibold hover:bg-gray-200 active:bg-gray-300 transition-colors text-sm w-full sm:w-auto min-h-[44px]"
                      >
                        S&apos;inscrire — 5 crédits offerts
                        <ArrowRight size={15} />
                      </button>
                      <button
                        type="button"
                        onClick={() => openAuth("login")}
                        className="inline-flex items-center justify-center px-6 py-3 rounded-lg font-semibold text-sm text-white border border-gray-700 hover:bg-white/[0.06] active:bg-white/[0.1] hover:border-gray-600 transition-colors w-full sm:w-auto min-h-[44px]"
                      >
                        Se connecter
                      </button>
                    </div>
                    <p className="mt-5 text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
                      Inscris-toi pour lancer des recherches par mode (prospection,
                      sous-traitants, etc.). Tu pourras aussi ouvrir l&apos;agent{" "}
                      <span className="text-teal-300/95">Atelier</span> pour un
                      dossier projet guidé (QCM puis tableaux d&apos;entreprises).
                    </p>
                  </>
                )}
              </div>

              {(user || sessionHint) && (
                <>
                  <section
                    className="w-full rounded-xl border border-white/[0.08] bg-surface-1/60 p-4 sm:p-6 flex flex-col min-w-0 mb-5"
                    aria-labelledby="recherche-mode-heading"
                  >
                    <div className="mb-4">
                    </div>
                    <ModeSelector
                      value={selectedMode}
                      onChange={setSelectedMode}
                      disabled={sending || !user}
                    />
                    <div className="mt-5 pt-5 border-t border-white/[0.07] flex flex-col min-h-0">
                      <ChatInput
                        onSend={handleSend}
                        disabled={sending || !user}
                        loading={sending}
                        onStop={handleStopSend}
                        placeholder={MODE_META[selectedMode].placeholder}
                      />
                    </div>
                    <div className="mt-6 pt-6 border-t border-white/[0.07]">
                      <p className="text-xs font-medium text-gray-500 mb-3">
                        Exemples · {MODE_META[selectedMode].label}
                      </p>
                      {templates.length > 0 ? (
                        <TemplateCards
                          nested
                          templates={templates}
                          onSelect={handleTemplateSelect}
                        />
                      ) : (
                        <p className="text-center text-xs text-gray-600 py-5 border border-dashed border-white/[0.06] rounded-lg">
                          Aucun exemple pour ce mode — décris ta recherche
                          directement.
                        </p>
                      )}
                    </div>
                  </section>

                  <div className="w-full mb-10">
                    <button
                      type="button"
                      onClick={handleOpenAtelier}
                      disabled={sending || !user}
                      className="group relative w-full overflow-hidden rounded-xl border border-white/[0.08] bg-surface-1 text-left hover:border-white/[0.14] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-teal-500/30 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-0"
                    >
                      <div
                        className="pointer-events-none absolute inset-y-0 left-0 w-[3px] bg-teal-700/90"
                        aria-hidden
                      />
                      <div className="relative flex flex-col sm:flex-row sm:items-center gap-4 pl-5 pr-4 py-4 sm:py-4">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-teal-950/45 text-teal-200/95">
                          <Compass size={20} strokeWidth={2} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-gray-500">Atelier</p>
                          <p className="text-base sm:text-[17px] font-medium text-white mt-0.5 leading-snug">
                            Créons ton entreprise ensemble.
                          </p>
                        </div>
                        <span className="inline-flex shrink-0 items-center justify-center gap-1.5 self-stretch sm:self-center rounded-lg border border-white/[0.1] bg-white/[0.05] px-3.5 py-2 text-sm font-medium text-white group-hover:bg-white/[0.08] sm:min-h-0 min-h-[44px]">
                          Ouvrir
                          <ArrowRight size={15} aria-hidden />
                        </span>
                      </div>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-6">
              <div className="max-w-3xl mx-auto space-y-6">
                {messages.map((m) => (
                  <ChatMessage
                    key={m.id}
                    message={m}
                    userCredits={user?.credits ?? 0}
                    creditsUnlimited={user?.credits_unlimited ?? false}
                    onExport={handleExport}
                    onExportAllAtelier={handleExportAllAtelier}
                    exporting={exporting}
                    onQcmSubmit={handleQcmSubmit}
                    conversationMode={activeConversationMode}
                    isAtelierConversation={isAtelierConversation}
                    conversationId={currentConvId}
                    onAtelierDossierReplaced={handleAtelierDossierReplaced}
                    onAtelierNotify={handleAtelierNotify}
                    onAtelierCreditsRemaining={handleAtelierCreditsRemaining}
                  />
                ))}

                {sending && <PipelineProgress currentStep={pipelineStep} />}

                <div ref={messagesEndRef} />
              </div>
            </div>

            {isAtelierConversation ? (
              messages.some((m) => m.message_type === "business_dossier") ? (
                <div className="border-t border-gray-800/60 px-4 py-3 bg-surface-0">
                  <div className="max-w-3xl mx-auto space-y-2">
                    <ChatInput
                      onSend={handleSend}
                      disabled={sending}
                      loading={sending}
                      onStop={handleStopSend}
                      placeholder="Poursuivre : ex. « Trouve des ESN à Toulouse » ou « concurrents secteur X »…"
                    />
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                      <p className="text-[11px] text-gray-500 text-center sm:text-left">
                        Session <span className="text-teal-300">Atelier</span> — recherche
                        suivante en mode prospection (historique conservé).
                      </p>
                      <button
                        type="button"
                        onClick={handleNewChat}
                        className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-white/[0.08] bg-surface-1 px-3 py-1.5 text-xs text-gray-300 hover:text-white hover:border-white/[0.18] transition-colors shrink-0"
                      >
                        Nouveau chat
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="border-t border-gray-800/60 px-4 py-3 bg-surface-0">
                  <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
                    <p className="text-[11px] text-gray-500">
                      Session <span className="text-teal-300">Atelier</span> — réponds au
                      questionnaire puis consulte ton dossier.{" "}
                      <span className="text-gray-600">
                        Nouveau chat pour quitter sans dossier.
                      </span>
                    </p>
                    <button
                      type="button"
                      onClick={handleNewChat}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-surface-1 px-3 py-1.5 text-xs text-gray-300 hover:text-white hover:border-white/[0.18] transition-colors"
                    >
                      Nouveau chat
                    </button>
                  </div>
                </div>
              )
            ) : (
              <div className="border-t border-gray-800/60 px-4 py-3 bg-surface-0">
                <div className="max-w-3xl mx-auto">
                  <ChatInput
                    onSend={handleSend}
                    disabled={sending}
                    loading={sending}
                    onStop={handleStopSend}
                    placeholder={
                      MODE_META[activeConversationMode ?? selectedMode].placeholder
                    }
                  />
                  <p className="text-center text-[11px] text-gray-600 mt-2">
                    {activeConversationMode && activeConversationMode !== "prospection" ? (
                      <>
                        Mode <span className="text-gray-400">{MODE_META[activeConversationMode].label}</span>
                        {" "}— données publiques INSEE & RCS, résultats indicatifs
                      </>
                    ) : (
                      "Données publiques INSEE & RCS — résultats indicatifs"
                    )}
                  </p>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {showAuth && (
        <AuthModal
          initialMode={authInitialMode}
          onAuth={handleAuth}
          onClose={() => setShowAuth(false)}
        />
      )}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-surface-0 text-gray-500 text-sm">
          Chargement…
        </div>
      }
    >
      <HomeInner />
    </Suspense>
  );
}
