import { AuraLeaderboard, PublicAuraShell } from '@vibelevel/aura-ui';

// Read-only pull of the public hosted leaderboard (the backend proxies it).
export const dynamic = 'force-dynamic';

export default function LeaderboardPage() {
  return (
    <PublicAuraShell>
      <AuraLeaderboard limit={50} />
    </PublicAuraShell>
  );
}
