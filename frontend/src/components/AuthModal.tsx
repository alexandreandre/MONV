"use client";

import { useState } from "react";
import { apiPost, setToken, type AuthResponse } from "@/lib/api";
import { X } from "lucide-react";

interface Props {
  onAuth: (user: AuthResponse["user"]) => void;
  onClose: () => void;
  /** Ouverture depuis la landing : inscription ou connexion */
  initialMode?: "login" | "register";
}

export default function AuthModal({
  onAuth,
  onClose,
  initialMode = "register",
}: Props) {
  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = mode === "register" ? "/auth/register" : "/auth/login";
      const body =
        mode === "register"
          ? { email, name, password }
          : { email, password };
      const res = await apiPost<AuthResponse>(endpoint, body);
      setToken(res.access_token);
      onAuth(res.user);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "w-full rounded-lg bg-surface-2 border border-white/[0.08] px-3.5 py-2.5 text-sm text-white placeholder-gray-600 focus:border-white/[0.2] focus:ring-1 focus:ring-white/[0.1] outline-none transition-colors";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-sm rounded-2xl bg-surface-1 border border-white/[0.08] p-7 shadow-2xl animate-fade-in">
        <button
          onClick={onClose}
          className="absolute right-3.5 top-3.5 p-1 rounded-md text-gray-600 hover:text-gray-300 hover:bg-white/[0.06] transition-colors"
        >
          <X size={18} />
        </button>

        <div className="mb-6">
          <h2 className="text-xl font-bold text-white">
            {mode === "register" ? "Créer un compte" : "Se connecter"}
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            {mode === "register"
              ? "Inscription rapide, sans engagement"
              : "Content de vous revoir"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {mode === "register" && (
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Nom
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputClass}
                placeholder="Votre nom"
                required
              />
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="votre@email.com"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">
              Mot de passe
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              placeholder="••••••••"
              required
              minLength={4}
            />
          </div>

          {error && (
            <p className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-white text-gray-950 px-4 py-2.5 text-sm font-semibold hover:bg-gray-200 disabled:opacity-50 transition-colors"
          >
            {loading
              ? "Chargement..."
              : mode === "register"
                ? "S'inscrire"
                : "Se connecter"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-gray-500">
          {mode === "register" ? "Déjà un compte ?" : "Pas encore de compte ?"}
          <button
            onClick={() => {
              setMode(mode === "register" ? "login" : "register");
              setError("");
            }}
            className="ml-1 text-white hover:underline underline-offset-2 transition-colors"
          >
            {mode === "register" ? "Se connecter" : "S'inscrire"}
          </button>
        </p>
      </div>
    </div>
  );
}
