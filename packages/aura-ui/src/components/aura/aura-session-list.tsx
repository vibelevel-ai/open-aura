// VibeLevel Aura — full session list (the Sessions page).
//
// Every locally scored session as a tappable row; clicking one deep-links into
// the Profile view (`/?session={id}`), which re-scopes its dimensions + insights
// to that session. Server-safe (no hooks) — just links.

import Link from 'next/link';
import { Code, FileText } from 'lucide-react';
import { type SessionSummary } from '../../lib/aura/types';
import { prettySource, modalityChip, formatSessionDate } from '../../lib/aura/format';

const GREEN = '#00e676';

function MonoChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-[rgba(139,146,184,0.18)] bg-[rgba(139,146,184,0.06)] px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--vibecoder-text-secondary)]">
      {children}
    </span>
  );
}

export function AuraSessionList({ sessions }: { sessions: SessionSummary[] }) {
  if (sessions.length === 0) {
    return (
      <div className="rounded-xl border border-[rgba(255,255,255,0.07)] bg-[rgba(14,20,33,0.85)] p-8 text-center">
        <p className="text-sm text-[var(--vibecoder-text-secondary)]">No scored sessions yet.</p>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {sessions.map((s) => {
        const Icon = s.modality === 'coding' ? Code : FileText;
        return (
          <Link
            key={s.id}
            href={`/?session=${encodeURIComponent(s.id)}`}
            className="flex items-center gap-3 overflow-hidden rounded-xl border border-[rgba(255,255,255,0.07)] bg-[rgba(14,20,33,0.85)] px-4 py-3 no-underline shadow-[0_2px_8px_rgba(0,0,0,0.4)] transition-colors hover:bg-[rgba(139,146,184,0.04)]"
          >
            <span
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border"
              style={{ borderColor: 'rgba(139,146,184,0.18)', background: 'rgba(0,230,118,0.08)' }}
            >
              <Icon className="h-4 w-4" style={{ color: GREEN }} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-[var(--vibecoder-text-primary)]">
                {s.title || 'Untitled session'}
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <MonoChip>{prettySource(s.source)}</MonoChip>
                <MonoChip>{formatSessionDate(s.created_at)}</MonoChip>
                <MonoChip>{modalityChip(s.modality)}</MonoChip>
              </div>
            </div>
            <span
              className="flex-shrink-0 font-mono text-xl font-bold"
              style={{ color: 'var(--vibecoder-text-secondary)' }}
            >
              {s.aura_score.toFixed(1)}
            </span>
          </Link>
        );
      })}
    </div>
  );
}

export default AuraSessionList;
