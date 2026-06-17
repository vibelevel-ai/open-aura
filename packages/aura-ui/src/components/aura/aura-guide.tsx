'use client';

// VibeLevel Aura — "How your Aura works" guide (reusable dialog).
//
// Wide two-pane dialog: a left topic nav + a scrollable content pane. Sections:
// Overview · Score levels · Archetypes (coding/writing) · Privacy. Highlights the
// viewer's current level + archetype when known. Pass the trigger via `trigger`.

import { useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogTrigger,
  DialogTitle,
  DialogDescription,
} from '../ui/dialog';
import { Code, FileText, Shield, BarChart3, Sparkles, Layers } from 'lucide-react';
import { AURA_LEVELS, AURA_ARCHETYPES } from '../../lib/aura/taxonomy';

const GREEN = '#00e676';

function levelColor(name: string): string {
  return name === 'Emerging' ? '#6b7280' : GREEN;
}

const NAV = [
  { id: 'overview', label: 'Overview', icon: Sparkles },
  { id: 'levels', label: 'Score levels', icon: BarChart3 },
  { id: 'archetypes', label: 'Archetypes', icon: Layers },
  { id: 'using-aura', label: 'Using Aura', icon: Code },
  { id: 'privacy', label: 'Privacy', icon: Shield },
] as const;

const WHAT_YOU_GET: { title: string; sub: string }[] = [
  { title: 'Cards', sub: 'your strengths & quirks' },
  { title: 'Archetype', sub: 'your working persona' },
  { title: 'Level', sub: 'where you stand' },
  { title: 'Leaderboard', sub: 'how you rank' },
];

const AURA_COMMANDS = [
  {
    category: 'Getting Started',
    icon: Sparkles,
    commands: [
      { prompt: '"aura whoami"', description: 'Confirm the connection + which account' },
      { prompt: '"import my recent history"', description: 'Bootstrap your Aura from past sessions' },
      { prompt: '"show my profile"', description: 'View your current Aura score and archetype' },
    ],
  },
  {
    category: 'Scoring Sessions',
    icon: BarChart3,
    commands: [
      { prompt: '"score this session"', description: 'Score the session you just finished (the current one)' },
      { prompt: '"score the last 5 sessions"', description: 'Batch-score recent sessions from your local history' },
    ],
  },
  {
    category: 'Insights & Analytics',
    icon: Layers,
    commands: [
      { prompt: '"show my strengths"', description: 'See which dimensions you excel at' },
      { prompt: '"what\'s my archetype?"', description: 'Get your current archetype and what it means' },
      { prompt: '"show my progress"', description: 'See your trends, percentile and personal bests' },
    ],
  },
];

export function AuraGuide({
  trigger,
  currentLevel,
  currentArchetype,
  modality = 'coding',
}: {
  trigger: React.ReactNode;
  currentLevel?: string;
  currentArchetype?: string;
  modality?: 'coding' | 'noncoding';
}) {
  const [tab, setTab] = useState<'coding' | 'noncoding'>(modality);
  const archetypes = AURA_ARCHETYPES[tab];
  const ArchIcon = tab === 'coding' ? Code : FileText;

  const overviewRef = useRef<HTMLDivElement>(null);
  const levelsRef = useRef<HTMLDivElement>(null);
  const archetypesRef = useRef<HTMLDivElement>(null);
  const usingAuraRef = useRef<HTMLDivElement>(null);
  const privacyRef = useRef<HTMLDivElement>(null);
  const refs: Record<string, React.RefObject<HTMLDivElement>> = {
    overview: overviewRef,
    levels: levelsRef,
    archetypes: archetypesRef,
    'using-aura': usingAuraRef,
    privacy: privacyRef,
  };
  const go = (id: string) =>
    refs[id]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="w-[95vw] max-w-6xl gap-0 overflow-hidden border-[var(--vibecoder-border)] bg-[var(--vibecoder-panel)] p-0 text-[var(--vibecoder-text-primary)]">
        <div className="flex max-h-[85vh] flex-col">{/* Header */}
          <div className="border-b border-[rgba(255,255,255,0.06)] px-6 py-4 pr-12">
            <DialogTitle className="text-lg text-white">How your Aura works</DialogTitle>
            <DialogDescription className="sr-only">
              VibeLevel Aura scoring — levels, archetypes and privacy.
            </DialogDescription>
          </div>

          <div className="flex min-h-0 flex-1">
            {/* Left topic nav */}
            <nav className="hidden w-52 flex-shrink-0 flex-col gap-1 border-r border-[rgba(255,255,255,0.06)] p-3 md:flex">{NAV.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => go(n.id)}
                  className="flex items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm text-[var(--vibecoder-text-secondary)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-white"
                >
                  <n.icon className="h-4 w-4 flex-shrink-0 opacity-70" />
                  {n.label}
                </button>
              ))}
            </nav>

            {/* Content */}
            <div className="min-w-0 flex-1 space-y-8 overflow-y-auto px-6 py-5">
              {/* Overview */}
              <section ref={overviewRef} className="scroll-mt-4 space-y-3">
                <h3 className="text-sm font-semibold text-white">Overview</h3>
                <p className="text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
                  Aura scores how you{' '}
                  <span className="text-[var(--vibecoder-text-primary)]">actually</span> work with AI
                  — referencelessly, from your real sessions (no test). Each session is rated 0–10 on
                  prompting, AI collaboration, product thinking, design sense and your own
                  contribution. The overall score maps to a <span className="text-[var(--vibecoder-text-primary)]">level</span>;
                  your habits map to an <span className="text-[var(--vibecoder-text-primary)]">archetype</span>.
                </p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {WHAT_YOU_GET.map((w) => (
                    <div
                      key={w.title}
                      className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] px-3 py-2"
                    >
                      <p className="text-xs font-semibold text-[var(--vibecoder-text-primary)]">{w.title}</p>
                      <p className="mt-0.5 text-[11px] leading-tight text-[var(--vibecoder-text-secondary)]">{w.sub}</p>
                    </div>
                  ))}
                </div>
              </section>

              {/* Score levels */}
              <section ref={levelsRef} className="scroll-mt-4 space-y-2">
                <h3 className="text-sm font-semibold text-white">Score levels</h3>
                <div className="space-y-1.5">
                  {AURA_LEVELS.map((lv) => {
                    const active = currentLevel === lv.name;
                    const c = levelColor(lv.name);
                    return (
                      <div
                        key={lv.name}
                        className={`flex items-center gap-3 rounded-lg border px-3 py-2 ${active ? '' : 'border-[rgba(139,146,184,0.12)]'}`}
                        style={active ? { borderColor: `${c}66`, background: `${c}14` } : undefined}
                      >
                        <span className="w-24 flex-shrink-0 text-sm font-semibold" style={{ color: c }}>
                          {lv.name}
                        </span>
                        <span className="w-12 flex-shrink-0 font-mono text-xs text-[var(--vibecoder-text-secondary)]">
                          {lv.min}–{lv.max}
                        </span>
                        <span className="min-w-0 flex-1 text-xs leading-snug text-[var(--vibecoder-text-secondary)]">
                          {lv.blurb}
                        </span>
                        {active && (
                          <span className="flex-shrink-0 font-mono text-[10px] uppercase tracking-[0.12em]" style={{ color: c }}>
                            You
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Archetypes */}
              <section ref={archetypesRef} className="scroll-mt-4 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-white">Archetypes</h3>
                  <div className="inline-flex rounded-lg border border-[rgba(139,146,184,0.18)] p-0.5">
                    {(['coding', 'noncoding'] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setTab(m)}
                        className={`rounded-md px-2.5 py-1 font-mono text-xs transition-colors ${
                          tab === m
                            ? 'bg-[rgba(255,255,255,0.1)] text-white'
                            : 'text-[var(--vibecoder-text-secondary)] hover:text-white'
                        }`}
                      >
                        {m === 'coding' ? 'Coding' : 'Writing'}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid gap-1.5 sm:grid-cols-2">
                  {archetypes.map((a) => {
                    const active = currentArchetype === a.name;
                    return (
                      <div
                        key={a.name}
                        className={`rounded-lg border px-3 py-2 ${active ? '' : 'border-[rgba(139,146,184,0.12)]'}`}
                        style={active ? { borderColor: `${GREEN}66`, background: `${GREEN}14` } : undefined}
                      >
                        <div className="flex items-center gap-2">
                          <ArchIcon
                            className="h-3.5 w-3.5 flex-shrink-0"
                            style={{ color: active ? GREEN : 'var(--vibecoder-text-secondary)' }}
                          />
                          <span
                            className="text-sm font-semibold"
                            style={{ color: active ? GREEN : 'var(--vibecoder-text-primary)' }}
                          >
                            {a.name}
                          </span>
                          {active && (
                            <span className="font-mono text-[10px] uppercase tracking-[0.12em]" style={{ color: GREEN }}>
                              You
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 text-xs leading-snug text-[var(--vibecoder-text-secondary)]">
                          {a.tagline}
                        </p>
                      </div>
                    );
                  })}
                </div>
                <p className="pt-1 text-[11px] text-[var(--vibecoder-text-secondary)] opacity-70">
                  Your archetype comes from your contribution level + your signature dimensions, not
                  your score — two builders at the same level can be different archetypes.
                </p>
              </section>

              {/* Using Aura */}
              <section ref={usingAuraRef} className="scroll-mt-4 space-y-4">
                <h3 className="text-sm font-semibold text-white">Using Aura — Example Commands</h3>
                <p className="text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
                  Once you've connected the MCP Connector to your AI agent, ask your agent these commands to interact with Aura.
                </p>
                <div className="space-y-4">
                  {AURA_COMMANDS.map((section) => {
                    const CategoryIcon = section.icon;
                    return (
                      <div key={section.category}>
                        <div className="mb-2.5 flex items-center gap-2">
                          <CategoryIcon className="h-3.5 w-3.5 text-[var(--vibecoder-accent)]" />
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--vibecoder-text-primary)]">
                            {section.category}
                          </h4>
                        </div>
                        <div className="space-y-2">
                          {section.commands.map((cmd, i) => (
                            <div
                              key={i}
                              className="rounded-lg border border-[rgba(0,230,118,0.15)] bg-[rgba(0,230,118,0.03)] p-3"
                            >
                              <code className="block font-mono text-xs font-semibold text-[var(--vibecoder-accent)]">
                                {cmd.prompt}
                              </code>
                              <p className="mt-1 text-[11px] leading-snug text-[var(--vibecoder-text-secondary)]">
                                {cmd.description}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Privacy */}
              <section ref={privacyRef} className="scroll-mt-4 space-y-3">
                <h3 className="text-sm font-semibold text-white">Privacy — what we collect</h3>
                <p className="text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
                  Everything is redacted on your machine before it&apos;s sent. We never see your{' '}
                  <span className="text-[var(--vibecoder-text-primary)]">full</span> prompts, files or
                  transcripts — coding or writing. Only truncated excerpts, file names (not their
                  contents), and your collaboration &amp; skill signals are submitted for scoring.
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-[rgba(0,230,118,0.2)] bg-[rgba(0,230,118,0.04)] p-3">
                    <p className="text-xs font-semibold text-[var(--vibecoder-accent)]">Sent (redacted)</p>
                    <ul className="mt-1.5 space-y-1 text-[11px] leading-snug text-[var(--vibecoder-text-secondary)]">
                      <li>· truncated message excerpts</li>
                      <li>· file names / paths (not contents)</li>
                      <li>· token counts &amp; tool usage</li>
                      <li>· the AI model you used</li>
                    </ul>
                  </div>
                  <div className="rounded-lg border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] p-3">
                    <p className="text-xs font-semibold text-white">Never leaves your machine</p>
                    <ul className="mt-1.5 space-y-1 text-[11px] leading-snug text-[var(--vibecoder-text-secondary)]">
                      <li>· full transcripts</li>
                      <li>· full file &amp; code contents</li>
                      <li>· your project&apos;s source</li>
                      <li>· anything you didn&apos;t share</li>
                    </ul>
                  </div>
                </div>
                <div className="rounded-lg border border-[rgba(125,211,252,0.2)] bg-[rgba(125,211,252,0.05)] p-3">
                  <p className="text-xs font-semibold text-[#7dd3fc]">When you share a link</p>
                  <p className="mt-1 text-[11px] leading-snug text-[var(--vibecoder-text-secondary)]">
                    Your public profile and single-session links show a generic, non-revealing label
                    for each session — e.g. &ldquo;An evening build session&rdquo; — never your real
                    session title or what you actually worked on. You still see your real titles when
                    you&apos;re signed in.
                  </p>
                </div>
              </section>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default AuraGuide;
