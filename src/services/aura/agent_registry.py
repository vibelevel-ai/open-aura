"""VibeLevel Aura — supported-agent registry + per-agent telemetry guidance.

The connector is consumed by many local AI agents / clients (Claude Code,
Cursor, Codex, Windsurf, Gemini CLI, Perplexity, VS Code MCP, the Claude.ai /
ChatGPT connectors, …). They expose different capabilities, so the telemetry an
agent can MEASURE — and therefore should put in ``EvidencePacket.local_stats``
— varies, as does the *kind of model* it runs. This module is the single source
of truth for:
  - which agents the connector recognises (mirrors ``contracts.Source``),
  - what each can measure (tokens / tools / subagents / skills / plan mode) and
    the command to read REAL token counts,
  - a ``model_hint`` so the agent reports a SENSIBLE model (a web/Perplexity
    session should never be tagged with a coding-CLI model like ``codex``),
  - ``normalize_source`` — maps the many raw client identifiers a connector may
    send (``"perplexity-web"``, ``"vscode_mcp"``, ``"claude.ai"`` …) onto a
    canonical ``Source`` so new clients are CAPTURED, not dropped to ``web`` or
    rejected by validation.

Pure data + string helpers, imports nothing.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Capability flags per recognised agent `source`. Keys mirror contracts.Source.
#   label         : human label shown for the agent
#   token_command : how to read REAL token usage (e.g. Claude Code `/context`)
#   tools         : exposes named tools (counts are reportable)
#   subagents     : can dispatch sub-agents (orchestration)
#   plan_mode     : has an explicit plan/architect mode
#   skills        : has skills / slash-commands
#   coding        : agent is used for real coding work (modality hint)
#   model_hint    : the kind of model this agent runs — so `model` is sensible
AGENT_CAPABILITIES: Dict[str, Dict[str, object]] = {
    # ── First-class coding agents (direct PAT, richest telemetry) ──────────────
    "claude_code": {
        "label": "Claude Code",
        "token_command": "/context",
        "tools": True, "subagents": True, "plan_mode": True, "skills": True,
        "coding": True,
        "model_hint": "claude-* (e.g. claude-opus-4-8)",
        "notes": "Run /context for real token counts (also /cost); you also know "
                 "tool calls, dispatched sub-agents, invoked skills, and whether "
                 "plan mode was used — report them, don't estimate.",
    },
    "cursor": {
        "label": "Cursor",
        "token_command": None,
        "tools": True, "subagents": False, "plan_mode": False, "skills": False,
        "coding": True,
        "model_hint": "the model you selected (claude-* / gpt-* / …)",
        "notes": "Report tool/edit counts and the selected model. No native "
                 "/context, sub-agents, or skills — omit those keys.",
    },
    "codex": {
        "label": "Codex CLI",
        "token_command": "/status",
        "tools": True, "subagents": False, "plan_mode": True, "skills": False,
        "coding": True,
        "model_hint": "gpt-* / o-series (e.g. gpt-5.1-codex)",
        "notes": "Use /status for token usage + rate limits; report tools and "
                 "plan-mode usage. No sub-agents/skills — omit those keys.",
    },
    "windsurf": {
        "label": "Windsurf",
        "token_command": None,
        "tools": True, "subagents": False, "plan_mode": True, "skills": False,
        "coding": True,
        "model_hint": "the Cascade model you selected (claude-* / gpt-* / …)",
        "notes": "Cascade is agentic — report tool calls, plan/flow usage, and "
                 "the selected model. No native token command — omit tokens "
                 "unless the UI exposes a count.",
    },
    "gemini_cli": {
        "label": "Gemini CLI",
        "token_command": "/stats",
        "tools": True, "subagents": False, "plan_mode": False, "skills": False,
        "coding": True,
        "model_hint": "gemini-* (e.g. gemini-2.5-pro)",
        "notes": "Use /stats for token usage; report tool calls and the model. "
                 "No sub-agents/skills — omit those keys.",
    },
    "vscode": {
        "label": "VS Code (MCP / Copilot)",
        "token_command": None,
        "tools": True, "subagents": False, "plan_mode": False, "skills": False,
        "coding": True,
        "model_hint": "the Copilot/MCP model in use (gpt-* / claude-* / …)",
        "notes": "Report MCP/Copilot tool calls and the model. No native token "
                 "command — omit tokens unless exposed.",
    },
    # ── Desktop / connector clients (lighter, conversational-leaning) ──────────
    "claude_desktop": {
        "label": "Claude Desktop",
        "token_command": None,
        "tools": True, "subagents": False, "plan_mode": False, "skills": False,
        "coding": False,
        "model_hint": "claude-*",
        "notes": "Report MCP tool calls and the model. Omit token/subagent/skill "
                 "keys you can't measure.",
    },
    "claude_ai": {
        "label": "Claude.ai",
        "token_command": None,
        "tools": True, "subagents": False, "plan_mode": False, "skills": False,
        "coding": False,
        "model_hint": "claude-*",
        "notes": "Connector session — report the model and any MCP tool calls. "
                 "Lighter telemetry; omit measured keys you can't read.",
    },
    "chatgpt": {
        "label": "ChatGPT",
        "token_command": None,
        "tools": True, "subagents": False, "plan_mode": False, "skills": False,
        "coding": False,
        "model_hint": "gpt-* / o-series",
        "notes": "Connector session — report the model and any tool/function "
                 "calls. Lighter telemetry; omit measured keys you can't read.",
    },
    "perplexity": {
        "label": "Perplexity",
        "token_command": None,
        "tools": False, "subagents": False, "plan_mode": False, "skills": False,
        "coding": False,
        "model_hint": "Perplexity model (sonar / gpt-* / claude-*) — NOT a coding-CLI model",
        "notes": "Answer-engine / web research — usually just turns + model. "
                 "Report the actual Perplexity model; omit measured-telemetry keys.",
    },
    "web": {
        "label": "Web / Chat",
        "token_command": None,
        "tools": False, "subagents": False, "plan_mode": False, "skills": False,
        "coding": False,
        "model_hint": "the actual chat model used",
        "notes": "Conversational only — usually just turns + model. Omit the "
                 "measured-telemetry keys.",
    },
}

SUPPORTED_SOURCES: List[str] = list(AGENT_CAPABILITIES.keys())

# Coding-capable agents — a modality HINT (content classification still wins).
CODING_SOURCES: List[str] = [s for s, c in AGENT_CAPABILITIES.items() if c.get("coding")]

# Raw client identifier → canonical Source. Lets a connector send whatever name
# it has (dashes, suffixes, brand spellings) and still land on a canonical
# source. Anything unrecognised falls through to "web" (the safe conversational
# default) in normalize_source(). Keys are matched after lower+underscore-casing.
SOURCE_ALIASES: Dict[str, str] = {
    "claudecode": "claude_code", "claude_code_cli": "claude_code", "anthropic_claude_code": "claude_code",
    "cursor_ide": "cursor", "cursor_ai": "cursor",
    "codex_cli": "codex", "openai_codex": "codex",
    "windsurf_ide": "windsurf", "windsurf_cascade": "windsurf", "cascade": "windsurf", "codeium": "windsurf",
    "gemini": "gemini_cli", "google_gemini": "gemini_cli", "gemini_code": "gemini_cli",
    "vs_code": "vscode", "vscode_mcp": "vscode", "copilot": "vscode", "github_copilot": "vscode",
    "claude_desktop_app": "claude_desktop", "anthropic_desktop": "claude_desktop",
    "claude.ai": "claude_ai", "claudeai": "claude_ai", "claude_ai_connector": "claude_ai",
    "chatgpt_connector": "chatgpt", "chat_gpt": "chatgpt", "openai_chatgpt": "chatgpt", "gpt": "chatgpt", "openai": "chatgpt",
    "perplexity_web": "perplexity", "pplx": "perplexity", "perplexity_ai": "perplexity",
    "browser": "web", "chat": "web", "unknown": "web", "other": "web",
}

# Conservative default for an unrecognised source.
_DEFAULT_CAP: Dict[str, object] = {
    "label": "Unknown agent", "token_command": None,
    "tools": True, "subagents": False, "plan_mode": False, "skills": False,
    "coding": False, "model_hint": "the actual model used",
    "notes": "Supply whatever local_stats you can actually measure.",
}


def normalize_source(raw: Optional[str]) -> str:
    """Map a raw client identifier onto a canonical ``Source``.

    Handles brand spellings / dashes / suffixes (``"Perplexity-Web"``,
    ``"vscode_mcp"``, ``"claude.ai"``). Returns a key present in
    ``AGENT_CAPABILITIES``; anything unrecognised → ``"web"`` so an unknown
    client is still captured (as conversational) rather than dropped or rejected.
    """
    if not raw:
        return "web"
    key = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
    if key in AGENT_CAPABILITIES:
        return key
    if key in SOURCE_ALIASES:
        return SOURCE_ALIASES[key]
    return "web"


def capabilities_for(source: str) -> Dict[str, object]:
    """Capability flags for a source (normalised; conservative default if odd)."""
    norm = normalize_source(source)
    return AGENT_CAPABILITIES.get(norm, {**_DEFAULT_CAP, "label": source or "Unknown agent"})


def telemetry_instructions(source: str) -> str:
    """One-line, per-agent guidance on what ``local_stats`` to MEASURE and send.

    Used by the MCP layer to tell a specific agent exactly which telemetry keys
    it should populate, how to read real token counts, and which kind of model
    to report (so a web/Perplexity session isn't mislabelled with a coding model).
    """
    cap = capabilities_for(source)
    want = ["tokens={total,human,measured:true}"]
    if cap.get("tools"):
        want.append("tools_used")
    if cap.get("subagents"):
        want.append("subagent_count")
    if cap.get("skills"):
        want.append("skills_used")
    if cap.get("plan_mode"):
        want.append("plan_mode")
    tc = cap.get("token_command")
    token_hint = f" Use `{tc}` for real token counts." if tc else " Omit tokens unless the agent exposes a real count."
    model_hint = cap.get("model_hint")
    model_str = f" Set model to {model_hint}." if model_hint else ""
    notes = str(cap.get("notes", "")).strip()
    return (
        f"{cap['label']}: send local_stats with {', '.join(want)}."
        f"{token_hint}{model_str} {notes}"
    ).strip()
