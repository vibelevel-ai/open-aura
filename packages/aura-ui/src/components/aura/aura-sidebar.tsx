'use client';

// VibeLevel Aura — the local viewer's left sidebar.
//
// Persistent rail across the viewer routes: a compact profile summary, the
// section nav (Profile · Getting Started · Leaderboard · Sessions) with the
// active route highlighted, and a teaser of the most recent sessions that links
// out to the full Sessions page. Hidden below md (the content goes full-width).

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { User, Rocket, Trophy, FolderClock, Code, FileText, Upload, Send, type LucideIcon } from 'lucide-react';
import { AURA_LEVEL_COLORS, type SessionSummary } from '../../lib/aura/types';
import { initialsOf } from '../../lib/aura/format';

const GREEN = '#00e676';

// Compact profile summary the shell feeds the sidebar (from /api/aura/me/profile).
export interface AuraSidebarSummary {
  display_name: string;
  aura_score: number;
  aura_level: string;
  archetype?: string;
  session_count: number;
}

const NAV: { href: string; label: string; icon: LucideIcon; exact?: boolean }[] = [
  { href: '/', label: 'Profile', icon: User, exact: true },
  { href: '/getting-started', label: 'Getting Started', icon: Rocket },
  { href: '/leaderboard', label: 'Leaderboard', icon: Trophy },
  { href: '/sessions', label: 'Sessions', icon: FolderClock },
];

// Local mode can't do these — they funnel to the hosted edition. Shown greyed
// so the roadmap is visible without implying they work locally yet.
const COMING_SOON: { label: string; icon: LucideIcon; hint: string }[] = [
  {
    label: 'Import your session',
    icon: Upload,
    hint: 'Bring your local sessions to your VibeLevel account — claim a handle, share & rank. Coming soon.',
  },
  {
    label: 'Submit to leaderboard',
    icon: Send,
    hint: 'Opt in to publish your Aura score to the public leaderboard. Coming soon.',
  },
];

function isActive(pathname: string, href: string, exact?: boolean): boolean {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AuraSidebar({
  recentSessions = [],
  summary = null,
}: {
  recentSessions?: SessionSummary[];
  summary?: AuraSidebarSummary | null;
}) {
  const pathname = usePathname() || '/';
  const levelColor = summary?.aura_level
    ? AURA_LEVEL_COLORS[summary.aura_level] ?? GREEN
    : GREEN;

  return (
    <aside className="hidden w-60 flex-shrink-0 flex-col gap-4 overflow-y-auto border-r border-[rgba(255,255,255,0.07)] bg-[#0b1019] px-3 py-4 md:flex">
      {/* profile mini-summary → Profile */}
      {summary && (
        <Link
          href="/"
          className="flex items-center gap-3 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] px-3 py-3 no-underline transition-colors hover:bg-[rgba(255,255,255,0.04)]"
        >
          <span
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border font-mono text-sm font-bold"
            style={{ color: GREEN, borderColor: 'rgba(0,230,118,0.35)', background: 'rgba(0,230,118,0.10)' }}
          >
            {initialsOf(summary.display_name)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-[var(--vibecoder-text-primary)]">
              {summary.display_name}
            </p>
            <div className="mt-0.5 flex items-center gap-1.5">
              <span className="font-mono text-xs font-bold" style={{ color: GREEN }}>
                {summary.aura_score.toFixed(1)}
              </span>
              {summary.aura_level && (
                <span
                  className="font-mono text-[10px] uppercase tracking-wide"
                  style={{ color: levelColor }}
                >
                  {summary.aura_level}
                </span>
              )}
            </div>
          </div>
        </Link>
      )}

      {/* section nav */}
      <nav className="flex flex-col gap-1">
        {NAV.map((n) => {
          const active = isActive(pathname, n.href, n.exact);
          return (
            <Link
              key={n.href}
              href={n.href}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm no-underline transition-colors ${
                active
                  ? 'bg-[rgba(0,230,118,0.10)] font-semibold'
                  : 'text-[var(--vibecoder-text-secondary)] hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--vibecoder-text-primary)]'
              }`}
              style={active ? { color: GREEN } : undefined}
            >
              <n.icon className="h-4 w-4 flex-shrink-0" style={active ? { color: GREEN } : undefined} />
              {n.label}
            </Link>
          );
        })}
      </nav>

      {/* coming soon — these funnel to the hosted edition; greyed for now */}
      <div className="flex flex-col gap-1">
        <span className="mb-1 px-3 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--vibecoder-text-secondary)] opacity-70">
          Coming Soon
        </span>
        {COMING_SOON.map((c) => (
          <div
            key={c.label}
            title={c.hint}
            aria-disabled="true"
            className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--vibecoder-text-secondary)] opacity-45"
          >
            <c.icon className="h-4 w-4 flex-shrink-0" />
            <span className="min-w-0 flex-1 truncate">{c.label}</span>
            <span className="flex-shrink-0 rounded-full border border-[rgba(139,146,184,0.25)] px-1.5 py-[1px] font-mono text-[9px] uppercase tracking-wide">
              Soon
            </span>
          </div>
        ))}
      </div>

      {/* recent sessions teaser → Sessions page */}
      {recentSessions.length > 0 && (
        <div className="mt-1 flex flex-col">
          <span className="mb-2 px-3 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--vibecoder-text-secondary)] opacity-70">
            Recent Sessions
          </span>
          <div className="flex flex-col gap-1">
            {recentSessions.slice(0, 5).map((s) => {
              const Icon = s.modality === 'coding' ? Code : FileText;
              return (
                <Link
                  key={s.id}
                  href="/sessions"
                  title={s.title || 'Untitled session'}
                  className="flex items-center gap-2.5 rounded-lg px-3 py-2 no-underline transition-colors hover:bg-[rgba(255,255,255,0.04)]"
                >
                  <Icon className="h-3.5 w-3.5 flex-shrink-0" style={{ color: GREEN }} />
                  <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--vibecoder-text-secondary)]">
                    {s.title || 'Untitled session'}
                  </span>
                  <span className="flex-shrink-0 font-mono text-xs font-bold text-[var(--vibecoder-text-secondary)]">
                    {s.aura_score.toFixed(1)}
                  </span>
                </Link>
              );
            })}
          </div>
          <Link
            href="/sessions"
            className="mt-2 px-3 font-mono text-xs font-medium no-underline hover:underline"
            style={{ color: GREEN }}
          >
            See all →
          </Link>
        </div>
      )}
    </aside>
  );
}

export default AuraSidebar;
