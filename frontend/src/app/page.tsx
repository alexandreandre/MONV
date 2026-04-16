"use client";

import {
  useState,
  useEffect,
  useLayoutEffect,
  useRef,
  useCallback,
} from "react";
import {
  apiPost,
  apiGet,
  clearToken,
  isLoggedIn,
  type User,
  type Message,
  type Conversation,
  type ChatResponse,
  type ExportResponse,
  type QcmSubmitPayload,
} from "@/lib/api";
import { LANDING_TEMPLATES } from "@/lib/landingTemplates";
import AuthModal from "@/components/AuthModal";
import Sidebar from "@/components/Sidebar";
import ChatInput from "@/components/ChatInput";
import ChatMessage from "@/components/ChatMessage";
import TemplateCards from "@/components/TemplateCards";
import Dashboard from "@/components/Dashboard";
import CreditsPage from "@/components/CreditsPage";
import ToastContainer, { type ToastData } from "@/components/Toast";
import MobileHeader from "@/components/MobileHeader";
import PipelineProgress, { type PipelineStep } from "@/components/PipelineProgress";
import { ArrowRight } from "lucide-react";

type Page = "chat" | "dashboard" | "credits";

/** Premier mot du nom affiché comme prénom (donnée actuelle côté API : un seul champ `name`). */
function displayFirstName(fullName: string): string | null {
  const w = fullName.trim().split(/\s+/)[0];
  if (!w) return null;
  return (
    w.charAt(0).toLocaleUpperCase("fr-FR") +
    w.slice(1).toLocaleLowerCase("fr-FR")
  );
}

export default function Home() {
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
  const [page, setPage] = useState<Page>("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [currentConvId, setCurrentConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const templates = LANDING_TEMPLATES;

  const [sending, setSending] = useState(false);
  const [pipelineStep, setPipelineStep] = useState<PipelineStep>("filtering");
  const [exporting, setExporting] = useState(false);
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const addToast = useCallback(
    (type: ToastData["type"], message: string, duration?: number) => {
      const id = "toast-" + Date.now() + "-" + Math.random();
      setToasts((prev) => [...prev, { id, type, message, duration }]);
    },
    []
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const loadConversations = useCallback(async () => {
    setConversationsLoading(true);
    try {
      const convs = await apiGet<Conversation[]>("/chat/conversations");
      setConversations(convs);
    } catch {
      /* ignore */
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
        const [meRes, convRes] = await Promise.allSettled([
          apiGet<User>("/auth/me?token=" + token),
          apiGet<Conversation[]>("/chat/conversations"),
        ]);
        if (cancelled) return;
        if (meRes.status === "rejected") {
          clearToken();
          setUser(null);
          setSessionHint(false);
          setConversations([]);
          return;
        }
        setUser(meRes.value);
        if (convRes.status === "fulfilled") {
          setConversations(convRes.value);
        } else {
          setConversations([]);
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
    setConversations([]);
    setConversationsLoading(false);
  };

  const handleNewChat = () => {
    setCurrentConvId(null);
    setMessages([]);
    setPage("chat");
  };

  const handleSelectConversation = async (id: string) => {
    setCurrentConvId(id);
    setPage("chat");
    try {
      const conv = await apiGet<Conversation>(
        `/chat/conversations/${id}`
      );
      setMessages(conv.messages);
    } catch {
      addToast("error", "Impossible de charger la conversation.");
    }
  };

  const simulatePipelineProgress = () => {
    setPipelineStep("filtering");
    const timers: ReturnType<typeof setTimeout>[] = [];
    timers.push(setTimeout(() => setPipelineStep("analyzing"), 1200));
    timers.push(setTimeout(() => setPipelineStep("searching"), 3000));
    return () => timers.forEach(clearTimeout);
  };

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

      try {
        const res = await apiPost<ChatResponse>("/chat/send", {
          conversation_id: currentConvId,
          message: text,
        });

        if (!currentConvId) {
          setCurrentConvId(res.conversation_id);
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
      }

      cleanupProgress();
      setSending(false);
    },
    [user, sessionHint, currentConvId, loadConversations, addToast, openAuth]
  );

  const handleQcmSubmit = useCallback(
    async (payload: QcmSubmitPayload) => {
      if (!user) return;
      setSending(true);
      const cleanupProgress = simulatePipelineProgress();

      const optimisticUserMsg: Message = {
        id: "temp-qcm-" + Date.now(),
        role: "user",
        content: "Choix validés",
        message_type: "text",
        metadata_json: JSON.stringify({ qcm_choice_submit: true }),
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimisticUserMsg]);

      try {
        const res = await apiPost<ChatResponse>("/chat/send", {
          conversation_id: currentConvId,
          message: payload.guardMessage,
          qcm_answers: payload.qcm_answers,
        });

        if (!currentConvId) {
          setCurrentConvId(res.conversation_id);
        }

        setMessages((prev) => {
          const rest = prev.filter((m) => m.id !== optimisticUserMsg.id);
          const userPersisted: Message = {
            ...optimisticUserMsg,
            id: "user-qcm-" + Date.now(),
          };
          return [...rest, userPersisted, ...res.messages];
        });

        const updatedUser = await apiGet<User>(
          "/auth/me?token=" + localStorage.getItem("monv_token")
        );
        setUser(updatedUser);
        await loadConversations();
      } catch (err: any) {
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
      }

      cleanupProgress();
      setSending(false);
    },
    [user, currentConvId, loadConversations, addToast]
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

  const handleTemplateSelect = (query: string) => {
    if (!user) {
      if (sessionHint) return;
      openAuth("register");
      return;
    }
    handleSend(query);
  };

  const CAPABILITIES = [
    "Clients & prospects",
    "Prestataires & fournisseurs",
    "Étude de marché",
    "Données INSEE & RCS",
  ];

  const showAuthenticatedChrome = Boolean(user || sessionHint);

  const chatLandingHeadline = (() => {
    if (!user) return "MONV";
    const first = displayFirstName(user.name);
    return first
      ? `Bonjour ${first}, bienvenue dans MONV`
      : "Bienvenue dans MONV";
  })();

  const sidebarProps = {
    user,
    conversations,
    conversationsLoading,
    currentConvId,
    onNewChat: handleNewChat,
    onSelectConversation: handleSelectConversation,
    onNavigate: (p: Page) => {
      if (!user && p !== "chat") return;
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
          />
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            <Dashboard onBack={handleNewChat} />
          </div>
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
          />
        )}
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center px-4 sm:px-6 overflow-y-auto">
            <div className="my-auto w-full flex flex-col items-center py-6 sm:py-10">
              <div className="max-w-2xl w-full text-center mb-8 sm:mb-10">
                <h1
                  className={`font-extrabold tracking-tight text-white mb-3 text-balance ${
                    user
                      ? "text-2xl sm:text-4xl leading-tight"
                      : "text-3xl sm:text-5xl"
                  }`}
                >
                  {chatLandingHeadline}
                </h1>
                <p className="text-base sm:text-lg text-gray-400 max-w-md mx-auto leading-relaxed">
                  Trouvez n&apos;importe quelle entreprise en France.
                  Décrivez ce que vous cherchez, récupérez votre liste.
                </p>

                <div className="flex flex-wrap items-center justify-center gap-2 mt-4 sm:mt-5">
                  {CAPABILITIES.map((cap) => (
                    <span
                      key={cap}
                      className="text-xs text-gray-500 border border-gray-800 rounded-full px-3 py-1"
                    >
                      {cap}
                    </span>
                  ))}
                </div>

                {!user && !sessionHint && (
                  <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3 px-2 sm:px-0">
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
                )}
              </div>

              {(user || sessionHint) && (
                <div className="w-full max-w-2xl mb-8">
                  <ChatInput
                    onSend={handleSend}
                    disabled={sending || !user}
                  />
                </div>
              )}

              <div className="w-full max-w-3xl">
                <p className="text-xs font-medium text-gray-600 uppercase tracking-wider text-center mb-3">
                  Exemples de recherches
                </p>
                <TemplateCards
                  templates={templates}
                  onSelect={handleTemplateSelect}
                />
              </div>
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
                    exporting={exporting}
                    onQcmSubmit={handleQcmSubmit}
                  />
                ))}

                {sending && <PipelineProgress currentStep={pipelineStep} />}

                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="border-t border-gray-800/60 px-4 py-3 bg-surface-0">
              <div className="max-w-3xl mx-auto">
                <ChatInput onSend={handleSend} disabled={sending} />
                <p className="text-center text-[11px] text-gray-600 mt-2">
                  Données publiques INSEE & RCS — résultats indicatifs
                </p>
              </div>
            </div>
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
