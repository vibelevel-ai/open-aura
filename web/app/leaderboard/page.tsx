import { AuraLeaderboard, PublicAuraShell } from '@vibelevel/aura-ui';
import { ossViewerConfig } from '../../lib/aura-config';

// Read-only pull of the public hosted leaderboard (the backend proxies it).
export const dynamic = 'force-dynamic';

export default function LeaderboardPage() {
  return (
    <PublicAuraShell config={ossViewerConfig}>
      <AuraLeaderboard limit={50} />
    </PublicAuraShell>
  );
}
