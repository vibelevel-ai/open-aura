import React from "react";

import type { AuraToolkit as AuraToolkitData, ProfileResponse, ToolkitEntry } from "../../lib/aura/types";
import { prettySource } from "../../lib/aura/format";

function RankedList({
  entries,
  empty,
}: {
  entries: ToolkitEntry[];
  empty: string;
}) {
  if (!entries.length) {
    return <p className="text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">{empty}</p>;
  }
  return (
    <div className="divide-y divide-[rgba(255,255,255,.07)]">
      {entries.slice(0, 8).map((entry) => (
        <div key={entry.name} className="flex min-w-0 items-center justify-between gap-3 py-2.5">
          <span title={entry.name} className="min-w-0 break-all text-sm font-medium text-white">
            {entry.name}
          </span>
          <span className="flex-shrink-0 font-mono text-xs text-[var(--vibecoder-text-secondary)]">
            {entry.count}
          </span>
        </div>
      ))}
    </div>
  );
}

function countsToEntries(counts?: Record<string, number>, source = false): ToolkitEntry[] {
  return Object.entries(counts ?? {})
    .map(([name, count]) => ({ name: source ? prettySource(name) : name, count }))
    .sort((left, right) => right.count - left.count || (left.name < right.name ? -1 : left.name > right.name ? 1 : 0));
}

export function AuraToolkit({ profile }: { profile: ProfileResponse }) {
  const toolkit: AuraToolkitData = profile.toolkit ?? {};
  const agents = countsToEntries(toolkit.sources ?? profile.sources, true);
  const models = countsToEntries(toolkit.models);
  const toolsAndSkills = [...(toolkit.tools ?? []), ...(toolkit.skills ?? []).map((item) => ({
    ...item,
    name: `Skill · ${item.name}`,
  }))].sort((left, right) => right.count - left.count || (left.name < right.name ? -1 : 1));

  return (
    <section className="mt-8" aria-labelledby="aura-toolkit-title">
      <div className="mb-4">
        <h2 id="aura-toolkit-title" className="text-xl font-semibold tracking-tight text-white md:text-2xl">
          AI-native toolkit
        </h2>
        <p className="mt-1 text-sm text-[var(--vibecoder-text-secondary)]">
          Measured and inferred from locally scored sessions—never filled with demo values.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {[
          {
            title: "Agents",
            subtitle: models.length ? `Models: ${models.map((item) => item.name).slice(0, 3).join(", ")}` : "Sources used across sessions",
            entries: agents,
            empty: "Score sessions from an AI agent to build this distribution.",
          },
          {
            title: "MCP servers",
            subtitle: "Sanitized names observed in workspace context",
            entries: toolkit.mcp_servers ?? [],
            empty: "No MCP server names have been observed in scored sessions.",
          },
          {
            title: "Tools & skills",
            subtitle: "Measured call and invocation counts",
            entries: toolsAndSkills,
            empty: "This source has not reported tool or skill telemetry yet.",
          },
        ].map((card) => (
          <article
            key={card.title}
            className="rounded-[20px] border border-[rgba(255,255,255,.08)] bg-[rgba(13,18,30,.94)] p-5"
          >
            <h3 className="text-base font-semibold text-white">{card.title}</h3>
            <p className="mb-3 mt-1 text-xs leading-relaxed text-[var(--vibecoder-text-secondary)]">
              {card.subtitle}
            </p>
            <RankedList entries={card.entries} empty={card.empty} />
          </article>
        ))}
      </div>
    </section>
  );
}
