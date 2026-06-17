'use client';

// VibeLevel Aura — insight card (the Paxel-style insight layer).
//
// Each card reads like a bold, collectible "trading card", not a list item.
// Anatomy (matches the v1.0 mock — a dark rounded card):
//   · top accent line — faint hairline at the card top (subtle class tint)
//   · category chip   — top-left pill: BEHAVIORAL (green) / PERSONALITY (amber)
//   · question        — small, gray, monospace ("How do you steer?")
//   · headline        — big bold WHITE answer ("Hands-on steerer")
//   · detail          — gray, relaxed one-sentence stat
//   · modality tag    — bottom-right muted pill: CODING / WRITING / BOTH
// Reusable at both the overall and per-session scope.
//
// Flip side: hover (desktop) or tap (touch) flips the card to a static guide —
// "what this measures" + "how it's populated" (from lib/aura/card-guide.ts),
// keyed by card id with a klass fallback. Guide copy only — no per-user data.
//
// Color rule (hard constraint): white / green / dark only — NO purple/violet.
//   · credibility (klass) → BEHAVIORAL → GREEN  (#00e676 / --vibecoder-accent)
//   · personality (klass) → PERSONALITY → AMBER (#f59e0b)
// Colors live in this file (not in AURA_LEVEL_COLORS, the score-band palette)
// so the two taxonomies don't get crossed.

import { useState } from 'react';
import { Info, ShieldCheck } from 'lucide-react';
import type { Card as AuraCard } from '../../lib/aura/types';
import { getCardGuide } from '../../lib/aura/card-guide';

interface KlassStyle {
  accent: string; // accent hex (top bar, chip text/border)
  chipBg: string; // category chip fill (rgba tint)
  chipBorder: string; // category chip border (rgba)
  border: string; // resting card border (rgba)
  borderHover: string; // hover card border (rgba, brighter accent)
  glow: string; // hover drop glow color (rgba)
  backBg: string; // flipped-back panel bg — soft accent tint (light intensity)
  backBorder: string; // flipped-back panel border (accent)
  label: string; // category chip label
}

// GREEN for behavioral/credibility, AMBER for personality. No purple anywhere.
const KLASS_STYLE: Record<string, KlassStyle> = {
  // Behavioral — verifiable, "serious". Green (#00e676 / --vibecoder-accent).
  credibility: {
    accent: '#00e676',
    chipBg: 'rgba(0,230,118,0.12)',
    chipBorder: 'rgba(0,230,118,0.35)',
    border: 'rgba(0,230,118,0.18)',
    borderHover: 'rgba(0,230,118,0.55)',
    glow: 'rgba(0,230,118,0.28)',
    backBg: 'linear-gradient(rgba(0,230,118,0.16), rgba(0,230,118,0.05)), rgba(15,25,21,0.98)',
    backBorder: 'rgba(0,230,118,0.40)',
    label: 'Behavioral',
  },
  // Personality — shareable/fun. Ice blue (#7dd3fc).
  personality: {
    accent: '#7dd3fc',
    chipBg: 'rgba(125,211,252,0.12)',
    chipBorder: 'rgba(125,211,252,0.35)',
    border: 'rgba(125,211,252,0.18)',
    borderHover: 'rgba(125,211,252,0.55)',
    glow: 'rgba(125,211,252,0.26)',
    backBg: 'linear-gradient(rgba(125,211,252,0.16), rgba(125,211,252,0.05)), rgba(15,23,33,0.98)',
    backBorder: 'rgba(125,211,252,0.44)',
    label: 'Personality',
  },
};

// coding → CODING · noncoding → WRITING · anything else/universal → BOTH
function modalityLabel(modality: string): string {
  if (modality === 'coding') return 'CODING';
  if (modality === 'noncoding') return 'WRITING';
  return 'BOTH';
}

// Flip-side source-badge color by guide tone. amber = estimated/approximate,
// gray = unavailable; green/blue mirror the class accents.
const TONE_HEX: Record<string, string> = {
  green: '#00e676',
  blue: '#7dd3fc',
  amber: '#f59e0b',
  gray: '#8b92b8',
};

export function InsightCard({
  card,
  showClassChip = true,
  showGrowthNudge = true,
}: {
  card: AuraCard;
  showClassChip?: boolean;
  // The "Try this →" growth nudge is personal coaching — suppressed on public /
  // shared views (someone else's profile or a shared session), shown to the owner.
  showGrowthNudge?: boolean;
}) {
  const s = KLASS_STYLE[card.klass] ?? KLASS_STYLE.credibility;
  // Flip-to-explainer: CLICK / TAP flips the card (no hover-flip — moving across
  // a grid of cards used to flip several at once, which was distracting). The
  // "info" hint still fades in on hover to signal the card is interactive.
  // prefers-reduced-motion skips the spin (motion-reduce:transition-none).
  const [flipped, setFlipped] = useState(false);
  const guide = getCardGuide(card);
  const sourceColor = TONE_HEX[guide.tone];

  const toggle = () => setFlipped((f) => !f);

  return (
    <div
      className="group relative h-full transition-transform duration-300 ease-out [perspective:1400px] hover:-translate-y-1"
      role="button"
      tabIndex={0}
      aria-label={`${card.headline}. Activate to see what this card means and how it's measured.`}
      onClick={toggle}
      onMouseLeave={() => setFlipped(false)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggle();
        }
      }}
    >
      <div
        className={`relative h-full w-full cursor-pointer transition-transform duration-500 ease-out [transform-style:preserve-3d] motion-reduce:transition-none ${
          flipped ? '[transform:rotateY(180deg)]' : ''
        }`}
      >
        {/* ───────── FRONT — stays in flow so it defines the card height ───────── */}
        <div
          className="relative flex h-full flex-col overflow-hidden rounded-2xl border bg-[rgba(14,20,33,0.7)] shadow-[0_8px_24px_-12px_rgba(0,0,0,0.7)] [backface-visibility:hidden]"
          style={{ borderColor: s.border }}
        >
          {/* Hover "pop": brighten the border in the class accent + soft glow. */}
          <span
            className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
            style={{ boxShadow: `0 16px 36px -16px ${s.glow}, inset 0 0 0 1px ${s.borderHover}` }}
          />
          {/* Top accent hairline — a subtle, low-opacity tint of the class accent. */}
          <span
            className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-40"
            style={{ background: s.accent }}
          />

          <div className="relative flex h-full flex-col p-5">
            {/* Category chip (top-left) + faint "info" flip hint (top-right). */}
            <div className="mb-4 flex items-start justify-between gap-2">
              {showClassChip ? (
                <span
                  className="inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.14em]"
                  style={{ color: s.accent, borderColor: s.chipBorder, background: s.chipBg }}
                >
                  {s.label}
                </span>
              ) : (
                <span />
              )}
              {/* Hover affordance — a pill that pops in to signal the card is
                  clickable (it flips to "how this works"). */}
              <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-[rgba(253,186,116,0.4)] bg-[rgba(253,186,116,0.12)] px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.1em] text-[#fdba74] opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                <Info className="h-3 w-3" />
                Click for details
              </span>
            </div>

            {/* Question — gray, monospace. */}
            <p className="font-mono text-[15px] leading-snug text-[var(--vibecoder-text-secondary)]">
              {card.question}
            </p>

            {/* Headline — big bold WHITE answer. The card's hero. */}
            <p className="mt-2 text-[1.6rem] font-extrabold leading-[1.1] tracking-tight text-[var(--vibecoder-text-primary)]">
              {card.headline}
            </p>

            {/* Detail — gray, relaxed one-sentence stat. */}
            {card.detail && (
              <p className="mt-2.5 text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
                {card.detail}
              </p>
            )}

            {/* Growth nudge — prescriptive next step. Owner-only; hidden on
                public/shared cards (showGrowthNudge=false). */}
            {card.growth_nudge && showGrowthNudge && (
              <div
                className="mt-3 rounded-lg border px-2.5 py-2"
                style={{ borderColor: 'rgba(0,230,118,0.25)', background: 'rgba(0,230,118,0.06)' }}
              >
                <p className="text-[12px] leading-snug text-[var(--vibecoder-text-secondary)]">
                  <span className="font-semibold" style={{ color: '#00e676' }}>Try this → </span>
                  {card.growth_nudge}
                </p>
              </div>
            )}

            {/* Bottom-right: modality tag (muted bordered pill). mt-auto pins it. */}
            <div className="mt-auto flex justify-end pt-4">
              <span className="inline-flex items-center rounded-md border border-[var(--vibecoder-border)] bg-[rgba(139,153,170,0.06)] px-1.5 py-0.5 font-mono text-[9px] font-medium uppercase tracking-[0.12em] text-[var(--vibecoder-text-secondary)]">
                {modalityLabel(card.modality)}
              </span>
            </div>
          </div>
        </div>

        {/* ───────── BACK — absolute overlay, pre-rotated; the "what / how" guide.
             Background is a soft, low-intensity tint of the card's own class
             accent (green = Behavioral, ice-blue = Personality) so a flipped
             card both stands out and signals which card it is. ───────── */}
        <div
          className="absolute inset-0 flex h-full flex-col overflow-hidden rounded-2xl border shadow-[0_10px_28px_-12px_rgba(0,0,0,0.7)] [transform:rotateY(180deg)] [backface-visibility:hidden]"
          style={{ background: s.backBg, borderColor: s.backBorder }}
        >
          <div className="relative flex h-full flex-col px-5 pb-4 pt-4">
            {/* What this measures. */}
            <div>
              <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-[rgba(206,214,236,0.72)]">
                What this measures
              </p>
              <p className="mt-1 text-[13px] leading-snug text-[var(--vibecoder-text-primary)]">
                {guide.what}
              </p>
            </div>

            {/* How it's populated — with a source badge. */}
            <div className="mt-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-[rgba(206,214,236,0.72)]">
                  How it&apos;s populated
                </p>
                <span
                  className="inline-flex items-center rounded-full border px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.1em]"
                  style={{
                    color: sourceColor,
                    borderColor: `${sourceColor}59`,
                    background: `${sourceColor}14`,
                  }}
                >
                  {guide.sourceLabel}
                </span>
              </div>
              <p className="mt-1 text-[13px] leading-snug text-[var(--vibecoder-text-secondary)]">
                {guide.how}
              </p>
            </div>

            {/* Privacy footer. */}
            <div className="mt-auto flex items-center gap-1.5 pt-2.5 text-[var(--vibecoder-text-secondary)]">
              <ShieldCheck className="h-3 w-3 flex-shrink-0" style={{ color: '#00e676' }} />
              <p className="text-[10px] leading-snug">Never your raw prompts or code.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Wall of insight cards — a responsive grid with a clean "card-wall" look.
 * 1-up on mobile → 2-up on small → 4-up on wide. Cards stay fluid at any
 * column count (the parent may wrap this for a 3-up layout). Generous gap.
 * Empty input renders nothing.
 *
 * The per-class filtering happens in the parent (aura-profile.tsx); here we
 * render whatever slice we're handed.
 */
export function InsightCardGrid({ cards }: { cards: AuraCard[] }) {
  if (!cards.length) return null;
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((c) => (
        <InsightCard key={c.id} card={c} />
      ))}
    </div>
  );
}
