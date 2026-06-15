"""VibeLevel Aura — shared contracts (the single source of truth for shapes).

Every Aura component codes against THESE shapes:
  - the MCP tools validate inbound evidence with `EvidencePacket`
  - the scoring service returns `ScoreResult`
  - the REST endpoints return `ProfileResponse` / `SessionSummary`
  - the frontend mirrors these as TypeScript types (see web `lib/aura/types.ts`)

Keep this file dependency-light and stable. Changing a shape here is a
cross-cutting change — update the TS mirror in lockstep.

Independent of assessment scoring (decision #17).
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Protocol, runtime_checkable

# TypedDict must come from typing_extensions (not typing) so pydantic can build
# JSON schemas from these shapes on Python < 3.12 — the MCP tools annotate their
# returns with these TypedDicts to emit a structured-output `outputSchema`, and
# pydantic raises PydanticUserError on `typing.TypedDict` under 3.11.
from typing_extensions import TypedDict

from pydantic import BaseModel, Field

Modality = Literal["coding", "noncoding"]
# Canonical agent sources (mirrors agent_registry.AGENT_CAPABILITIES). The MCP
# layer runs agent_registry.normalize_source() to map raw client identifiers
# (e.g. "perplexity-web", "vscode_mcp", "claude.ai") onto one of these before
# validation, so an unknown client lands on "web" rather than being rejected.
Source = Literal[
    "claude_code", "cursor", "codex", "windsurf", "gemini_cli", "vscode",
    "claude_desktop", "claude_ai", "chatgpt", "perplexity", "web",
]
IngestedVia = Literal["mcp", "import"]
CardScope = Literal["overall", "session"]
CardClass = Literal["credibility", "personality"]
# Task type (spec §1.3) — the agent infers ONE from this fixed set; correlation
# insights across task types are deferred, but the tag is captured now.
TaskType = Literal[
    "debugging", "architecture", "feature_build", "code_review",
    "writing", "research", "infrastructure", "other",
]


# ===========================================================================
# INBOUND — the redacted evidence packet the agent sends. RAW never leaves the
# user's machine: excerpts are truncated, file bodies are reduced to digests.
# ===========================================================================

class Turn(BaseModel):
    role: Literal["user", "assistant", "tool"]
    text_excerpt: str = Field("", description="Truncated/redacted text; NOT the full message.")
    ts: Optional[str] = Field(None, description="ISO-8601 timestamp if available.")
    token_est: Optional[int] = None
    tool_name: Optional[str] = Field(None, description="For role='tool' or assistant tool-use.")


class FileTouched(BaseModel):
    path: str = Field(..., description="Relative path or basename; no contents.")
    lang: Optional[str] = None
    bytes: Optional[int] = None
    ops: Optional[str] = Field(None, description="e.g. 'created' | 'edited' | 'read'.")


class EvidencePacket(BaseModel):
    """What `score_this_session` / `import_history` receive per session."""
    source: Source
    modality: Optional[Modality] = Field(None, description="If omitted, server classifies.")
    title: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    model: Optional[str] = Field(None, description="Primary model used, e.g. 'claude-opus-4-8'.")
    task_type: Optional[TaskType] = Field(
        None,
        description="Task type — infer ONE from the fixed set (debugging | "
                    "architecture | feature_build | code_review | writing | "
                    "research | infrastructure | other) from the session content.",
    )
    turns: list[Turn] = Field(default_factory=list)
    files_touched: list[FileTouched] = Field(default_factory=list)
    # Local stats the agent supplies. PREFER MEASURED values here over the
    # redacted `turns` — a truncated/excerpted packet drastically under-counts
    # tokens, so token cards trust these when present. Recognised keys (all
    # optional; unknown keys ignored; never trusted for the LLM score itself):
    #   tokens: {total, human, [context_window], [subagents], [cumulative],
    #            measured}   # REAL counts, e.g. Claude Code's /context output
    #   tools_used: {"Edit": 42, "Read": 30, ...}  |  ["Edit", "Read", ...]
    #   subagent_count: int           # agents/subagents dispatched this session
    #   skills_used: ["/code-review", "deep-research", ...]
    #   plan_mode: bool               # used an explicit plan/architect mode
    local_stats: dict[str, Any] = Field(default_factory=dict)

    def fingerprint_basis(self) -> str:
        first_user = next((t.text_excerpt for t in self.turns if t.role == "user"), "")
        return f"{self.source}|{self.started_at or ''}|{first_user[:120]}"


# ===========================================================================
# OUTBOUND — what scoring produces and the API returns.
# ===========================================================================

class Card(TypedDict, total=False):
    id: str            # signal id, e.g. "time_of_day"
    scope: CardScope   # overall | session
    klass: CardClass   # credibility | personality
    modality: str      # coding | noncoding | universal
    question: str      # "When are you most productive?"
    headline: str      # "Night owl"
    detail: str        # "70% of your work lands 10pm-2am."
    growth_nudge: str  # one-sentence prescriptive next step (spec §1.1; optional)
    stat: Any          # raw value for client-side formatting/badges


class DimensionScore(TypedDict, total=False):
    score: float       # 0-10
    reasoning: str


class ScoreResult(TypedDict, total=False):
    session_id: str
    aura_score: float                       # 0-10 overall
    aura_level: str                         # Emerging | Capable | Strong | Exceptional
    archetype: str
    dimension_scores: dict[str, DimensionScore]
    cards: list[Card]                       # session-scope cards
    human_contribution_label: str
    model_version: str
    profile_delta: dict[str, Any]           # change vs the user's running profile


class SessionSummary(TypedDict, total=False):
    id: str
    title: str
    share_title: str   # generic, non-revealing label shown on PUBLIC/shared links
    source: str
    modality: str
    aura_score: float
    aura_level: str
    archetype: str
    created_at: str
    ships_it: bool   # lifecycle card marks the work shipped/delivered end-to-end


class ProfileResponse(TypedDict, total=False):
    handle: str
    display_name: str
    visibility: str                         # private | public
    aura_score: float                       # aggregate overall (avg of sessions)
    aura_level: str
    best_score: float                       # highest single-session aura_score
    best_level: str                         # aura level for best_score
    archetype: str
    archetype_tagline: str                  # evocative tagline for the assigned archetype
    dimension_scores: dict[str, DimensionScore]   # averaged across sessions
    cards: list[Card]                       # overall-scope cards
    session_count: int
    like_count: int                         # public count-only profile likes
    sources: dict[str, int]                 # {claude_code: 31, web: 11, ...}
    sessions: list[SessionSummary]
    stats: dict  # {avg_tokens_per_session, avg_prompts_per_session, top_model, total_tokens}
    benchmarks: dict  # personal-relative benchmarks (spec §1.4)
    dimension_trends: dict[str, list[float]]  # last-N per-dimension score series (spec §1.2)
    ships_it: bool  # majority of sessions taken through to a shipped/delivered outcome


class WhoAmIResponse(TypedDict, total=False):
    """`whoami` MCP tool — cheap identity/connection check (no aggregation).

    MCP-only (the web never calls it), so it has no `lib/aura/types.ts` mirror.
    """
    connected: bool
    handle: str
    display_name: str
    email: str                              # the account's login email (own identity only)
    visibility: str                         # private | public
    session_count: int                      # scored Aura sessions so far
    profile_url: str                        # web link to VIEW the Aura — public /u/<handle> if public, else the /aura dashboard. Always set (funnels to the site). NO scores in this response.


class ImportSummary(TypedDict, total=False):
    """`import_history` MCP tool result. MCP-only (no TS mirror)."""
    scored: int
    skipped: int                            # deduped (already imported) + invalid
    total: int
    results: list[ScoreResult]


# ===========================================================================
# Scoring service interface — agents that CALL scoring (MCP, REST) code against
# this Protocol, decoupled from the concrete implementation (BE-B writes it).
# ===========================================================================

@runtime_checkable
class AuraScorer(Protocol):
    async def score_evidence(
        self, user_id: str, evidence: EvidencePacket
    ) -> ScoreResult:
        """Score one session: classify modality if needed, run the referenceless
        pipeline, persist an AuraSession row, return the result + profile delta.
        Dedups on (user_id, evidence.fingerprint_basis())."""
        ...

    async def import_sessions(
        self, user_id: str, packets: list[EvidencePacket]
    ) -> list[ScoreResult]:
        """Bulk one-shot history import. Skips already-fingerprinted sessions."""
        ...
