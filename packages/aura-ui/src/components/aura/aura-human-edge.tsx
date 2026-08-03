import React from "react";

import type { DimensionScore } from "../../lib/aura/types";

const ROWS = [
  ["Independent code understanding", "human_contribution"],
  ["Validation & judgement", "ai_pairing"],
  ["Debugging autonomy", "product_thinking"],
  ["Plan-first decomposition", "prompting"],
  ["Testing & verification", "design_thinking"],
] as const;

export function AuraHumanEdge({
  dimensions,
}: {
  dimensions: Record<string, DimensionScore>;
}) {
  const rows = ROWS.flatMap(([label, key]) => {
    const value = dimensions[key]?.score;
    return typeof value === "number" ? [{ label, value }] : [];
  });
  if (!rows.length) return null;
  return (
    <section className="mt-8 rounded-[22px] border border-[rgba(255,255,255,.08)] bg-[rgba(13,18,30,.94)] p-5 md:p-6">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-semibold text-white">Human edge</h2>
          <span className="rounded-full bg-[rgba(0,230,118,.1)] px-2.5 py-1 font-mono text-[9px] font-semibold uppercase tracking-[.1em] text-[var(--vibecoder-accent)]">
            From sessions
          </span>
        </div>
        <p className="mt-1 text-sm text-[var(--vibecoder-text-secondary)]">
          Independent-work indicators derived from the existing Aura dimensions.
        </p>
      </div>
      <div className="mt-4 divide-y divide-[rgba(255,255,255,.07)]">
        {rows.map((row) => (
          <div key={row.label} className="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_180px] sm:items-center">
            <span className="text-sm font-medium text-white">{row.label}</span>
            <div className="flex items-center gap-3">
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[rgba(255,255,255,.07)]">
                <span
                  className="block h-full rounded-full bg-[var(--vibecoder-accent)]"
                  style={{ width: `${Math.max(0, Math.min(100, row.value * 10))}%` }}
                />
              </span>
              <span className="w-8 text-right font-mono text-sm font-semibold text-white">
                {row.value.toFixed(1)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
