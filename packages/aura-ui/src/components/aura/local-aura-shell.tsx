// VibeLevel Aura — the local viewer's app shell.
//
// The slim branded funnel header on top + a persistent left sidebar + a
// scrollable content area. Used by Open Aura's web host for every viewer route
// (Profile · Getting Started · Leaderboard · Sessions). Server-safe wrapper; the
// sidebar (which needs the active route) is the only client piece.

import { PublicAuraHeader } from './public-aura-shell';
import { AuraSidebar, type AuraSidebarSummary } from './aura-sidebar';
import { type AuraViewerConfig } from '../../lib/aura/viewer-config';
import { type SessionSummary } from '../../lib/aura/types';

export function LocalAuraShell({
  children,
  config,
  recentSessions = [],
  summary = null,
}: {
  children: React.ReactNode;
  config?: AuraViewerConfig;
  recentSessions?: SessionSummary[];
  summary?: AuraSidebarSummary | null;
}) {
  return (
    <div className="vibecoder-ide flex h-screen flex-col overflow-hidden">
      <PublicAuraHeader config={config} />
      <div className="flex min-h-0 flex-1">
        <AuraSidebar recentSessions={recentSessions} summary={summary} />
        <main className="min-w-0 flex-1 overflow-y-auto px-4 py-4 sm:px-8 lg:px-12">
          {children}
        </main>
      </div>
    </div>
  );
}

export default LocalAuraShell;
