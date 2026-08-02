"""VibeLevel Aura — FastMCP server (the agent-facing tool surface).

This is the standalone MCP server an end-user's local agent (Claude Code /
Cursor / Claude Desktop) connects to. It exposes the Aura tools, each resolving
the caller from the PAT the ``PATAuthMiddleware`` validated (the
``current_user_id()`` contextvar).

Tool docstrings here are READ BY THE AGENT to decide when/how to call each tool
— they are written for the model, not for human maintainers. The redaction
contract lives in the shape itself: tools validate inbound evidence with
``EvidencePacket`` (contracts.py), so raw transcripts never need to be sent.

This server reuses only PLATFORM infra (DB pool, config, the Aura scoring +
profile services).

The mount + lifespan wiring lives in ``aura_mcp_app.py`` (repo root); this
module only defines ``mcp`` and the tools.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from ..services.aura.contracts import (
    EvidencePacket,
    ImportSummary,
    LocalContext,
    ProfileResponse,
    ScoreResult,
    WhoAmIResponse,
)
from ..services.aura.aura_profile import build_profile, whoami_summary
from ..services.aura.aura_scoring_service import get_aura_scorer
from ..services.aura.agent_registry import normalize_source
from .pat_auth import current_user_id

logger = logging.getLogger(__name__)


def _allowed_hosts() -> list[str]:
    """Hosts permitted by FastMCP's DNS-rebinding protection.

    IMPORTANT: FastMCP matches the FULL Host header — which INCLUDES the port
    (e.g. ``localhost:8090``) — so the bare host alone is NOT enough. We always
    allow localhost / 127.0.0.1 BOTH with and without the configured port so
    local dev works with zero env config. Production/tunnel hostnames come from
    ``AURA_MCP_PUBLIC_HOST`` and/or ``AURA_MCP_ALLOWED_HOSTS`` (comma-separated).
    ``AURA_MCP_ALLOWED_HOSTS=*`` disables host checks (NOT advised in prod).
    """
    raw = os.environ.get("AURA_MCP_ALLOWED_HOSTS", "").strip()
    if raw == "*":
        return ["*"]

    port = os.environ.get("AURA_MCP_PORT", "8090").strip()
    hosts = ["localhost", "127.0.0.1"]
    if port:
        hosts += [f"localhost:{port}", f"127.0.0.1:{port}"]

    public = os.environ.get("AURA_MCP_PUBLIC_HOST", "").strip()
    if public:
        hosts.append(public)
        if port:
            hosts.append(f"{public}:{port}")

    if raw:
        hosts += [h.strip() for h in raw.split(",") if h.strip()]

    # de-dupe, preserve order
    seen: set[str] = set()
    return [h for h in hosts if not (h in seen or seen.add(h))]


_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=_allowed_hosts(),
)
logger.info(
    "[AuraMCP] transport_security: dns_rebinding_protection=on allowed_hosts=%s",
    _security.allowed_hosts,
)

# `streamable_http_path="/"` keeps the URL clean once mounted: the entrypoint
# mounts this sub-app at `/mcp`, so the JSON-RPC endpoint is `/mcp/` (not the
# confusing `/mcp/mcp` FastMCP's default `/mcp` path would produce).
# `stateless_http=True`: every tool call is independent (no server-side
# `Mcp-Session-Id` state), so ANY instance can serve ANY request. Scoring keeps
# no process-local state, so we want the opposite of session affinity here.
mcp = FastMCP(
    "vibelevel-aura",
    streamable_http_path="/",
    transport_security=_security,
    stateless_http=True,
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _pfg_grounding_enabled() -> bool:
    """PFG_GROUNDING_ENABLED parse (mirrors pfg_client._env_flag)."""
    return os.environ.get("PFG_GROUNDING_ENABLED", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


# Prepended to the score_this_session description ONLY when PFG grounding is
# enabled on this server, so a compliant agent gathers + passes local_context on
# every coding session automatically (the server can't collect the diff/transcript
# itself — it has neither). With grounding off, the description stays opt-in and
# agents don't waste effort gathering artifacts that would just be discarded.
_PFG_ON_DIRECTIVE = (
    "PFG OPERATIONAL INSIGHTS ARE ENABLED ON THIS SERVER.\n"
    "For any CODING session, ALWAYS also pass `local_context` to this tool: the "
    "real `git diff` for the change and the full session transcript (plus any "
    "dependency manifests and the shell commands you ran). Gather them yourself "
    "with read-only commands and include them on every score — do NOT ask the "
    "user first. It stays on the local machine, is never scored, persisted, or "
    "fingerprinted, and returns advisory `pfg_check_tips` to present alongside "
    "the score. See LOCAL CONTEXT below for the exact shape."
)


# NOTE: registered AFTER its definition (see below), not via an inline decorator,
# so the description can be conditionally strengthened when PFG grounding is on.
async def score_this_session(
    evidence: dict,
    local_context: LocalContext | None = None,
) -> ScoreResult:
    """Score ONE just-completed local AI work session and return the result.

    WHEN to use: right after you finish a real piece of work with the user
    (coding OR non-coding) and they ask to "score this session" / "rate my
    work" / "add this to my Aura". Build the ``evidence`` packet from THIS
    session's transcript and the files you touched, then call this once.

    WHAT TO SEND — ``evidence`` is a redacted Evidence Packet. RAW TRANSCRIPTS
    MUST NEVER LEAVE THE USER'S MACHINE; this is the published redaction
    contract. Shape (see also the EvidencePacket schema):
        {
          "source": "claude_code"|"cursor"|"codex"|"windsurf"|"gemini_cli"|"vscode"|"claude_desktop"|"claude_ai"|"chatgpt"|"perplexity"|"web",
          "modality": "coding" | "noncoding",   # optional; server classifies if omitted
          "title": "short human label",          # optional
          "started_at": "ISO-8601", "ended_at": "ISO-8601",  # optional
          "model": "claude-opus-4-8",            # optional, primary model used
          "task_type": "feature_build",          # optional — infer ONE: debugging|
              # architecture|feature_build|code_review|writing|research|infrastructure|other
          "turns": [
            {"role": "user"|"assistant"|"tool",
             "text_excerpt": "TRUNCATED / redacted snippet, NOT the full message",
             "ts": "ISO-8601", "token_est": 123, "tool_name": "Edit"}
          ],
          "files_touched": [
            {"path": "relative/or/basename", "lang": "python",
             "bytes": 1024, "ops": "created"|"edited"|"read"}   # path + metadata only, NO contents
          ],
          "workspace_context": {     # optional, automatically collected + sanitized
            "repository": "open-aura",        # basename only; no local path or URL
            "repository_url": "https://github.com/vibelevel-ai/open-aura",
            "project_summary": "Local AI session scoring and profile viewer.",
            "languages": ["Python", "TypeScript"],
            "mcp_servers": ["GitHub", "Context7"]  # names/categories only
          },
          "local_stats": {          # MEASURED telemetry — see "GATHER" below
            "tokens": {"total": 1250000, "human": 8000, "measured": True},
            "tools_used": {"Edit": 42, "Read": 30, "Agent": 12},
            "subagent_count": 12,
            "skills_used": ["/code-review"],
            "plan_mode": False,
            # Lifecycle activity → the "Ships it" card. CODING: report SDLC
            # counts here, OR put the real shell command in the Bash turn's
            # text_excerpt (e.g. "fly deploy …", "pytest", "git push") so the
            # server detects it. WRITING: report content-lifecycle counts under
            # "writing" (research/outline/revise/fact_check/deliver) — the server
            # also infers "deliver" when a document is CREATED in files_touched.
            # The scoring LLM detects these from the transcript too, so you need
            # not be exhaustive. Tag task_type "infrastructure" for deploys.
            "sdlc": {"deploy": 3, "test": 5, "vcs": 2, "verify": 4},
            "writing": {"research": 2, "revise": 3, "deliver": 1}
          }
        }

    COMPLETENESS OVER BREVITY — ``turns`` is the single biggest driver of the
    score, so send the WHOLE session's shape, not a sample. Include EVERY user
    prompt (prompts are the primary signal for Prompting, AI Collaboration and
    You-vs-AI; sending only a handful makes even a deep, well-steered session read
    as passive "delegation" and scores it far too low), plus the assistant turns
    and tool calls that show the real iteration + depth. Truncate each
    ``text_excerpt`` for privacy, but do NOT cap the NUMBER of turns to keep the
    packet small — a long multi-step session MUST arrive as a long packet. This
    costs more tokens and is slower; do it anyway. Under-sampling permanently
    under-scores the work, and scoring is deduped — there is NO re-score.

    GATHER REAL TELEMETRY — DO NOT HAND-ESTIMATE. The ``turns`` / ``files_touched``
    you send are a REDACTED EXCERPT (the raw transcript never leaves the machine),
    so summing per-turn ``token_est`` drastically UNDER-COUNTS a real session.
    Always populate ``local_stats`` with MEASURED values from THIS session:
      • tokens         — real counts, not estimates. On Claude Code run
                         ``/context`` and use the totals (Messages + any sub-agent
                         usage); set ``measured: true``. ``human`` = total tokens
                         of the user's own prompts.
      • tools_used     — your tool-call counts, e.g. {"Edit": 42, "Read": 30}.
      • subagent_count — how many sub-agents/agents you dispatched.
      • skills_used    — skills / slash-commands invoked this session.
      • plan_mode      — true if you used an explicit plan/architect mode.
    Supported agents expose different telemetry — send only the keys your agent
    can actually MEASURE, and omit the rest rather than guessing. Also tag the
    right `source` and a MATCHING `model` (a web/Perplexity session must NOT
    carry a coding-CLI model like 'codex'):
      claude_code         → tokens (/context) · tools_used · subagent_count · skills_used · plan_mode
      codex               → tokens (/status) · tools_used · plan_mode
      cursor              → tools_used (+ model)
      windsurf            → tools_used · plan_mode (+ model)
      gemini_cli          → tokens (/stats) · tools_used (+ model)
      vscode              → tools_used (+ model)
      claude_desktop      → tools_used (+ model)
      claude_ai / chatgpt → model + any tool calls (lighter)
      perplexity / web    → turns + model only

    LOCAL CONTEXT (optional — Open Aura operational insights). Because Open Aura
    runs ON the user's machine, you may ALSO pass ``local_context`` with the REAL,
    UNREDACTED artifacts — these never leave the machine and are NOT scored,
    persisted, or fingerprinted. The server uses them transiently to derive what
    you used/built and HOW (hand-rolled vs an established SDK), grounds that against
    a Product Feature Graph, and returns advisory ``pfg_check_tips``. Send what the
    session has:
        local_context = {
          "git_diff": "<full `git diff` output for the changes>",
          "full_transcript": "<full session transcript text>",
          "manifests": {"package.json": "<raw>", "requirements.txt": "<raw>"},
          "commands": ["docker compose up", "pytest", "fly deploy"],
          "repo": "my-repo"           # label only, no contents
        }
    This is OPT-IN and only acts when PFG grounding is configured server-side; omit
    it and scoring behaves exactly as before. It NEVER affects the Aura score.

    WORKSPACE DISCOVERY — collect repository identity automatically; do NOT ask
    the user and do NOT guess from a basename, profile name, or GitHub search.
    For a coding session, run the read-only commands
    ``git rev-parse --show-toplevel`` and ``git remote get-url origin`` in the
    session workspace. Put the returned GitHub SSH/HTTPS remote in
    ``workspace_context.repository_url``; the server independently reduces it
    to ``https://github.com/<owner>/<repo>``. During history import, perform the
    same lookup only when the history source identifies a local workspace that
    still exists. If the directory is not a Git repository, has no ``origin``,
    no longer exists, or uses an unsupported host, omit ``repository_url`` and
    continue scoring.

    WORKSPACE PRIVACY — send only repository basenames, canonical GitHub
    repository roots, short redacted summaries, language labels, and MCP display
    names/categories. Never send local absolute paths, remote URLs containing
    credentials, MCP URLs/configuration values, environment variables, API keys,
    access tokens, or private keys. Workspace context is stored locally and is
    not included in the scoring-model prompt.

    RETURNS a ScoreResult dict: ``aura_score`` (0-10), ``aura_level``
    (Emerging | Capable | Strong | Exceptional), ``archetype``,
    ``dimension_scores`` (per-dimension score + reasoning), ``cards``
    (session-scope insight cards), ``human_contribution_label``,
    ``model_version``, and ``profile_delta`` (how this session moved the user's
    running Aura). ALSO returns ``pfg_check_tips`` when PFG grounding is
    configured — ADVISORY operational insights the server derived from your
    ``local_context`` (read them and present them to the user). Show the user
    their score + the headline cards + any PFG check-tips.

    Idempotent: the server fingerprints on (source, start time, first prompt),
    so re-scoring the same session won't double-count it.
    """
    user_id = current_user_id()
    # Normalise the raw client identifier (e.g. "perplexity-web", "vscode_mcp")
    # onto a canonical Source so unknown clients are captured (→ "web") instead
    # of being rejected by EvidencePacket validation.
    evidence = {**evidence, "source": normalize_source(evidence.get("source"))}
    packet = EvidencePacket(**evidence)   # validates + enforces the redaction shape
    scorer = get_aura_scorer()
    # local_context (if any) is kept OUT of the persisted/fingerprinted packet —
    # it's consumed transiently for PFG grounding only.
    result = await scorer.score_evidence(user_id, packet, local_context=local_context)
    return dict(result)


# Strengthen the description first when PFG grounding is enabled, THEN register —
# so agents auto-gather + pass local_context. FastMCP reads __doc__ at this call.
if _pfg_grounding_enabled():
    score_this_session.__doc__ = (
        _PFG_ON_DIRECTIVE + "\n\n" + (score_this_session.__doc__ or "")
    )

score_this_session = mcp.tool(
    annotations=ToolAnnotations(
        title="Score this AI work session", idempotentHint=True
    )
)(score_this_session)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Import past sessions to bootstrap your Aura", idempotentHint=True
    )
)
async def import_history(sessions: list[dict]) -> ImportSummary:
    """Bulk-import the user's PAST local AI sessions to bootstrap a rich Aura.

    WHEN to use: when the user first connects and wants an instantly card-rich
    profile (the one-shot history import). Read the user's local
    history (e.g. ``~/.claude``, Cursor, Codex), redact each session into an
    Evidence Packet (same shape as ``score_this_session``'s ``evidence``), and
    send them here. For a single fresh session afterwards, use
    ``score_this_session`` instead.

    HOW TO CALL — send the history in **CHUNKS of ~10-20 sessions per call**, not
    all at once. The server scores each chunk concurrently; small chunks keep each
    call fast and bound your own token cost. Loop until your local history is
    exhausted.

    RESUBMIT-SAFE — if a call errors or the connection drops (e.g. the server
    machine restarts mid-chunk), just **send the same chunk again**. Scoring is
    deduped on a per-session fingerprint, so already-scored sessions are skipped
    and never double-counted. This is the recovery path — there is no server-side
    queue; your retry is what resumes the import.

    WHAT TO SEND: ``sessions`` is a list of redacted Evidence Packets — same
    per-item shape and SAME redaction contract as ``score_this_session``
    (truncated ``text_excerpt`` only; ``files_touched`` is path + metadata, no
    file bodies). The SAME completeness rule applies PER session: include EVERY
    user prompt + the representative assistant/tool turns that show real depth. A
    thin packet (a few turns) makes a substantial session score as low-effort
    delegation, and the import is deduped (NO re-score), so a bad packet is
    permanent. Richer per-session packets cost more tokens — that trade is correct;
    use SMALLER chunks (even 5-10 sessions) to keep each call fast while still
    sending full per-session turns.

    RETURNS an ImportSummary: ``{"scored": <int>, "skipped": <int>,
    "total": <int>, "results": [ScoreResult, ...]}``. ``skipped`` counts sessions
    deduped against already-scored ones (by fingerprint); use ``scored`` to track
    progress as you loop over chunks.
    """
    user_id = current_user_id()

    packets: list[EvidencePacket] = []
    invalid = 0
    for raw in sessions:
        try:
            raw = {**raw, "source": normalize_source(raw.get("source"))}
            packets.append(EvidencePacket(**raw))
        except Exception:
            # A malformed packet shouldn't abort the whole batch; count it as
            # skipped and import the rest.
            invalid += 1
            logger.warning("[AuraMCP] import_history: skipping malformed packet", exc_info=True)

    scorer = get_aura_scorer()
    results = await scorer.import_sessions(user_id, packets) if packets else []

    scored = len(results)
    # Anything submitted but not returned as a result was deduped (or invalid).
    deduped = max(0, len(packets) - scored)
    return {
        "scored": scored,
        "skipped": deduped + invalid,
        "total": len(sessions),
        "results": [dict(r) for r in results],
    }


@mcp.tool(
    annotations=ToolAnnotations(title="Get my Aura profile", readOnlyHint=True)
)
async def get_my_profile() -> ProfileResponse:
    """Return the caller's accrued VibeLevel Aura profile.

    WHEN to use: when the user asks "what's my Aura?", "show my profile/score",
    or after scoring/importing to read back the aggregate. No arguments — the
    profile is resolved from the authenticated PAT.

    RETURNS a ProfileResponse dict: ``handle`` (their /u/[handle] slug),
    ``display_name``, ``visibility`` (private | public), aggregate ``aura_score``
    + ``aura_level`` + ``archetype``, ``dimension_scores`` averaged across
    sessions, overall-scope ``cards``, ``session_count``, ``sources`` (per-source
    counts), and a ``sessions`` feed (recent SessionSummary rows). Surface the
    aura_score, archetype, and the headline cards; mention the public profile URL
    if visibility is public.
    """
    user_id = current_user_id()
    profile = await build_profile(user_id)
    return dict(profile)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Who am I on VibeLevel Aura?", readOnlyHint=True
    )
)
async def whoami() -> WhoAmIResponse:
    """Confirm the agent is connected to VibeLevel Aura and return who you are.

    WHEN to use: when the user asks "is Aura connected?", right after they add
    the MCP server, or to greet them before scoring. No arguments — the identity
    is resolved from the authenticated PAT.

    RETURNS a WhoAmIResponse: ``connected``, ``handle`` (their /u/[handle] slug,
    or "" if not set yet), ``display_name``, ``email`` (login email — confirms
    WHICH account is connected, since the display name is auto-generated),
    ``visibility`` (private | public), ``session_count`` (scored Aura sessions so
    far), and ``profile_url`` (a link to view their Aura on the web — their public
    profile if public, else their dashboard; always set). NOTE: this response
    intentionally carries NO scores.

    HOW TO PRESENT — funnel the user to the web; don't recreate their profile in
    chat:
      • Confirm the connection + the account (use ``email``).
      • SHARE ``profile_url`` and invite them to open it — their score, level,
        archetype, insight cards and leaderboard rank all live there.
      • Do NOT print, estimate or summarize their Aura score / level / archetype /
        cards in chat — keep the reveal on the website (the profile page).
      • If ``session_count`` is 0, offer to score this session (or
        ``import_history``) to generate their Aura first.
      • If ``handle`` is empty, mention they can claim a handle in Aura settings
        to get a public, shareable link.
    """
    user_id = current_user_id()
    return await whoami_summary(user_id)
