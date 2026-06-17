import { AuraProfile } from '@vibelevel/aura-ui';
import { ossViewerConfig } from '../lib/aura-config';

// Server-side: reach the backend directly (relative URLs don't resolve on the
// server). The browser-side fetches the components make use relative /api/aura/*
// which the route handler proxies to the same backend.
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

export default async function Page() {
  const profile = await getProfile();
  if (!profile || !profile.session_count) {
    return (
      <div style={{ padding: '4rem 1rem', textAlign: 'center', color: 'var(--vibecoder-text-secondary)' }}>
        <h2 style={{ color: 'var(--vibecoder-text-primary)', fontSize: 22 }}>No Aura yet</h2>
        <p style={{ marginTop: 8 }}>
          Connect your agent to the Aura MCP server (<code>http://localhost:8090/mcp</code>) and ask it to
          {' '}&ldquo;score this session with Aura.&rdquo; New here? See{' '}
          <a href="/getting-started" style={{ color: '#00e676' }}>Getting Started</a>.
        </p>
      </div>
    );
  }
  // The session feed lives in the sidebar + /sessions now, so the profile hides
  // its own bottom Recent Sessions block.
  return <AuraProfile profile={profile} config={ossViewerConfig} showRecentSessions={false} />;
}
