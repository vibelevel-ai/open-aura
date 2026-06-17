import type { Metadata } from 'next';
import { Toaster } from 'sonner';
import { LocalAuraShell } from '@vibelevel/aura-ui';
import { ossViewerConfig } from '../lib/aura-config';
// Theme tokens for the viewer components, then the host's Tailwind layer.
import '@vibelevel/aura-ui/styles/aura-theme.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'Open Aura',
  description: 'Your local AI Aura — how you work with AI, from your real sessions.',
};

// Server-side: reach the backend directly (relative URLs don't resolve on the
// server). The sidebar needs the profile summary + recent sessions, so the root
// layout fetches the profile once and feeds the shell. Pages fetch their own
// data for the content area.
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

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const profile = await getProfile();
  const summary =
    profile && profile.session_count
      ? {
          display_name: profile.display_name,
          aura_score: profile.aura_score,
          aura_level: profile.aura_level,
          archetype: profile.archetype,
          session_count: profile.session_count,
        }
      : null;
  return (
    <html lang="en">
      <body>
        <LocalAuraShell
          config={ossViewerConfig}
          summary={summary}
          recentSessions={profile?.sessions ?? []}
        >
          {children}
        </LocalAuraShell>
        <Toaster theme="dark" position="bottom-center" />
      </body>
    </html>
  );
}
