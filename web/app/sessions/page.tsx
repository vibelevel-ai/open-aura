import { AuraSessionList } from '@vibelevel/aura-ui';

// Server-side: reach the backend directly. The list links each row into the
// Profile view (`/?session={id}`), which re-scopes its dimensions + insights.
const API = process.env.INTERNAL_API_URL || 'http://localhost:8090';

async function getProfile() {
  try {
    const res = await fetch(`${API}/api/aura/me/profile`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export const dynamic = 'force-dynamic';

export default async function SessionsPage() {
  const profile = await getProfile();
  const sessions = profile?.sessions ?? [];
  return (
    <div className="mx-auto max-w-3xl py-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-[var(--vibecoder-text-primary)]">Sessions</h1>
        <span className="font-mono text-xs text-[var(--vibecoder-text-secondary)]">
          {sessions.length} scored
        </span>
      </div>
      <p className="mb-4 text-sm text-[var(--vibecoder-text-secondary)]">
        Every locally scored session. Click one to open it in your profile.
      </p>
      <AuraSessionList sessions={sessions} />
    </div>
  );
}
