// VibeLevel Aura — display formatting helpers for the viewer.
//
// One token-count formatter for every Aura surface (profile, sidebar, sessions,
// leaderboard) so the same number never reads two different ways. Rolls over by
// magnitude:
//   ≥ 1,000,000 → "1.2M"   ·   ≥ 1,000 → "12.4K"   ·   < 1,000 → "950"
export function formatTokens(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

// Source key → display label (the agent/tool that produced the session).
const SOURCE_LABEL: Record<string, string> = {
  claude_code: 'Claude Code',
  cursor: 'Cursor',
  codex: 'Codex',
  claude_desktop: 'Claude Desktop',
  web: 'Web',
};

// Uppercased source label for the mono chips (falls back to the raw key).
export function prettySource(src: string): string {
  return (SOURCE_LABEL[src] ?? (src || '').replace(/_/g, ' ')).toUpperCase();
}

// coding → CODING · everything else → WRITING.
export function modalityChip(modality: string): string {
  return modality === 'coding' ? 'CODING' : 'WRITING';
}

// Short "Jun 17, 2026" date for session rows (empty string on a bad value).
export function formatSessionDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Two-letter monogram from a display name (e.g. "Local Builder" → "LB").
export function initialsOf(name: string): string {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
