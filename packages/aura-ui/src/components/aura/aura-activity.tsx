"use client";

import React, { useMemo, useState } from "react";

import type { SessionSummary } from "../../lib/aura/types";
import { prettySource } from "../../lib/aura/format";
import {
  buildAuraActivity,
  type AuraActivityWindowDays,
} from "./aura-activity-data";

const LEVELS = [
  "rgba(255,255,255,0.055)",
  "rgba(0,230,118,0.22)",
  "rgba(0,230,118,0.42)",
  "rgba(0,230,118,0.68)",
  "#00e676",
];

const TIMELINES: Array<{ label: string; value: AuraActivityWindowDays }> = [
  { label: "Last week", value: 7 },
  { label: "Last month", value: 30 },
  { label: "Last year", value: 365 },
];

function levelFor(count: number, max: number): number {
  if (count <= 0 || max <= 0) return 0;
  return Math.max(1, Math.min(4, Math.ceil((count / max) * 4)));
}

export function AuraActivity({ sessions }: { sessions: SessionSummary[] }) {
  const [source, setSource] = useState<string | null>(null);
  const [windowDays, setWindowDays] = useState<AuraActivityWindowDays>(365);
  const activity = useMemo(
    () => buildAuraActivity(sessions, { source, windowDays }),
    [sessions, source, windowDays],
  );
  const maxCount = Math.max(0, ...activity.days.map((day) => day.count));
  const heatmapRows = windowDays === 7 ? 1 : 7;

  return (
    <section className="mt-8" aria-labelledby="aura-activity-title">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2
            id="aura-activity-title"
            className="text-xl font-semibold tracking-tight text-white md:text-2xl"
          >
            AI activity
          </h2>
          <p
            aria-live="polite"
            className="mt-1 text-sm text-[var(--vibecoder-text-secondary)]"
          >
            Your last {windowDays} UTC days, derived only from locally scored sessions.
          </p>
        </div>
        <div className="flex max-w-full flex-wrap gap-2" aria-label="Filter activity by source">
          <button
            type="button"
            onClick={() => setSource(null)}
            aria-pressed={source === null}
            className="rounded-lg border px-3 py-1.5 font-mono text-[11px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--vibecoder-accent)]"
            style={
              source === null
                ? { background: "#00e676", borderColor: "#00e676", color: "#07110b" }
                : { borderColor: "rgba(255,255,255,.12)", color: "rgba(255,255,255,.68)" }
            }
          >
            All
          </button>
          {activity.sources.map((item) => (
            <button
              key={item.source}
              type="button"
              title={prettySource(item.source)}
              onClick={() => setSource(item.source)}
              aria-pressed={source === item.source}
              className="max-w-full break-all rounded-lg border px-3 py-1.5 font-mono text-[11px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--vibecoder-accent)]"
              style={
                source === item.source
                  ? { background: "#00e676", borderColor: "#00e676", color: "#07110b" }
                  : { borderColor: "rgba(255,255,255,.12)", color: "rgba(255,255,255,.68)" }
              }
            >
              {prettySource(item.source)} · {item.count}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-[22px] border border-[rgba(255,255,255,0.08)] bg-[rgba(13,18,30,0.94)] p-4 shadow-[0_12px_40px_rgba(0,0,0,.25)] md:p-6">
        <div className="max-w-full overflow-x-auto pb-1">
          <div
            className="mx-auto grid w-max grid-flow-col gap-[3px]"
            style={{ gridTemplateRows: `repeat(${heatmapRows}, minmax(0, 1fr))` }}
            role="img"
            aria-label={`${windowDays}-day activity heatmap with ${activity.summary.sessionCount} sessions across ${activity.summary.activeDays} active days`}
          >
            {activity.days.map((day) => {
              const level = levelFor(day.count, maxCount);
              const label = `${new Date(`${day.date}T00:00:00Z`).toLocaleDateString("en-US", {
                timeZone: "UTC",
                year: "numeric",
                month: "long",
                day: "numeric",
              })}: ${day.count} session${day.count === 1 ? "" : "s"}`;
              return (
                <span
                  key={day.date}
                  aria-hidden="true"
                  title={label}
                  className="h-3 w-3 rounded-[2px] sm:h-4 sm:w-4"
                  style={{ background: LEVELS[level] }}
                />
              );
            })}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-[rgba(255,255,255,.07)] pt-5 sm:grid-cols-4">
          {[
            ["Sessions", activity.summary.sessionCount],
            ["Active days", activity.summary.activeDays],
            ["Current streak", activity.summary.currentStreak],
            ["Longest streak", activity.summary.longestStreak],
          ].map(([label, value]) => (
            <div key={label}>
              <div className="font-mono text-xl font-bold text-white">{value}</div>
              <div className="mt-0.5 text-xs text-[var(--vibecoder-text-secondary)]">{label}</div>
            </div>
          ))}
        </div>

        <div className="mt-5 flex flex-col gap-3 border-t border-[rgba(255,255,255,.07)] pt-5 sm:flex-row sm:items-center sm:justify-between">
          <span id="aura-timeline-label" className="text-sm font-medium text-white">
            Timeline
          </span>
          <div
            role="group"
            aria-labelledby="aura-timeline-label"
            className="grid w-full grid-cols-3 rounded-lg border border-[rgba(255,255,255,.12)] bg-[rgba(255,255,255,.03)] p-1 sm:w-auto"
          >
            {TIMELINES.map((timeline) => {
              const selected = timeline.value === windowDays;
              return (
                <button
                  key={timeline.value}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setWindowDays(timeline.value)}
                  className={[
                    "min-w-0 rounded-md px-2 py-2 text-center font-mono text-[10px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--vibecoder-accent)] sm:px-3 sm:text-[11px]",
                    selected
                      ? "bg-[#00e676] text-[#07110b]"
                      : "text-[var(--vibecoder-text-secondary)] hover:text-white",
                  ].join(" ")}
                >
                  {timeline.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
