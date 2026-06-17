// VibeLevel Aura — insight-card "guide" copy (the flip-side explainer).
//
// Each insight card can flip to a short, static "what this card means / how it's
// populated" explainer so users understand the signal. This is GUIDE COPY ONLY —
// no per-user data, no backend call. It mirrors the backend card-signal catalog
// (aura_model_coding.py / aura_model_writing.py): every card `id` has a fixed
// `klass` and `source`, and `source` is literally "how it's populated".
//
// Coding and writing share the same card ids where the meaning lines up, so one
// map covers both modalities. Any id not listed falls back to a klass-level
// blurb via getCardGuide(), so new cards still render sensible copy.

export type CardSource = "telemetry" | "score" | "llm" | "mixed";

// "How it's populated" — keyed by the card's source. The privacy promise is the
// same everywhere (raw content never leaves the machine); this describes the
// mechanism. `tone` picks the badge color (green = measured/derived, blue =
// model-inferred) within the white/green/ice-blue palette.
export const SOURCE_HOW: Record<
  CardSource,
  { label: string; how: string; tone: "green" | "blue" }
> = {
  telemetry: {
    label: "Measured",
    tone: "green",
    how: "Counts and ratios measured locally from your session — no LLM.",
  },
  score: {
    label: "From your scores",
    tone: "green",
    how: "Derived from this session's dimension scores.",
  },
  llm: {
    label: "Model-inferred",
    tone: "blue",
    how: "Inferred by the model from short, redacted excerpts.",
  },
  mixed: {
    label: "Measured + model",
    tone: "green",
    how: "From tool and command signals, plus a model read of the stages you reached.",
  },
};

interface CardGuideEntry {
  what: string; // "What this measures" — one plain sentence
  source: CardSource;
}

// id → { what it measures, how it's populated }. Shared across coding + writing.
const CARD_GUIDE: Record<string, CardGuideEntry> = {
  // ── credibility (behavioral) ──────────────────────────────────────────────
  plan_ratio: {
    source: "telemetry",
    what: "How often you scaffold or plan before building, instead of diving straight in.",
  },
  outline_ratio: {
    source: "telemetry",
    what: "How often you outline or structure a piece before you start drafting.",
  },
  redirect_rate: {
    source: "telemetry",
    what: "How often you course-correct the AI mid-task — active steering vs. accepting the first output.",
  },
  revision_habit: {
    source: "telemetry",
    what: "How much you revise and refine the work rather than shipping the first pass.",
  },
  parallel_agents: {
    source: "telemetry",
    what: "How many AI agents you orchestrate at once.",
  },
  human_token_share: {
    source: "telemetry",
    what: "How much of the work you write yourself vs. how much the AI generates.",
  },
  top_dimension: {
    source: "score",
    what: "Your strongest dimension this session, taken straight from your scores.",
  },
  growth_edge: {
    source: "llm",
    what: "The area with the most room to grow in how you work with AI.",
  },
  lifecycle: {
    source: "mixed",
    what: "How far you carry work through the lifecycle: build → test → deploy (or research → draft → deliver).",
  },
  archetype: {
    source: "score",
    what: "Your overall AI-collaboration style, summed up as one archetype.",
  },
  // ── personality (shareable) ───────────────────────────────────────────────
  token_footprint: {
    source: "telemetry",
    what: "The rough volume of tokens your session moved — just for color.",
  },
  model_mix: {
    source: "telemetry",
    what: "Which model you lean on most across your work.",
  },
  tools_used: {
    source: "telemetry",
    what: "The tools and integrations you reached for during the session.",
  },
  skills_used: {
    source: "telemetry",
    what: "The skills or commands you tapped while working.",
  },
  time_of_day: {
    source: "telemetry",
    what: "When your work tends to land during the day.",
  },
  prompt_length: {
    source: "telemetry",
    what: "How long and detailed your prompts tend to be.",
  },
  politeness: {
    source: "telemetry",
    what: "How often you thank or encourage your agent — purely for fun.",
  },
  go_to_phrase: {
    source: "llm",
    what: "The phrase you reach for most when prompting.",
  },
  signature: {
    source: "llm",
    what: "A recurring move — a recognizable habit in how you work with AI.",
  },
};

// Token usage is special: per session it can be a real measured count, an
// estimate (the source doesn't report tokens), or unavailable. The card already
// carries this as stat.provenance, so the flip-side "how" reflects the actual
// case instead of the static "Measured" telemetry blurb. amber = approximate.
const TOKEN_IDS = new Set(["token_footprint", "human_token_share"]);

const TOKEN_HOW: Record<
  string,
  { label: string; how: string; tone: "green" | "amber" | "gray" }
> = {
  measured: {
    label: "Measured",
    tone: "green",
    how: "Real counts your agent reported (e.g. Claude Code's /context) — read locally.",
  },
  estimated: {
    label: "Estimated",
    tone: "amber",
    how: "Estimated from session activity — approximate, and never used in your score.",
  },
  unavailable: {
    label: "Not available",
    tone: "gray",
    how: "This source doesn't expose token usage. The session is still scored on behavioral signals.",
  },
};

export interface ResolvedCardGuide {
  what: string;
  how: string;
  sourceLabel: string;
  tone: "green" | "blue" | "amber" | "gray";
}

// Resolve guide copy for a card: exact id match first, else a klass-level
// fallback so unknown/new ids still flip to something sensible.
export function getCardGuide(card: {
  id: string;
  klass: string;
  stat?: unknown;
}): ResolvedCardGuide {
  const entry: CardGuideEntry =
    CARD_GUIDE[card.id] ??
    (card.klass === "personality"
      ? {
          source: "telemetry",
          what: "A lighter, shareable trait about your style of working with AI.",
        }
      : {
          source: "telemetry",
          what: "A verifiable pattern in how you work with AI.",
        });

  // Token cards: surface the real per-session provenance (measured / estimated /
  // unavailable) rather than the generic "Measured" telemetry blurb.
  const prov = (card.stat as { provenance?: string } | null | undefined)
    ?.provenance;
  if (prov && TOKEN_IDS.has(card.id)) {
    const p = TOKEN_HOW[prov] ?? TOKEN_HOW.estimated;
    return { what: entry.what, how: p.how, sourceLabel: p.label, tone: p.tone };
  }

  const s = SOURCE_HOW[entry.source];
  return { what: entry.what, how: s.how, sourceLabel: s.label, tone: s.tone };
}
