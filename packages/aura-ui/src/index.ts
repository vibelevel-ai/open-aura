// @vibelevel/aura-ui — public entry point.
//
// The presentational, auth-free viewer UI for Open Aura (the local-first
// edition). Originally extracted from the VibeLevel SaaS; the SaaS keeps its
// own copy. Components fetch from RELATIVE `/api/aura/*` URLs — the host app
// must provide that API.
// Import the theme once in your host app: `@vibelevel/aura-ui/styles/aura-theme.css`.

// ── Primary public surface ────────────────────────────────────────────────
export { AuraProfile } from './components/aura/aura-profile';
export { PublicAuraShell } from './components/aura/public-aura-shell';
export { AuraLeaderboard } from './components/aura/aura-leaderboard';
export { AuraRadar, type RadarDimension } from './components/aura/aura-radar';

// ── Supporting presentational components (also auth-free) ──────────────────
export { InsightCard, InsightCardGrid } from './components/aura/insight-card';
export { AuraGuide } from './components/aura/aura-guide';
export { VibeLevelLogo } from './components/vibelevel-logo';

// ── Edition config (SaaS vs OSS funnel differences) ───────────────────────
export {
  type AuraViewerConfig,
  DEFAULT_VIEWER_CONFIG,
  resolveViewerConfig,
} from './lib/aura/viewer-config';

// ── Public data types (mirror the backend Aura contracts) ──────────────────
export type {
  Modality,
  Source,
  CardScope,
  CardClass,
  Card,
  DimensionScore,
  SessionSummary,
  ScoreResult,
  ProfileResponse,
  AuraPAT,
  AuraLeaderboardEntry,
} from './lib/aura/types';
export { AURA_LEVEL_COLORS } from './lib/aura/types';

// ── Taxonomy + formatting helpers (display-only) ───────────────────────────
export {
  AURA_LEVELS,
  AURA_ARCHETYPES,
  AURA_DIMENSION_LABELS,
  dominantModality,
  type AuraLevel,
  type AuraArchetype,
} from './lib/aura/taxonomy';
export { formatTokens } from './lib/aura/format';
export {
  getCardGuide,
  SOURCE_HOW,
  type CardSource,
  type ResolvedCardGuide,
} from './lib/aura/card-guide';
