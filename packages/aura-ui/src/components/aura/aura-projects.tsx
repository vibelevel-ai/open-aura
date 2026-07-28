import React from "react";

import type { AuraProject } from "../../lib/aura/types";

export function AuraProjects({ projects }: { projects: AuraProject[] }) {
  return (
    <section className="mt-8" aria-labelledby="aura-projects-title">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="aura-projects-title" className="text-xl font-semibold tracking-tight text-white md:text-2xl">
            What they build
          </h2>
          <p className="mt-1 text-sm text-[var(--vibecoder-text-secondary)]">
            Project evidence grouped from repeated, sanitized repository context.
          </p>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-[.14em] text-[var(--vibecoder-accent)]">
          Evidence-weighted
        </span>
      </div>
      {projects.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <article
              key={project.name}
              className="flex min-h-40 flex-col rounded-[20px] border border-[rgba(255,255,255,.08)] bg-[rgba(13,18,30,.94)] p-5"
            >
              <h3 title={project.name} className="break-all text-lg font-semibold text-white">
                {project.name}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
                {project.summary || "Project context observed across scored sessions."}
              </p>
              <div className="mt-auto flex flex-wrap gap-2 pt-5">
                <span className="rounded-lg border border-[rgba(0,230,118,.28)] bg-[rgba(0,230,118,.08)] px-2.5 py-1 font-mono text-[10px] text-[var(--vibecoder-accent)]">
                  {project.aura_score.toFixed(1)} PROJECT AURA
                </span>
                <span className="rounded-lg border border-[rgba(255,255,255,.1)] px-2.5 py-1 font-mono text-[10px] text-[var(--vibecoder-text-secondary)]">
                  {project.session_count} SESSION{project.session_count === 1 ? "" : "S"}
                </span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="rounded-[20px] border border-dashed border-[rgba(255,255,255,.12)] bg-[rgba(13,18,30,.6)] p-6">
          <p className="text-sm text-[var(--vibecoder-text-secondary)]">
            No project evidence yet. Newly scored sessions can add sanitized repository and project context automatically.
          </p>
        </div>
      )}
    </section>
  );
}
