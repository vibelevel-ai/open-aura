import { AuraProfile, PublicAuraShell } from '@vibelevel/aura-ui';

// Server-side: reach the backend directly (relative URLs don't resolve on the
// server). The browser-side fetches the components make use relative /api/aura/*
// which next.config rewrites to the same backend.
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
      <PublicAuraShell>
        <div style={{ padding: '4rem 1rem', textAlign: 'center', color: 'var(--vibecoder-text-secondary)' }}>
          <h2 style={{ color: 'var(--vibecoder-text-primary)', fontSize: 22 }}>No Aura yet</h2>
          <p style={{ marginTop: 8 }}>
            Connect your agent to the Aura MCP server (<code>http://localhost:8090/mcp</code>) and ask it to
            {' '}&ldquo;score this session with Aura.&rdquo;
          </p>
        </div>
      </PublicAuraShell>
    );
  }
  return (
    <PublicAuraShell>
      <AuraProfile profile={profile} />
    </PublicAuraShell>
  );
}
