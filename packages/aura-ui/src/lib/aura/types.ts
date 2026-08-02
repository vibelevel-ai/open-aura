// VibeLevel Aura — frontend type contract.
// Mirrors the backend Aura contracts (src/services/aura/contracts.py, the source
// of truth). Keep in lockstep with that file.

export type Modality = "coding" | "noncoding";
export type Source = "claude_code" | "cursor" | "codex" | "claude_desktop" | "web";
export type CardScope = "overall" | "session";
export type CardClass = "credibility" | "personality";

export interface Card {
  id: string;
  scope: CardScope;
  klass: CardClass;
  modality: string; // coding | noncoding | universal
  question: string; // "When are you most productive?"
  headline: string; // "Night owl"
  detail: string; // "70% of your work lands 10pm-2am."
  growth_nudge?: string; // one-sentence prescriptive next step
  stat?: unknown; // raw value for badges/formatting
}

export interface DimensionScore {
  score: number; // 0-10
  reasoning?: string;
}

export interface SessionSummary {
  id: string;
  title: string;
  share_title?: string; // generic, non-revealing label shown on shared/public links
  source: string;
  modality: string;
  aura_score: number;
  aura_level?: string; // Emerging | Capable | Strong | Exceptional
  archetype: string;
  started_at?: string; // when the work actually started (from evidence); may be ""
  ended_at?: string; // when the work actually ended (from evidence); may be ""
  created_at: string; // when the session was scored (row ingested)
  ships_it?: boolean; // lifecycle card marks the work shipped/delivered end-to-end
}

export interface ScoreResult {
  session_id: string;
  aura_score: number;
  aura_level: string; // Emerging | Capable | Strong | Exceptional
  archetype: string;
  dimension_scores: Record<string, DimensionScore>;
  cards: Card[];
  human_contribution_label: string;
  model_version: string;
  profile_delta: Record<string, unknown>;
  profile_facts?: Record<string, ProfileFact>;
}

export interface ProfileFact {
  value: string;
  confidence: number;
  source: "measured" | "inferred" | string;
  observations?: number;
}

export interface ToolkitEntry {
  name: string;
  count: number;
}

export interface AuraToolkit {
  sources?: Record<string, number>;
  models?: Record<string, number>;
  tools?: ToolkitEntry[];
  skills?: ToolkitEntry[];
  mcp_servers?: ToolkitEntry[];
}

export interface AuraProject {
  name: string;
  summary?: string;
  session_count: number;
  aura_score: number;
  github_url?: string;
}

export interface ProfileResponse {
  handle: string;
  display_name: string;
  visibility: "private" | "public";
  aura_score: number;
  aura_level: string;
  best_score?: number; // highest single-session aura_score
  best_level?: string; // aura level for best_score
  archetype: string;
  archetype_tagline?: string; // short flavor line under the archetype name
  dimension_scores: Record<string, DimensionScore>; // averaged
  cards: Card[]; // overall-scope
  session_count: number;
  like_count?: number; // public count-only profile likes
  sources: Record<string, number>; // { claude_code: 31, web: 11 }
  sessions: SessionSummary[];
  // Usage telemetry (token/prompt stats) — a profile-level summary, NOT a 0-10 score.
  stats?: {
    avg_tokens_per_session?: number;
    avg_prompts_per_session?: number;
    top_model?: string;
    total_tokens?: number;
  };
  // Personal-relative benchmarks.
  benchmarks?: {
    this_session_score?: number;
    thirty_day_avg?: number;
    vs_30d_avg?: number;
    month_percentile?: number;
    best_week?: { avg: number; label: string };
  };
  // Last-N per-dimension score series for sparklines.
  dimension_trends?: Record<string, number[]>;
  // True when the user takes the majority of their sessions through to a
  // shipped/delivered outcome (drives the overall "Ships it" hero badge).
  ships_it?: boolean;
  // Evidence-weighted facts inferred from redacted session evidence.
  profile_facts?: Record<string, ProfileFact>;
  // Measured local session metadata; absent when a source cannot report it.
  toolkit?: AuraToolkit;
  // Repository-grouped evidence. Names are sanitized basenames, never paths.
  projects?: AuraProject[];
}

// Leaderboard Aura view row
export interface AuraLeaderboardEntry {
  handle: string;
  display_name: string;
  aura_score: number;
  avg_aura_score?: number;
  aura_level: string;
  archetype: string;
  rank: number;
  // Session telemetry: total scored sessions + coding/non-coding split.
  session_count?: number;
  coding_sessions?: number;
  noncoding_sessions?: number;
  // Public count-only profile likes (likeable directly from the leaderboard).
  like_count?: number;
  // Usage telemetry: total measured tokens across all scored sessions (volume).
  total_tokens?: number;
  // Primary agent/source (most-used across the user's scored sessions).
  source?: string;
  // Best session's modality (coding/non-coding icon) + whether that session was
  // shipped/delivered end-to-end (lifecycle "Ships it" badge on the board).
  modality?: string;
  ships_it?: boolean;
  // Verified assessment badge (NOT mixed into the Aura rank — display only).
  // Present when the user also has an eligible graded assessment level.
  verified_level?: string | null;
  verified_score?: number | null;
}

// Aura Score band → color (distinct from assessment LEVEL_COLORS).
// White / green / ice-blue / dark only — NO purple/violet. The top band
// (Exceptional, 8+) shifts to ice blue so it reads as "elite", not just green.
export const AURA_LEVEL_COLORS: Record<string, string> = {
  Emerging: "#6b7280",
  Capable: "#00e676",
  Strong: "#00e676",
  Exceptional: "#7dd3fc",
};

// Account / connect surfaces
export interface AuraPAT {
  id: string;
  name: string;
  prefix: string; // e.g. "aura_ab12cd"
  created_at: string;
  last_used_at?: string | null;
  revoked_at?: string | null;
}
