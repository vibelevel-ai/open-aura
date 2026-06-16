// VibeLevel Aura — shared shell for the PUBLIC, shareable Aura surfaces:
//   · /u/{handle}  — full public profile
//   · /s/{id}      — single shared session
// Both render the same slim branded funnel header + a fixed-height viewport
// where the CONTENT area scrolls (not the page), so the two share links look
// and behave identically. Plain component (no hooks) → usable from both server
// (/u) and client (/s) trees.

import Link from 'next/link';
import { VibeLevelLogo } from '../vibelevel-logo';

// Slim branded header — the viral funnel bar. Left: logo + wordmark + AURA tag.
// Center (lg+): a one-line descriptor of what Aura is. Right: green sign-up CTA.
function PublicAuraHeader() {
  return (
    <header className="relative shrink-0 border-b border-[rgba(255,255,255,0.07)] bg-[#0d1320]">
      <div className="flex h-14 items-center justify-between gap-4 px-5 md:h-16 md:px-6">
        {/* left: logo + wordmark + AURA tag */}
        <Link href="/" className="relative z-10 flex min-w-0 items-center gap-2.5 no-underline">
          <VibeLevelLogo />
          <span className="text-[20px] font-bold tracking-[-0.5px] text-[var(--vibecoder-text-primary)]">
            Vibe<em className="not-italic text-[var(--vibecoder-accent)]">Level</em>
          </span>
          <span className="hidden sm:inline-flex items-center rounded-md border border-[rgba(255,255,255,0.35)] bg-[rgba(255,255,255,0.12)] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em] text-white">
            Aura
          </span>
        </Link>

        {/* center (lg+): describe what Aura is — absolute-centered like the app header */}
        <div className="pointer-events-none absolute inset-0 hidden items-center justify-center px-44 lg:flex">
          <p className="truncate text-center text-[13px] text-[var(--vibecoder-text-secondary)]">
            <span className="font-semibold text-[var(--vibecoder-text-primary)]">Your AI Aura</span>
            {' '}— Connect your sessions and see how you work with AI — your style &amp; signature from your real work.
          </p>
        </div>

        {/* right: sign-up CTA */}
        <Link
          href="/login?persona=builder&source=aura"
          className="relative z-10 inline-flex flex-shrink-0 items-center justify-center rounded-lg border border-[rgba(255,255,255,0.35)] bg-[rgba(255,255,255,0.12)] px-4 py-2 font-mono text-[13px] font-semibold text-white no-underline transition-colors hover:bg-[rgba(255,255,255,0.18)]"
        >
          Reveal your Aura  →
        </Link>
      </div>
    </header>
  );
}

// Fixed-height viewport: slim header on top, scrollable content below. The
// content area (not the page) scrolls.
export function PublicAuraShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="vibecoder-ide flex h-screen flex-col overflow-hidden">
      <PublicAuraHeader />
      <div className="flex-1 overflow-y-auto px-4 sm:px-10 md:px-16 lg:px-24 xl:px-32">{children}</div>
    </div>
  );
}
