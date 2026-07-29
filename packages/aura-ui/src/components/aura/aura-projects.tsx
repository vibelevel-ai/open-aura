import type { AuraProject } from "../../lib/aura/types";

function GitHubIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-4 w-4"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 .7a11.5 11.5 0 0 0-3.64 22.41c.58.11.79-.25.79-.56v-2.24c-3.22.7-3.9-1.37-3.9-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.72 1.27 3.38.97.1-.75.4-1.27.74-1.56-2.57-.29-5.27-1.29-5.27-5.73 0-1.27.45-2.3 1.2-3.11-.12-.3-.52-1.48.11-3.07 0 0 .98-.31 3.16 1.19a10.96 10.96 0 0 1 5.75 0c2.19-1.5 3.17-1.19 3.17-1.19.63 1.59.23 2.77.11 3.07.75.81 1.2 1.84 1.2 3.11 0 4.45-2.71 5.43-5.29 5.72.42.36.79 1.06.79 2.14v3.18c0 .31.21.68.8.56A11.5 11.5 0 0 0 12 .7Z" />
    </svg>
  );
}

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
              <div className="flex items-start justify-between gap-3">
                <h3 title={project.name} className="min-w-0 break-all text-lg font-semibold text-white">
                  {project.name}
                </h3>
                {project.github_url ? (
                  <a
                    href={project.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Open ${project.name} on GitHub`}
                    title={`Open ${project.name} on GitHub`}
                    className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-[rgba(255,255,255,.14)] text-[var(--vibecoder-text-secondary)] transition-colors hover:border-[rgba(0,230,118,.4)] hover:text-[var(--vibecoder-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--vibecoder-accent)]"
                  >
                    <GitHubIcon />
                  </a>
                ) : (
                  <button
                    type="button"
                    disabled
                    aria-disabled="true"
                    aria-label={`GitHub repository unavailable for ${project.name}`}
                    title="GitHub repository unavailable"
                    className="inline-flex h-9 w-9 flex-shrink-0 cursor-not-allowed items-center justify-center rounded-lg border border-[rgba(255,255,255,.08)] text-[var(--vibecoder-text-secondary)] opacity-40"
                  >
                    <GitHubIcon />
                  </button>
                )}
              </div>
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
