"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Compass } from "lucide-react";
import { AGENT_META } from "@/lib/agents";
import type { ProjectFolder } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
interface Props {
  onBack: () => void;
  /**
   * `attachFolderId` : id d’un projet existant, ou `null` pour en créer un nouveau (défaut).
   */
  onSubmit: (pitch: string, attachFolderId: string | null) => void;
  projectFolders?: ProjectFolder[];
  disabled?: boolean;
  loading?: boolean;
}

const EXAMPLE_PITCHES: { label: string; query: string }[] = [
  {
    label: "Restaurant japonais premium à Lyon",
    query:
      "Je veux ouvrir un restaurant japonais haut de gamme à Lyon, avec service à table, livraison locale et vente en ligne de sakés rares importés.",
  },
  {
    label: "Boutique de vêtements éthiques",
    query:
      "Je lance une boutique de vêtements éthiques à Bordeaux pour une clientèle 25-45 ans urbaine, avec une boutique physique et un site e-commerce.",
  },
  {
    label: "Coworking familial en Normandie",
    query:
      "Je veux créer un espace de coworking avec garderie intégrée à Caen pour les jeunes parents entrepreneurs, en location à la journée ou au mois.",
  },
  {
    label: "Atelier d'impression 3D B2B",
    query:
      "Je monte un atelier d'impression 3D B2B à Toulouse pour produire des prototypes et petites séries pour PME industrielles locales.",
  },
];

/**
 * Écran d'accueil de l'agent Atelier. Exposé comme `Page = "atelier"` dans
 * page.tsx quand l'utilisateur clique sur la carte hero.
 */
export default function AgentWelcome({
  onBack,
  onSubmit,
  projectFolders = [],
  disabled = false,
  loading = false,
}: Props) {
  const meta = AGENT_META.atelier;
  const [pitch, setPitch] = useState("");
  /** "" = nouveau projet (comportement par défaut côté API). */
  const [attachFolderId, setAttachFolderId] = useState("");

  const canSubmit = pitch.trim().length >= 20 && !disabled && !loading;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const fid = attachFolderId.trim();
    onSubmit(pitch.trim(), fid ? fid : null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="scrollbar-thin flex flex-1 flex-col overflow-y-auto">
      <div className="mx-auto w-full max-w-screen-2xl px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
        <div className="mx-auto w-full max-w-3xl">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="-ml-2 mb-8 gap-2 text-muted-foreground"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            Retour à l&apos;accueil
          </Button>

          <Card className="mb-6 overflow-hidden border-border/80 shadow-sm sm:mb-8">
            <CardContent className="border-l-[3px] border-primary/70 px-5 py-7 sm:px-8 sm:py-9">
              <div className="mb-6 flex items-start gap-4">
                <div
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-border bg-primary/10 text-primary sm:h-12 sm:w-12"
                  aria-hidden
                >
                  <Compass className="size-5" strokeWidth={2} />
                </div>
                <div className="min-w-0 pt-0.5">
                  <p className="mb-1 text-[11px] font-medium tracking-wide text-primary">
                    Atelier
                  </p>
                  <h1 className="font-serif text-xl font-semibold leading-snug tracking-tight text-foreground sm:text-2xl">
                    Parcours guidé — du pitch au dossier
                  </h1>
                </div>
              </div>

              <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
                Quelques phrases sur le projet, puis 4 questions. Livrable : business
                model, flux, et{" "}
                <span className="text-foreground">tableaux d&rsquo;entreprises</span>{" "}
                (fournisseurs, clients, concurrents, prestataires) à partir de données
                publiques.
              </p>

              <div className="mt-6 rounded-lg border border-border bg-muted/40 px-4 py-3">
                <Label
                  htmlFor="atelier-projet-rattachement"
                  className="mb-2 text-xs text-muted-foreground"
                >
                  Projet MONV (dossier)
                </Label>
                <Select
                  value={attachFolderId || "__new__"}
                  onValueChange={(v) =>
                    setAttachFolderId(v === "__new__" ? "" : v)
                  }
                  disabled={disabled || loading}
                >
                  <SelectTrigger
                    id="atelier-projet-rattachement"
                    className="w-full"
                  >
                    <SelectValue placeholder="Nouveau projet" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__new__">Nouveau projet (par défaut)</SelectItem>
                    {projectFolders.map((f) => (
                      <SelectItem key={f.id} value={f.id}>
                        {f.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  Par défaut, un <span className="font-medium">nouveau</span> projet
                  est créé pour cette session Atelier. Choisis un projet existant pour
                  tout regrouper au même endroit.
                </p>
              </div>

              <div className="mt-7">
                <Label htmlFor="pitch" className="mb-2 text-xs text-muted-foreground">
                  Description du projet
                </Label>
                <Textarea
                  id="pitch"
                  value={pitch}
                  onChange={(e) => setPitch(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={disabled || loading}
                  rows={5}
                  placeholder={meta.placeholder}
                  className="min-h-[140px] resize-none text-sm leading-relaxed"
                />
                <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                  <p className="max-w-md text-[11px] leading-relaxed text-muted-foreground">
                    Plus tu donnes de contexte (secteur, ville, cible), meilleur
                    sera le dossier.{" "}
                    <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-sans text-[10px] not-italic text-muted-foreground">
                      ⌘ + Entrée
                    </kbd>{" "}
                    pour envoyer.
                  </p>
                  <Button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!canSubmit}
                    className="min-h-[44px] shrink-0 gap-2"
                  >
                    {loading ? "Analyse en cours…" : "Lancer l'Atelier"}
                    {!loading && <ArrowRight className="size-4" aria-hidden />}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Formulations types (à adapter)
            </p>
            <ul className="flex flex-col gap-1.5">
              {EXAMPLE_PITCHES.map((ex) => (
                <li key={ex.label}>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={disabled || loading}
                    onClick={() => setPitch(ex.query)}
                    className="h-auto min-h-0 w-full flex-col items-start gap-1 whitespace-normal py-2.5 text-left"
                  >
                    <span className="text-sm font-medium leading-snug text-foreground">
                      {ex.label}
                    </span>
                    <span className="line-clamp-2 text-[11px] font-normal leading-snug text-muted-foreground">
                      {ex.query}
                    </span>
                  </Button>
                </li>
              ))}
            </ul>
          </div>

          <Card className="mt-8 border-border/80 bg-muted/30">
            <CardContent className="flex items-start gap-3 px-4 py-3.5">
              <Compass
                className="mt-0.5 size-3.5 shrink-0 text-primary"
                aria-hidden
              />
              <p className="text-xs leading-relaxed text-muted-foreground">
                L&rsquo;Atelier enchaîne plusieurs recherches MONV dans une même session
                (une recherche par type d&rsquo;entreprise repéré). Export comme une
                recherche classique ; crédits débités à l&rsquo;export.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
