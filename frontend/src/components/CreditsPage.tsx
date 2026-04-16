"use client";

import { useState, useEffect } from "react";
import { Zap, ArrowLeft } from "lucide-react";
import { apiGet, apiPost, type CreditPack, type User } from "@/lib/api";

interface Props {
  user: User;
  onCreditsUpdated: (newBalance: number) => void;
  onBack: () => void;
}

export default function CreditsPage({ user, onCreditsUpdated, onBack }: Props) {
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [buying, setBuying] = useState<string | null>(null);

  useEffect(() => {
    apiGet<CreditPack[]>("/credits/packs").then(setPacks).catch(() => {});
  }, []);

  const handleBuy = async (packId: string) => {
    setBuying(packId);
    try {
      const res = await apiPost<{ new_balance: number }>(`/credits/add/${packId}`, {});
      onCreditsUpdated(res.new_balance);
    } catch {
      /* parent gère les toasts */
    }
    setBuying(null);
  };

  const CREDIT_USAGE = [
    { action: "Recherche simple (SIRENE)", credits: 1 },
    { action: "Recherche enrichie (SIRENE + Pappers)", credits: 3 },
    { action: "Recherche + contacts", credits: 5 },
    { action: "Recherche massive (>500 résultats)", credits: 10 },
  ];

  return (
    <div className="max-w-3xl mx-auto py-6 sm:py-10 px-4 sm:px-6">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 active:text-white transition-colors mb-6 min-h-[44px]"
      >
        <ArrowLeft size={14} />
        Retour au chat
      </button>

      <div className="flex items-baseline justify-between mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Crédits</h1>
          <p className="text-gray-500 text-sm mt-1">
            Solde :{" "}
            <span className="text-white font-semibold tabular-nums">
              {user.credits_unlimited ? "Illimité" : user.credits}
            </span>
            {!user.credits_unlimited && (
              <>
                {" "}
                crédit{user.credits > 1 ? "s" : ""}
              </>
            )}
          </p>
        </div>
      </div>

      <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
        Acheter des crédits
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-10">
        {user.credits_unlimited && (
          <p className="col-span-full text-sm text-gray-400 mb-2">
            Avec un compte illimité, les exports ne consomment pas de crédits.
          </p>
        )}
        {packs.map((pack) => {
          const isPopular = pack.id === "pro";
          return (
            <div
              key={pack.id}
              className={`relative rounded-xl border p-5 transition-all ${
                isPopular
                  ? "border-white/[0.15] bg-surface-2"
                  : "border-white/[0.06] bg-surface-1 hover:border-white/[0.12]"
              }`}
            >
              {isPopular && (
                <span className="absolute -top-2.5 left-4 bg-white text-gray-950 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded">
                  Populaire
                </span>
              )}
              <h3 className="text-base font-semibold text-white">{pack.name}</h3>
              <div className="mt-2 flex items-baseline gap-0.5">
                <span className="text-2xl font-bold tabular-nums text-white">
                  {pack.price_euros}
                </span>
                <span className="text-gray-500 text-sm">&thinsp;&euro;</span>
              </div>
              <p className="mt-1 text-xs text-gray-500">
                {pack.credits} crédits &middot; {pack.price_per_credit.toFixed(2)}&thinsp;&euro;/cr.
              </p>
              <button
                onClick={() => handleBuy(pack.id)}
                disabled={buying === pack.id || !!user.credits_unlimited}
                className={`mt-4 w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors min-h-[44px] ${
                  isPopular
                    ? "bg-white text-gray-950 hover:bg-gray-200 active:bg-gray-300"
                    : "bg-white/[0.06] text-gray-300 hover:bg-white/[0.1] active:bg-white/[0.15]"
                } disabled:opacity-50`}
              >
                {buying === pack.id ? "Traitement..." : "Acheter"}
              </button>
            </div>
          );
        })}
      </div>

      <div className="rounded-xl border border-white/[0.06] bg-surface-1 p-5">
        <h3 className="text-sm font-medium text-gray-400 mb-4 flex items-center gap-2">
          <Zap size={14} />
          Coût par recherche
        </h3>
        <div className="space-y-0">
          {CREDIT_USAGE.map((item, i) => (
            <div
              key={i}
              className="flex items-center justify-between py-2.5 border-b border-white/[0.04] last:border-0"
            >
              <span className="text-sm text-gray-400">{item.action}</span>
              <span className="text-sm font-medium tabular-nums text-white">
                {item.credits}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
