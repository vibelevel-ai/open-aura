import { AuraLeaderboard } from '@vibelevel/aura-ui';
import { ossViewerConfig } from '../../lib/aura-config';

// Read-only pull of the public hosted leaderboard (the backend proxies it).
export const dynamic = 'force-dynamic';

export default function LeaderboardPage() {
  return (
    <div className="mx-auto max-w-4xl py-6">
      {/* Get-listed banner: the board is the public VibeLevel ranking — local
          sessions don't appear until you sign up + score on the hosted site. */}
      <div className="mb-5 flex flex-col items-start justify-between gap-3 rounded-xl border border-[rgba(0,230,118,0.2)] bg-[rgba(0,230,118,0.04)] px-5 py-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-semibold text-[var(--vibecoder-text-primary)]">
            Get on the leaderboard
          </p>
          <p className="mt-0.5 text-[13px] text-[var(--vibecoder-text-secondary)]">
            This is the public VibeLevel ranking. Sign up and score a session to claim a handle and get listed.
          </p>
        </div>
        <a
          href={ossViewerConfig.signInHref}
          className="inline-flex flex-shrink-0 items-center justify-center rounded-lg bg-[rgba(255,255,255,0.12)] px-4 py-2 font-mono text-[13px] font-semibold text-white no-underline transition-colors hover:bg-[rgba(255,255,255,0.18)]"
        >
          {ossViewerConfig.signInLabel}
        </a>
      </div>
      <AuraLeaderboard limit={50} />
    </div>
  );
}
