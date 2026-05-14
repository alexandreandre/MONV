import Link from "next/link";
import { Button } from "@/components/ui/button";

const MODES = [
  { id: "prospection", label: "Prospection" },
  { id: "sous_traitant", label: "Sous-traitant" },
  { id: "benchmark", label: "Benchmark" },
  { id: "rachat", label: "Rachat" },
  { id: "atelier", label: "Atelier création d’entreprise" },
];

export default function AdminModesListPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">Modes & agents</h1>
        <p className="text-sm text-muted-foreground">
          Un graphe dédié par agent. Sur chaque éditeur, le bouton « JSON » ouvre la topologie et la réponse API en
          texte brut (copie / téléchargement).
        </p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2">
        {MODES.map((m) => (
          <li key={m.id}>
            <Button asChild variant="outline" className="h-auto w-full justify-start px-4 py-6 text-left">
              <Link href={`/admin/modes/${m.id}`}>
                <span className="block text-base font-medium">{m.label}</span>
                <span className="text-xs text-muted-foreground">{m.id}</span>
              </Link>
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
