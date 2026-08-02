'use client';

// VibeLevel Aura profile renderer shared by the local and hosted viewers.
//
// Sections (top → bottom):
//   1. Reference-style identity hero + score ring.
//   2. Local evidence: profile signals, activity, toolkit, and projects.
//   3. Dimensions + human edge.
//   4. Insights with existing layout/scope/filter controls.
//   5. Recent sessions and explicit hosted publication boundary.
//
// HARD COLOR RULE: white / green / dark only. NO purple/violet.
//   Behavioral / primary → GREEN.  Personality / mid → AMBER (#f59e0b).  low → RED.
// font-mono used for the techy labels/chips (the mock is monospace-flavored).

import { useEffect, useMemo, useState } from 'react';
import { Card } from '../ui/card';
import { Code, FileText, Share2, Check, Rocket, HelpCircle, EyeOff, Heart } from 'lucide-react';
import { toast } from 'sonner';
import {
  AURA_LEVEL_COLORS,
  type ProfileResponse,
  type SessionSummary,
  type DimensionScore,
  type Card as AuraCard,
} from '../../lib/aura/types';
import { InsightCard } from './insight-card';
import { AuraGuide } from './aura-guide';
import { dominantModality } from '../../lib/aura/taxonomy';
import { formatTokens } from '../../lib/aura/format';
import { type AuraViewerConfig, resolveViewerConfig } from '../../lib/aura/viewer-config';
import { AuraActivity } from './aura-activity';
import { AuraToolkit } from './aura-toolkit';
import { AuraProjects } from './aura-projects';
import { AuraHumanEdge } from './aura-human-edge';
import { AuraPublishCta } from './aura-publish-cta';

// ─── color helpers ───────────────────────────────────────────────────────────
// Canonical VibeLevel green (#00e676 === var(--vibecoder-accent)). Use this for
// every brand-accent surface: score, archetype, level badge, links, high band.
const GREEN_HEX = '#00e676';
const AMBER = '#f59e0b';
const RED = '#ef4444';
const BLUE = '#7dd3fc'; // Exceptional (8+) — ice blue, distinct from the green band

// Dimension-bar fill color by 0-10 score.
//   ≥8 → blue (Exceptional) · 7–7.9 → green (brand) · 4–6.9 → amber · <4 → red
function scoreColor(score: number): string {
  if (score >= 8) return BLUE;
  if (score >= 7) return GREEN_HEX;
  if (score >= 4) return AMBER;
  return RED;
}

function levelColor(level: string): string {
  return AURA_LEVEL_COLORS[level] ?? GREEN_HEX;
}

// ─── label helpers ───────────────────────────────────────────────────────────
function initialsOf(name: string): string {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const SOURCE_LABEL: Record<string, string> = {
  claude_code: 'Claude Code',
  cursor: 'Cursor',
  codex: 'Codex',
  claude_desktop: 'Claude Desktop',
  web: 'Web',
};

function prettySource(src: string): string {
  return (SOURCE_LABEL[src] ?? src.replace(/_/g, ' ')).toUpperCase();
}

// The profile's primary source = the source key with the most sessions.
function primarySource(sources: Record<string, number>): string | null {
  const entries = Object.entries(sources || {});
  if (entries.length === 0) return null;
  entries.sort((a, b) => b[1] - a[1]);
  return entries[0][0];
}

// coding → CODING · noncoding → WRITING.
function modalityChip(modality: string): string {
  return modality === 'coding' ? 'CODING' : 'WRITING';
}

// Derive an overall modality chip from the session feed's modalities.
function overallModality(sessions: SessionSummary[]): string | null {
  const hasCoding = sessions.some((s) => s.modality === 'coding');
  const hasWriting = sessions.some((s) => s.modality !== 'coding');
  if (hasCoding && hasWriting) return 'CODING + WRITING';
  if (hasCoding) return 'CODING';
  if (hasWriting) return 'WRITING';
  return null;
}

function formatDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

// ─── dimension config (OUR dims, fixed order) ────────────────────────────────
const DIM_ORDER: { key: string; label: string }[] = [
  { key: 'prompting', label: 'PROMPTING' },
  { key: 'ai_pairing', label: 'AI COLLABORATION' },
  { key: 'product_thinking', label: 'PRODUCT THINKING' },
  { key: 'design_thinking', label: 'DESIGN SENSE' },
  { key: 'human_contribution', label: 'YOU VS AI' },
];

// ─── small mono chip ─────────────────────────────────────────────────────────
// size 'sm' (default) for dense lists (session rows); 'md' for the hero chips
// where they need to read clearly under the score.
// fill=true → the chip stretches to fill its grid cell (equal-width hero row)
// and truncates long values (e.g. a long model name) instead of widening.
function MonoChip({
  children,
  size = 'sm',
  fill = false,
}: {
  children: React.ReactNode;
  size?: 'sm' | 'md';
  fill?: boolean;
}) {
  const sz = size === 'md' ? 'px-2.5 py-1 text-[12px]' : 'px-2 py-0.5 text-[10px]';
  const box = fill ? 'flex w-full min-w-0 justify-center' : 'inline-flex';
  return (
    <span className={`${box} items-center rounded-md border border-[rgba(139,146,184,0.18)] bg-[rgba(139,146,184,0.06)] font-mono font-medium uppercase tracking-[0.12em] text-[var(--vibecoder-text-secondary)] ${sz}`}>
      {fill ? <span className="truncate">{children}</span> : children}
    </span>
  );
}

// ─── segmented toggle ────────────────────────────────────────────────────────
interface SegOption<T extends string> {
  value: T;
  label: string;
  disabled?: boolean;
}

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label?: string;
  value: T;
  options: SegOption<T>[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      {label && (
        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--vibecoder-text-secondary)] opacity-70">
          {label}
        </span>
      )}
      <div className="inline-flex items-center rounded-lg border border-[rgba(139,146,184,0.18)] bg-[rgba(139,146,184,0.04)] p-0.5">
        {options.map((opt) => {
          const active = opt.value === value;
          return (
            <button
              key={opt.value}
              type="button"
              disabled={opt.disabled}
              onClick={() => !opt.disabled && onChange(opt.value)}
              className={[
                'rounded-md px-3 py-1 font-mono text-[13px] font-medium tracking-wide transition-colors',
                opt.disabled
                  ? 'cursor-not-allowed text-[var(--vibecoder-text-secondary)] opacity-35'
                  : active
                    ? 'bg-[rgba(255,255,255,0.10)] text-white'
                    : 'text-[var(--vibecoder-text-secondary)] hover:text-white',
              ].join(' ')}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── sparkline (last-N dimension scores) ────────────────────────────────────
function Sparkline({ data }: { data: number[] }) {
  if (!data || data.length < 2) return null;
  const w = 72;
  const h = 18;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
  // Up over the window → green; flat/down → amber.
  const up = data[data.length - 1] >= data[0];
  const stroke = up ? GREEN_HEX : AMBER;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible" aria-hidden>
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ─── dimension bar ───────────────────────────────────────────────────────────
function DimensionBar({ label, score, trend }: { label: string; score: number; trend?: number[] }) {
  const color = scoreColor(score);
  return (
    <div className="rounded-lg border border-[rgba(139,146,184,0.12)] bg-[rgba(139,146,184,0.03)] p-3.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--vibecoder-text-secondary)]">
          {label}
        </span>
        <div className="flex items-center gap-2.5">
          {trend && trend.length >= 2 && <Sparkline data={trend} />}
          <span className="font-mono text-sm font-bold" style={{ color }}>
            {score.toFixed(1)}
          </span>
        </div>
      </div>
      <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-[rgba(139,146,184,0.15)]">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.max(0, Math.min(100, score * 10))}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

// ─── usage tile (telemetry, NOT a 0-10 score) ────────────────────────────────
// Compact token count (M / K / plain) — one formatter so every surface matches.
const formatCompact = formatTokens;

// Sits in the Dimensions 2-col grid as the 6th cell — same dark tile look as
// DimensionBar, but a compact stat block instead of a bar. Profile-level
// summary: identical in both the avg and selected-session dim views.
function UsageTile({
  stats,
}: {
  stats: NonNullable<ProfileResponse['stats']>;
}) {
  const avgTokens = stats.avg_tokens_per_session ?? 0;
  const avgPrompts = stats.avg_prompts_per_session ?? 0;
  const topModel = stats.top_model;
  return (
    <div className="rounded-lg border border-[rgba(139,146,184,0.12)] bg-[rgba(139,146,184,0.03)] p-3.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--vibecoder-text-secondary)]">
          Usage
        </span>
        <span
          className="font-mono text-[10px] uppercase tracking-[0.12em]"
          style={{ color: 'var(--vibecoder-accent)' }}
        >
          Telemetry
        </span>
      </div>
      <div className="mt-2.5 grid grid-cols-3 gap-2">
        <div className="min-w-0">
          <div className="truncate font-mono text-sm font-bold text-white">
            {formatCompact(avgTokens)}
          </div>
          <div className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-[var(--vibecoder-text-secondary)]">
            tok/session
          </div>
        </div>
        <div className="min-w-0">
          <div className="truncate font-mono text-sm font-bold text-white">
            {avgPrompts.toFixed(1)}
          </div>
          <div className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-[var(--vibecoder-text-secondary)]">
            prompts/sn
          </div>
        </div>
        <div className="min-w-0">
          <div className="truncate font-mono text-sm font-bold text-white" title={topModel || undefined}>
            {topModel || '—'}
          </div>
          <div className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-[var(--vibecoder-text-secondary)]">
            model
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── session-detail fetch (memoised per session in the cache) ────────────────
interface SessionDetail {
  cards: AuraCard[];
  dimension_scores?: Record<string, DimensionScore>;
  title?: string;
}

async function fetchSessionDetail(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`/api/aura/session/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to load session detail (${res.status})`);
  const data = await res.json();
  return {
    cards: Array.isArray(data.cards) ? (data.cards as AuraCard[]) : [],
    dimension_scores:
      data.dimension_scores && typeof data.dimension_scores === 'object'
        ? (data.dimension_scores as Record<string, DimensionScore>)
        : undefined,
    title: typeof data.title === 'string' ? data.title : undefined,
  };
}

type DimView = 'avg' | 'selected';
type Scope = 'overall' | 'session';
type Layout = 'wall' | 'three';
type Filter = 'all' | 'credibility' | 'personality';

// ─── Profile ─────────────────────────────────────────────────────────────────
// `isPublic` tailors the profile for the shareable /u/{handle} surface: it hides
// owner-only affordances (the per-card public/private eye, the Scope + Dimensions
// session toggles) and the private session feed, and swaps in a visitor sign-up
// CTA. Default (false) = owner's /aura view, unchanged.
export function AuraProfile({
  profile,
  isPublic = false,
  showRecentSessions = true,
  lockedSession,
  config,
}: {
  profile: ProfileResponse;
  isPublic?: boolean;
  // When false, the bottom Recent Sessions feed (owner) / visitor CTA (public)
  // is hidden — Open Aura moves the session feed into the sidebar + /sessions.
  showRecentSessions?: boolean;
  // Edition config — funnel labels/links + share behavior. The host passes
  // Open Aura's config (Sign in → vibelevel.ai, share → signup).
  config?: AuraViewerConfig;
  // Single-session share (/s/{id}): lock the whole view to ONE session — its
  // hero, chips, footer, insight cards and dimensions — with the public visitor
  // chrome. The detail is seeded (no fetch); the Scope/Dimensions toggles and
  // the session feed stay hidden. Owner + /u profile flows omit this entirely.
  lockedSession?: {
    id: string;
    cards: AuraCard[];
    dimension_scores?: Record<string, DimensionScore>;
    title?: string;
  };
}) {
  const locked = !!lockedSession;
  const cfg = resolveViewerConfig(config);
  const isLocalOwnerProfile = !locked && !isPublic && cfg.edition === 'local';
  const [copied, setCopied] = useState(false);
  // Count-only profile likes — local override for optimistic updates (null until
  // the visitor likes, then falls back to profile.like_count).
  const [likeCount, setLikeCount] = useState<number | null>(null);

  // Insights controls
  const [layout, setLayout] = useState<Layout>('wall');
  const [scope, setScope] = useState<Scope>(locked ? 'session' : 'overall');
  const [filter, setFilter] = useState<Filter>('all');

  // Dimensions control
  const [dimView, setDimView] = useState<DimView>(locked ? 'selected' : 'avg');

  // Session selection + per-session detail cache. A locked single-session share
  // seeds the selection + detail up front (no fetch); the owner view fetches.
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    lockedSession?.id ?? null,
  );
  const [detailCache, setDetailCache] = useState<Record<string, SessionDetail>>(
    lockedSession
      ? {
          [lockedSession.id]: {
            cards: lockedSession.cards,
            dimension_scores: lockedSession.dimension_scores,
            title: lockedSession.title,
          },
        }
      : {},
  );

  const selectedDetail = selectedSessionId ? detailCache[selectedSessionId] : undefined;
  const selectedSession = useMemo(
    () => profile.sessions.find((s) => s.id === selectedSessionId) ?? null,
    [profile.sessions, selectedSessionId],
  );

  // Hero score reacts to the selected session: when one is selected (owner view),
  // show THAT session's score + level; otherwise the profile average. Public has
  // no session feed, so it always shows the average.
  // Owner drills into a session; a locked share always views its one session,
  // even though it renders with the public visitor chrome.
  const viewingSession = (locked || !isPublic) && !!selectedSessionId && !!selectedSession;
  const heroScore = viewingSession ? selectedSession!.aura_score : profile.aura_score;
  const heroLevel = viewingSession ? (selectedSession!.aura_level || '') : profile.aura_level;
  const lvlColor = levelColor(heroLevel);
  // Token total for the SELECTED session (from its token_footprint card), so the
  // hero chips reflect that one session instead of the profile aggregate.
  const sessionTokens = viewingSession
    ? ((selectedDetail?.cards?.find((c) => c.id === 'token_footprint')?.stat as
        | { tokens?: number }
        | undefined)?.tokens ?? 0)
    : 0;
  // "Ships it" badge: the selected session's lifecycle when viewing one,
  // otherwise the profile-level flag (majority of sessions shipped).
  const shipsIt = viewingSession ? !!selectedSession!.ships_it : !!profile.ships_it;

  const primary = primarySource(profile.sources);
  const overallMod = overallModality(profile.sessions);
  const totalTokens = profile.stats?.total_tokens;
  const profileFacts = profile.profile_facts ?? {};
  const availability = profileFacts.availability?.value?.trim();
  const location = profileFacts.location?.value?.trim();

  // Best single-session score + its level — computed by the backend
  // (build_profile) and surfaced next to "Avg of all sessions". Shown when a
  // real best exists and it differs from the average (otherwise it's redundant).
  const showBest =
    !viewingSession &&
    typeof profile.best_score === 'number' &&
    profile.best_score > 0;

  // ── share (reused logic) ──
  const handleShare = async () => {
    // OSS edition: local profiles aren't shareable. Open the explicit hosted
    // publishing destination; this navigation does not upload local data.
    if (cfg.shareMode === 'signup') {
      if (typeof window !== 'undefined') {
        window.open(cfg.hostedAuraHref, '_blank', 'noopener,noreferrer');
      }
      toast.info('Your Aura stays local until you explicitly publish it');
      return;
    }
    // Viewing a single session → share THAT session via its unguessable link,
    // which works even when the profile is private. Otherwise share the public
    // profile (needs a claimed handle + public visibility).
    const sessionShare = viewingSession && !!selectedSessionId;
    const url = sessionShare
      ? `${window.location.origin}/s/${selectedSessionId}`
      : profile.handle
        ? `${window.location.origin}/u/${profile.handle}`
        : null;
    if (!url) {
      toast.info('Claim a handle in Settings to share your Aura');
      return;
    }
    // Always copy the link (no native share sheet) — predictable across desktop
    // and mobile, and what users expect from a "Share" affordance here.
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success(sessionShare ? 'Session link copied' : 'Profile link copied');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.info(url); // clipboard blocked — surface the URL to copy manually
    }
  };

  // ── like (count-only, public, no auth/dedup): optimistic +1, reconcile ──
  const displayLikes = likeCount ?? profile.like_count ?? 0;
  const likeProfile = async () => {
    if (!profile.handle) return;
    setLikeCount(displayLikes + 1); // optimistic
    try {
      const res = await fetch(
        `/api/aura/profile/${encodeURIComponent(profile.handle)}/like`,
        { method: 'POST' },
      );
      if (res.ok) {
        const data = await res.json();
        if (typeof data?.like_count === 'number') setLikeCount(data.like_count);
      }
    } catch {
      /* keep optimistic value on network error */
    }
  };

  // ── select a session: fetch detail (memoised), sync Dimensions + Scope ──
  const selectSession = async (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setDimView('selected');
    setScope('session');
    if (!detailCache[sessionId]) {
      try {
        const detail = await fetchSessionDetail(sessionId);
        setDetailCache((prev) => ({ ...prev, [sessionId]: detail }));
      } catch {
        setDetailCache((prev) => ({ ...prev, [sessionId]: { cards: [] } }));
      }
    }
  };

  // ── deep-link: ?session={id} pre-selects that session on mount, reusing the
  // same selected-session view as clicking a Recent Sessions row. Lets the
  // sidebar / sessions page link straight into one session's detail (no
  // separate detail page or inline accordion). Owner view only — the public
  // /u view has no session feed. Client-only read (window.location), runs once.
  useEffect(() => {
    if (isPublic) return;
    const sid = new URLSearchParams(window.location.search).get('session');
    if (sid && profile.sessions.some((s) => s.id === sid)) {
      void selectSession(sid);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── insight cards: scope → source set, then filter by class ──
  // While a freshly-selected session's detail is still being fetched, show a
  // skeleton instead of the empty "no insights" state so the grid doesn't flash
  // empty → fill (the "narrow then expands" feel).
  const detailLoading = scope === 'session' && !!selectedSessionId && !selectedDetail;
  const scopedCards: AuraCard[] =
    scope === 'session' ? selectedDetail?.cards ?? [] : profile.cards;
  const filteredCards = scopedCards.filter((c) =>
    filter === 'all' ? true : c.klass === filter,
  );

  const insightGridCols =
    layout === 'wall' ? 'sm:grid-cols-2 xl:grid-cols-4' : 'sm:grid-cols-2 lg:grid-cols-3';

  // ── dimensions: avg vs selected session ──
  const dimScores: Record<string, DimensionScore> =
    dimView === 'selected'
      ? selectedDetail?.dimension_scores ?? {}
      : profile.dimension_scores;
  const dimRows = DIM_ORDER.filter((d) => dimScores[d.key] != null);

  const sessionDisabled = selectedSessionId == null;

  return (
    <div className="mx-auto w-full max-w-[1120px] px-4 pb-10 pt-2">
      {/* ── 1. Hero ─────────────────────────────────────────────────────── */}
      <Card className="relative overflow-hidden rounded-2xl border border-[rgba(255,255,255,0.08)] bg-[rgba(13,18,30,0.95)] shadow-[0_8px_40px_rgba(0,0,0,0.45)]">
        {/* faint WHITE glow (dark → white, no green tint in the hero bg) */}
        <div
          className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full blur-3xl"
          style={{ background: 'rgba(255,255,255,0.05)' }}
        />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[rgba(255,255,255,0.12)] to-transparent" />

        <div
          className={[
            'relative grid gap-8 p-6 md:grid-cols-[minmax(0,1fr)_220px] md:p-8 lg:gap-12',
            isLocalOwnerProfile
              ? 'lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-8'
              : '',
          ].join(' ')}
        >
          <div className="min-w-0">
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
              <div className="flex min-w-0 items-center gap-4">
                <div
                  className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-2xl border font-mono text-xl font-bold"
                  style={{
                    color: GREEN_HEX,
                    borderColor: 'rgba(0,230,118,0.35)',
                    background: 'rgba(0,230,118,0.10)',
                  }}
                >
                  {initialsOf(profile.display_name)}
                </div>
                <div className="min-w-0 flex-1">
                  <h1 className="truncate text-2xl font-bold tracking-tight text-white md:text-3xl">
                    {profile.display_name}
                  </h1>
                  {profile.handle ? (
                    <p className="mt-1 truncate font-mono text-xs text-[var(--vibecoder-text-secondary)]">
                      vibelevel.ai/u/{profile.handle}
                    </p>
                  ) : !isPublic ? (
                    <p className="mt-1 font-mono text-xs text-[var(--vibecoder-text-secondary)]">
                      Local profile · stored on this device
                    </p>
                  ) : null}
                  {profileFacts.headline?.value && (
                    <p className="mt-1 text-sm font-medium text-[rgba(255,255,255,.76)]">
                      {profileFacts.headline.value}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex flex-col items-start gap-2 lg:items-end">
                {isLocalOwnerProfile ? (
                  <a
                    href={cfg.hostedAuraHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex max-w-full items-center justify-center gap-2 rounded-xl border border-[rgba(255,255,255,.14)] bg-[rgba(255,255,255,.04)] px-4 py-2.5 text-center text-sm font-semibold leading-snug text-white transition-colors hover:border-[rgba(0,230,118,.4)] hover:text-[var(--vibecoder-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--vibecoder-accent)]"
                  >
                    <Rocket className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
                    Import your profile to VibeLevel.ai
                  </a>
                ) : (
                  <button
                    type="button"
                    onClick={handleShare}
                    className="inline-flex w-fit items-center justify-center gap-2 rounded-xl border border-[rgba(255,255,255,.14)] bg-[rgba(255,255,255,.04)] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:border-[rgba(0,230,118,.4)] hover:text-[var(--vibecoder-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--vibecoder-accent)]"
                  >
                    {copied ? <Check className="h-4 w-4" /> : <Share2 className="h-4 w-4" />}
                    {copied ? 'Copied' : 'Share this Aura'}
                  </button>
                )}
                {profile.handle && (
                  <button
                    type="button"
                    onClick={likeProfile}
                    aria-label="Like this Aura"
                    className="group inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold text-[var(--vibecoder-text-secondary)] transition-colors hover:text-rose-400"
                  >
                    <Heart className="h-3.5 w-3.5 transition-colors group-hover:fill-rose-400 group-hover:text-rose-400" />
                    {displayLikes} {displayLikes === 1 ? 'like' : 'likes'}
                  </button>
                )}
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <span
                className="inline-flex rounded-lg px-3 py-1.5 text-sm font-semibold"
                style={{ color: GREEN_HEX, background: 'rgba(0,230,118,.1)' }}
              >
                {profile.archetype}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[.16em] text-[var(--vibecoder-text-secondary)]">
                From {profile.session_count} session{profile.session_count === 1 ? '' : 's'}
              </span>
            </div>

            {profile.archetype_tagline && (
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--vibecoder-text-secondary)] md:text-lg">
                {profile.archetype_tagline}
              </p>
            )}

            <div className="mt-5 flex flex-wrap gap-2">
              {viewingSession ? (
                <>
                  {selectedSession!.created_at && (
                    <MonoChip size="md">{formatDate(selectedSession!.created_at)}</MonoChip>
                  )}
                  {selectedSession!.source && (
                    <MonoChip size="md">{prettySource(selectedSession!.source)}</MonoChip>
                  )}
                  <MonoChip size="md">{modalityChip(selectedSession!.modality)}</MonoChip>
                  {sessionTokens > 0 && (
                    <MonoChip size="md">{formatCompact(sessionTokens)} TOKENS</MonoChip>
                  )}
                </>
              ) : (
                <>
                  <MonoChip size="md">
                    {profile.session_count} SESSION{profile.session_count === 1 ? '' : 'S'}
                  </MonoChip>
                  {primary && <MonoChip size="md">{prettySource(primary)}</MonoChip>}
                  {overallMod && <MonoChip size="md">{overallMod}</MonoChip>}
                  {typeof totalTokens === 'number' && totalTokens > 0 && (
                    <MonoChip size="md">{formatCompact(totalTokens)} TOKENS</MonoChip>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="flex flex-col items-center md:border-l md:border-[rgba(139,146,184,.14)] md:pl-8">
            <span className="font-mono text-[10px] font-semibold uppercase tracking-[.18em] text-[var(--vibecoder-text-secondary)]">
              {viewingSession ? 'Session score' : 'Avg of all sessions'}
            </span>
            <div
              className="mt-3 grid h-44 w-44 place-items-center rounded-full p-[11px] shadow-[0_0_36px_rgba(0,230,118,.12)]"
              style={{
                background: `conic-gradient(${lvlColor} ${Math.max(0, Math.min(100, heroScore * 10))}%, rgba(255,255,255,.07) 0)`,
              }}
            >
              <div className="grid h-full w-full place-items-center rounded-full border border-[rgba(255,255,255,.06)] bg-[#0a111d]">
                <div className="text-center">
                  <div className="flex items-baseline justify-center gap-1">
                    <span className="font-mono text-5xl font-bold leading-none text-white">
                      {heroScore.toFixed(1)}
                    </span>
                    <span className="font-mono text-sm text-[var(--vibecoder-text-secondary)]">
                      /10
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div
              className={[
                'mt-4 flex w-full flex-wrap items-center justify-center gap-2',
                isLocalOwnerProfile ? 'lg:flex-nowrap' : '',
              ].join(' ')}
            >
              {heroLevel && (
                <AuraGuide
                  currentLevel={heroLevel}
                  currentArchetype={profile.archetype}
                  modality={dominantModality(profile.sessions)}
                  trigger={
                    <button
                      type="button"
                      title="How levels & archetypes work"
                      className="inline-flex items-center gap-1 rounded-full border px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-wide transition-opacity hover:opacity-80"
                      style={{
                        color: lvlColor,
                        borderColor: `${lvlColor}66`,
                        background: `${lvlColor}1a`,
                      }}
                    >
                      {heroLevel}
                      <HelpCircle className="h-3 w-3 opacity-70" />
                    </button>
                  }
                />
              )}
              {showBest && (
                <div className="inline-flex items-center gap-2 rounded-xl border border-[rgba(255,255,255,.1)] bg-[rgba(255,255,255,.04)] px-3 py-1.5">
                  <span className="font-mono text-base font-bold text-white">
                    {profile.best_score!.toFixed(1)}
                  </span>
                  <span className="text-[9px] font-semibold uppercase leading-tight tracking-wide text-[var(--vibecoder-text-secondary)]">
                    Best session
                    {profile.best_level ? <><br />{profile.best_level}</> : null}
                  </span>
                </div>
              )}
              {shipsIt && (
                <span
                  title={
                    viewingSession
                      ? 'Shipped end-to-end this session'
                      : 'Consistently ships end-to-end'
                  }
                  className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wide"
                  style={{
                    color: GREEN_HEX,
                    borderColor: `${GREEN_HEX}66`,
                    background: `${GREEN_HEX}1a`,
                  }}
                >
                  <Rocket className="h-3 w-3" />
                  Ships it
                </span>
              )}
            </div>
          </div>
        </div>

        {isLocalOwnerProfile && (
          <div className="relative mx-6 mb-6 flex flex-col gap-4 rounded-2xl border border-[rgba(255,255,255,.1)] bg-[rgba(255,255,255,.035)] p-4 md:mx-8 md:flex-row md:items-center">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2.5">
              <span className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[.14em] text-[var(--vibecoder-text-secondary)]">
                <span className="h-2 w-2 rounded-sm bg-[var(--vibecoder-accent)]" />
                For hiring
              </span>
              {availability && (
                <span className="rounded-lg border border-[rgba(255,255,255,.1)] bg-[rgba(255,255,255,.04)] px-3 py-1.5 text-xs text-[var(--vibecoder-text-secondary)]">
                  {availability}
                </span>
              )}
              {location && (
                <span className="rounded-lg border border-[rgba(255,255,255,.1)] bg-[rgba(255,255,255,.04)] px-3 py-1.5 text-xs text-[var(--vibecoder-text-secondary)]">
                  {location}
                </span>
              )}
            </div>
            <a
              href={cfg.hostedAuraHref}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-full items-center justify-center whitespace-normal rounded-xl bg-[var(--vibecoder-accent)] px-4 py-2.5 text-center text-sm font-semibold leading-snug text-[#07110b] transition-colors hover:bg-[#12f287] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--vibecoder-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0d121e] md:w-auto md:max-w-sm"
            >
              Sign up on VibeLevel.ai for hiring opportunities with companies
            </a>
          </div>
        )}

        {/* Session-aware footer: only shown when viewing a specific session —
            displays its name, ID, and (if shared) the public alias. */}
        {viewingSession && (
        <div className="relative border-t border-[rgba(139,146,184,0.12)] px-6 py-3 md:px-8">
          <>
              <div className="grid grid-cols-1 gap-x-8 gap-y-1.5 sm:grid-cols-2">
                <div className="min-w-0">
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--vibecoder-text-secondary)]">
                    Session
                  </span>
                  <p className="truncate text-sm font-medium text-[var(--vibecoder-text-primary)]">
                    {selectedDetail?.title || selectedSession!.title || 'Untitled session'}
                  </p>
                </div>
                <div className="min-w-0">
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--vibecoder-text-secondary)]">
                    Session ID
                  </span>
                  <p className="truncate font-mono text-sm text-[var(--vibecoder-text-secondary)]">
                    {selectedSessionId}
                  </p>
                </div>
              </div>
              {/* Reassure the owner: a shared link shows a generic label, not the
                  real title above — so they can share without exposing their work.
                  (Hidden on the public/share view itself, where the title IS the alias.) */}
              {!isPublic && selectedSession?.share_title && (
                <div className="mt-3 flex items-start gap-2 border-t border-[rgba(139,146,184,0.08)] pt-3">
                  <EyeOff className="mt-0.5 h-4 w-4 flex-shrink-0" style={{ color: '#7dd3fc' }} />
                  <p className="text-[13px] leading-relaxed text-[var(--vibecoder-text-secondary)]">
                    When you share this session, it appears as{' '}
                    <span className="font-semibold" style={{ color: '#7dd3fc' }}>
                      &ldquo;{selectedSession.share_title}&rdquo;
                    </span>
                    . Your real title and what you worked on stay private.
                  </p>
                </div>
              )}
            </>
        </div>
        )}
      </Card>

      {isLocalOwnerProfile && (
        <>
          <AuraActivity sessions={profile.sessions} />
          <AuraToolkit profile={profile} />
          <AuraProjects projects={profile.projects ?? []} />
        </>
      )}

      {/* ── 2. Dimensions ───────────────────────────────────────────────── */}
      <section className="mt-6">
        <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-lg font-semibold text-[var(--vibecoder-text-primary)]">
            Dimensions
          </h2>
          {/* avg | selected-session toggle is owner-only (no public session
              feed). The "Average across N sessions" heading below stays. */}
          {!isPublic && (
            <Segmented<DimView>
              value={dimView}
              onChange={setDimView}
              options={[
                { value: 'avg', label: 'All sessions avg' },
                { value: 'selected', label: 'Selected session', disabled: sessionDisabled },
              ]}
            />
          )}
        </div>

        <div className="mb-4 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: GREEN_HEX }} />
          <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--vibecoder-text-secondary)]">
            {dimView === 'selected'
              ? selectedDetail?.title || selectedSession?.title || 'Selected session'
              : `Average across ${profile.session_count} session${profile.session_count === 1 ? '' : 's'}`}
          </span>
        </div>

        {detailLoading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-14 animate-pulse rounded-lg border border-[rgba(255,255,255,0.07)] bg-[rgba(14,20,33,0.85)]"
              />
            ))}
          </div>
        ) : dimRows.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {dimRows.map((d) => (
              <DimensionBar
                key={d.key}
                label={d.label}
                score={dimScores[d.key].score}
                trend={dimView === 'avg' ? profile.dimension_trends?.[d.key] : undefined}
              />
            ))}
            {/* 6th cell: Usage telemetry tile — profile-level, identical in both
                the avg and selected-session dim views (does NOT change with the
                toggle). Fills the empty grid slot beside the 5 score bars. */}
            {profile.stats && <UsageTile stats={profile.stats} />}
          </div>
        ) : (
          <Card className="rounded-xl border border-[rgba(255,255,255,0.07)] bg-[rgba(14,20,33,0.85)] p-8 text-center">
            <p className="text-sm text-[var(--vibecoder-text-secondary)]">
              {dimView === 'selected'
                ? 'No dimension scores for the selected session.'
                : 'No dimension scores yet.'}
            </p>
          </Card>
        )}
      </section>

      {!locked && !isPublic && cfg.edition === 'local' && (
        <AuraHumanEdge dimensions={dimScores} />
      )}

      {/* ── 3. Insights ─────────────────────────────────────────────────── */}
      <section className="mt-8">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-white md:text-2xl">
              Insights
            </h2>
            <p className="mt-1 text-sm text-[var(--vibecoder-text-secondary)]">
              Behavioral patterns and personality signals from scored sessions.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Segmented<Layout>
              label="Layout"
              value={layout}
              onChange={setLayout}
              options={[
                { value: 'wall', label: 'Card wall' },
                { value: 'three', label: '3-up' },
              ]}
            />
            {!isPublic && (
              <Segmented<Scope>
                label="Scope"
                value={scope}
                onChange={setScope}
                options={[
                  { value: 'overall', label: 'Overall' },
                  { value: 'session', label: 'This session', disabled: sessionDisabled },
                ]}
              />
            )}
            <Segmented<Filter>
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'all', label: 'All' },
                { value: 'credibility', label: 'Behavioral' },
                { value: 'personality', label: 'Personality' },
              ]}
            />
          </div>
        </div>

        {detailLoading ? (
          <div className={`grid gap-3 ${insightGridCols}`}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-44 animate-pulse rounded-xl border border-[rgba(255,255,255,0.07)] bg-[rgba(14,20,33,0.85)]"
              />
            ))}
          </div>
        ) : filteredCards.length > 0 ? (
          <div className={`grid gap-3 ${insightGridCols}`}>
            {filteredCards.map((c) => (
              <InsightCard key={c.id} card={c} showGrowthNudge={!isPublic} />
            ))}
          </div>
        ) : (
          <Card className="rounded-xl border border-[rgba(255,255,255,0.07)] bg-[rgba(14,20,33,0.85)] p-8 text-center">
            <p className="text-sm text-[var(--vibecoder-text-secondary)]">
              {scope === 'session'
                ? 'No insights for the selected session.'
                : 'No insights yet.'}
            </p>
          </Card>
        )}

        <p className="mt-4 font-mono text-[11px] leading-relaxed text-[var(--vibecoder-text-secondary)] opacity-80">
          Behavioral (green) = how you steer, plan &amp; verify · Personality (ice blue) =
          style &amp; habits
        </p>
      </section>

      {/* ── 4. Recent Sessions (owner) · Visitor CTA (public) ───────────── */}
      {showRecentSessions && (isPublic ? (
        /* Public view: the private session feed is hidden — show the viral
           sign-up funnel CTA in its place. */
        <section className="mt-6">
          <Card className="rounded-xl border border-[rgba(255,255,255,0.07)] bg-[rgba(14,20,33,0.85)] p-8 text-center shadow-[0_2px_8px_rgba(0,0,0,0.4)]">
            <h2 className="text-xl font-bold text-white md:text-2xl">
              Discover your AI Style from your AI Sessions
            </h2>
            <p className="mx-auto mt-2 max-w-md sm:max-w-none text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
              VibeLevel Aura scores your real AI work — Coding or Writing. See where you land.
            </p>
            <a
              href={cfg.signInHref}
              className="mt-5 inline-flex items-center justify-center rounded-lg bg-[rgba(255,255,255,0.12)] px-5 py-2.5 font-mono text-sm font-semibold text-white no-underline transition-colors hover:bg-[rgba(255,255,255,0.18)]"
            >
              {cfg.signInLabel}
            </a>
          </Card>
        </section>
      ) : (
      <section className="mt-6">
        <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-lg font-semibold text-[var(--vibecoder-text-primary)]">
            Recent Aura Sessions
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--vibecoder-text-secondary)] opacity-70">
            Click a session to sync dimensions
          </span>
        </div>

        {profile.sessions.length === 0 ? (
          <Card className="rounded-xl border border-[rgba(255,255,255,0.07)] bg-[rgba(14,20,33,0.85)] p-8 text-center">
            <p className="text-sm text-[var(--vibecoder-text-secondary)]">
              No scored sessions yet.
            </p>
          </Card>
        ) : (
          <div className="space-y-2">
            {/* Cap the feed at the 5 most recent — the "See all" link below
                opens the full list (otherwise 35+ sessions flood the page). */}
            {profile.sessions.slice(0, 5).map((s) => {
              const selected = s.id === selectedSessionId;
              const isCoding = s.modality === 'coding';
              return (
                <Card
                  key={s.id}
                  className="overflow-hidden rounded-xl border shadow-[0_2px_8px_rgba(0,0,0,0.4)] transition-colors"
                  style={{
                    borderColor: selected ? 'rgba(0,230,118,0.5)' : 'rgba(255,255,255,0.07)',
                    background: selected ? 'rgba(0,230,118,0.06)' : 'rgba(14,20,33,0.85)',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => selectSession(s.id)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[rgba(139,146,184,0.04)]"
                  >
                    <span
                      className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border"
                      style={{
                        borderColor: 'rgba(139,146,184,0.18)',
                        background: 'rgba(0,230,118,0.08)',
                      }}
                    >
                      {isCoding ? (
                        <Code className="h-4 w-4" style={{ color: GREEN_HEX }} />
                      ) : (
                        <FileText className="h-4 w-4" style={{ color: GREEN_HEX }} />
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-[var(--vibecoder-text-primary)]">
                        {s.title || 'Untitled session'}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        <MonoChip>{prettySource(s.source)}</MonoChip>
                        <MonoChip>{formatDate(s.created_at)}</MonoChip>
                        <MonoChip>{modalityChip(s.modality)}</MonoChip>
                      </div>
                    </div>
                    <span
                      className="flex-shrink-0 font-mono text-xl font-bold"
                      style={{ color: selected ? GREEN_HEX : 'var(--vibecoder-text-secondary)' }}
                    >
                      {s.aura_score.toFixed(1)}
                    </span>
                  </button>
                </Card>
              );
            })}
          </div>
        )}

        <div className="mt-4">
          <a
            href="/aura/sessions"
            className="font-mono text-sm font-medium hover:underline"
            style={{ color: GREEN_HEX }}
          >
            See all {profile.session_count} sessions →
          </a>
        </div>
      </section>
      ))}
      {!locked && !isPublic && cfg.showHostedProfilePreview && (
        <AuraPublishCta
          href={cfg.hostedAuraHref}
          label={cfg.publishProfileLabel}
        />
      )}
    </div>
  );
}
