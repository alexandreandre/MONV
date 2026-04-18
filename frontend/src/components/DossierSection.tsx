"use client";

import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export default function DossierSection({
  icon: Icon,
  title,
  subtitle,
  children,
}: {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section>
      <div className="flex items-start gap-3 mb-3 px-1">
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-gray-300">
          <Icon size={15} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          {subtitle && (
            <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      {children}
    </section>
  );
}
