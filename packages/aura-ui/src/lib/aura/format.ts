// VibeLevel Aura — shared display formatting.
//
// One token-count formatter for EVERY Aura surface (profile chip, insight card,
// dashboard, leaderboard, public pages) so the same number never reads two
// different ways. Rolls over by magnitude:
//   ≥ 1,000,000 → "1.2M"   ·   ≥ 1,000 → "12.4K"   ·   < 1,000 → "950"
export function formatTokens(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}
