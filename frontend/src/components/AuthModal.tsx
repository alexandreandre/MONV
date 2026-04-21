"use client";

import { useState } from "react";
import { apiPost, setToken, type AuthResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[95vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl">
            {mode === "register" ? "Créer un compte" : "Se connecter"}
          </DialogTitle>
          <DialogDescription>
            {mode === "register"
              ? "Inscription rapide, sans engagement"
              : "Content de vous revoir"}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {mode === "register" && (
            <div className="space-y-1.5">
              <Label htmlFor="auth-name" className="text-xs">
                Nom
              </Label>
              <Input
                id="auth-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Votre nom"
                required
              />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="auth-email" className="text-xs">
              Email
            </Label>
            <Input
              id="auth-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="votre@email.com"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="auth-password" className="text-xs">
              Mot de passe
            </Label>
            <Input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={4}
            />
          </div>

          {error && (
            <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <Button type="submit" disabled={loading} className="h-11 w-full">
            {loading
              ? "Chargement..."
              : mode === "register"
                ? "S'inscrire"
                : "Se connecter"}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          {mode === "register" ? "Déjà un compte ?" : "Pas encore de compte ?"}
          <Button
            type="button"
            variant="link"
            className="h-auto px-1 font-normal"
            onClick={() => {
              setMode(mode === "register" ? "login" : "register");
              setError("");
            }}
          >
            {mode === "register" ? "Se connecter" : "S'inscrire"}
          </Button>
        </p>
      </DialogContent>
    </Dialog>
  );
}
