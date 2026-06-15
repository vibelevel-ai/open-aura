"""VibeLevel Aura — deterministic signal & card extraction (NO LLM).

This module computes the telemetry/score cards and the archetype assignment from
an `EvidencePacket` (per session) or a collection of stored `AuraSession` rows
(overall profile). It is deterministic and cheap — the qualitative `source:'llm'`
cards (go_to_phrase, signature, growth_edge) are filled elsewhere by the scoring
service, NOT here.

Standalone (decision #17): imports only Aura contracts + the two Aura model
modules (coding / writing) for the card-signal templates and archetype catalogs.
It imports nothing from the assessment engine.

Public interface (other Aura modules import these):
    session_fingerprint(evidence)                       -> str
    classify_modality(evidence)                         -> "coding" | "noncoding"
    build_session_cards(evidence, dimension_scores, modality) -> list[Card]
    build_overall_cards(sessions, modality)             -> list[Card]
    assign_archetype(dimension_scores, telemetry, modality) -> str  # archetype NAME
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from . import aura_model_coding, aura_model_writing
from .agent_registry import CODING_SOURCES
from .contracts import Card, EvidencePacket

logger = logging.getLogger(__name__)

# Modalities mirror contracts.Modality.
MODALITY_CODING = "coding"
MODALITY_NONCODING = "noncoding"

# Sources whose work is intrinsically code-shaped (decision: source is the
# strongest signal; content/files refine the ambiguous "desktop"/"web" cases).
# Sourced from the agent registry (coding=True) so it stays in sync as agents
# are added — claude_code, cursor, codex, windsurf, gemini_cli, vscode.
_CODING_SOURCES = set(CODING_SOURCES)
_NONCODING_SOURCES = {"web"}  # claude_desktop is genuinely ambiguous → inspect

# File extensions / langs that imply coding work.
_CODE_EXTENSIONS = {
    "py", "js", "jsx", "ts", "tsx", "go", "rs", "rb", "java", "kt", "c", "h",
    "cpp", "hpp", "cc", "cs", "php", "swift", "scala", "sh", "bash", "zsh",
    "sql", "html", "css", "scss", "vue", "svelte", "dart", "lua", "r", "m",
    "json", "yaml", "yml", "toml", "ini", "xml", "gradle", "dockerfile",
}
_CODE_LANGS = {
    "python", "javascript", "typescript", "go", "rust", "ruby", "java",
    "kotlin", "c", "c++", "cpp", "csharp", "c#", "php", "swift", "scala",
    "shell", "bash", "sql", "html", "css", "vue", "svelte", "dart", "lua",
}
# Document-ish extensions that imply non-coding work.
_DOC_EXTENSIONS = {"md", "txt", "doc", "docx", "rtf", "pdf", "tex", "csv", "xlsx", "pptx", "odt"}

# Keyword heuristics (lowercased substring match on user-turn text).
_PLAN_KEYWORDS = (
    "plan", "outline", "let's start by", "first,", "step 1", "step one",
    "approach", "strategy", "break this down", "break it down", "structure",
    "before we", "high level", "high-level", "draft an outline", "roadmap",
)
_REDIRECT_KEYWORDS = (
    "no,", "not what", "instead", "actually", "wait", "that's wrong", "thats wrong",
    "don't", "do not", "stop", "redo", "rather", "try again", "let's go back",
    "go back", "revert", "undo", "not quite", "incorrect", "you misunderstood",
    "i meant", "rephrase", "change it", "fix that",
)
_REVISE_KEYWORDS = (
    "revise", "rewrite", "edit", "refine", "tighten", "polish", "proofread",
    "another draft", "redraft", "improve", "make it clearer", "shorten", "expand",
    "reword", "tone", "cut", "trim", "another pass",
)
_POLITE_KEYWORDS = ("thank", "thanks", "please", "appreciate", "cheers")


# ===========================================================================
# Fingerprint & modality
# ===========================================================================

def session_fingerprint(evidence: EvidencePacket) -> str:
    """Stable hash of `evidence.fingerprint_basis()` for idempotency/dedup.

    Import + per-session scoring both fingerprint identically so a session is
    never double-counted (spec §9.2).
    """
    basis = evidence.fingerprint_basis()
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _ext_of(path: str) -> Optional[str]:
    base = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    if base in ("dockerfile", "makefile"):
        return base
    if "." not in base:
        return None
    return base.rsplit(".", 1)[-1]


def classify_modality(evidence: EvidencePacket) -> str:
    """Classify a session as "coding" or "noncoding".

    Precedence:
      1. Explicit `evidence.modality` if the agent supplied one.
      2. Source — agent-native coding tools (claude_code/cursor/codex) → coding;
         web → noncoding.
      3. Touched-file langs/extensions — code files → coding, doc files → noncoding.
      4. Content heuristic — code-fence / code keywords in the transcript.
      5. Default → noncoding (the conservative, broader bucket).
    """
    if evidence.modality in (MODALITY_CODING, MODALITY_NONCODING):
        return evidence.modality

    src = evidence.source
    if src in _CODING_SOURCES:
        return MODALITY_CODING
    if src in _NONCODING_SOURCES:
        return MODALITY_NONCODING

    # Ambiguous source (e.g. claude_desktop) → look at the files touched.
    code_files = doc_files = 0
    for f in evidence.files_touched:
        lang = (f.lang or "").strip().lower()
        ext = _ext_of(f.path)
        if (lang and lang in _CODE_LANGS) or (ext and ext in _CODE_EXTENSIONS):
            code_files += 1
        elif (ext and ext in _DOC_EXTENSIONS):
            doc_files += 1
    if code_files or doc_files:
        return MODALITY_CODING if code_files >= doc_files else MODALITY_NONCODING

    # No file signal → inspect transcript content for code markers.
    blob = " ".join(t.text_excerpt for t in evidence.turns).lower()
    code_markers = ("```", "def ", "function ", "import ", "class ", "const ",
                    "npm ", "pip ", "git ", "() =>", "</", "console.log")
    if any(m in blob for m in code_markers):
        return MODALITY_CODING

    return MODALITY_NONCODING


# ===========================================================================
# Model module selection
# ===========================================================================

def _model_for(modality: str):
    """Return the Aura model module matching the modality."""
    return aura_model_coding if modality == MODALITY_CODING else aura_model_writing


def _card_signal_map(modality: str) -> Dict[str, Dict[str, Any]]:
    return {sig["id"]: sig for sig in _model_for(modality).get_card_signals()}


# ===========================================================================
# Telemetry computation (deterministic, no LLM)
# ===========================================================================

def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _hour_of(ts: Optional[str]) -> Optional[int]:
    """Extract the hour (0-23) from an ISO-8601 timestamp, best-effort."""
    if not ts:
        return None
    m = re.search(r"[T ](\d{2}):", ts)
    if m:
        return int(m.group(1))
    return None


_TIME_BUCKETS = [
    # (label, window-copy, predicate on hour)
    ("Early bird", "between 5am-9am", lambda h: 5 <= h < 9),
    ("Morning maker", "in the morning", lambda h: 9 <= h < 12),
    ("Afternoon builder", "in the afternoon", lambda h: 12 <= h < 17),
    ("Evening grinder", "in the evening", lambda h: 17 <= h < 22),
    ("Night owl", "between 10pm-2am", lambda h: h >= 22 or h < 2),
    ("Insomniac", "in the small hours", lambda h: 2 <= h < 5),
]


def _time_of_day(user_turns: List[Any], all_turns: List[Any]) -> Optional[Dict[str, Any]]:
    hours = [h for h in (_hour_of(t.ts) for t in all_turns) if h is not None]
    if not hours:
        return None
    counts = {label: 0 for label, _, _ in _TIME_BUCKETS}
    windows = {label: win for label, win, _ in _TIME_BUCKETS}
    for h in hours:
        for label, _win, pred in _TIME_BUCKETS:
            if pred(h):
                counts[label] += 1
                break
    top_label = max(counts, key=lambda k: counts[k])
    pct = round(100 * counts[top_label] / len(hours))
    return {"label": top_label, "window": windows[top_label], "pct": pct, "stat": {"hours": hours, "pct": pct, "label": top_label}}


def _prompt_length(user_turns: List[Any]) -> Optional[Dict[str, Any]]:
    if not user_turns:
        return None
    counts = [_word_count(t.text_excerpt) for t in user_turns]
    avg = round(sum(counts) / len(counts))
    label = "Straight to the point" if avg < 25 else "Detailed"
    return {"label": label, "n": avg, "stat": {"avg_words": avg, "label": label}}


def _politeness(user_turns: List[Any]) -> Optional[Dict[str, Any]]:
    n = 0
    for t in user_turns:
        low = (t.text_excerpt or "").lower()
        n += sum(low.count(kw) for kw in _POLITE_KEYWORDS)
    return {"n": n, "stat": {"count": n}}


def _keyword_hit(text: str, keywords) -> bool:
    low = (text or "").lower()
    return any(kw in low for kw in keywords)


def _redirect_rate(user_turns: List[Any]) -> Optional[Dict[str, Any]]:
    """User turns that correct/redirect the AI, per 10 prompts."""
    if not user_turns:
        return None
    redirects = sum(1 for t in user_turns if _keyword_hit(t.text_excerpt, _REDIRECT_KEYWORDS))
    per_ten = round(10 * redirects / len(user_turns), 1)
    return {"n": per_ten, "stat": {"redirects": redirects, "prompts": len(user_turns), "per_ten": per_ten}}


def _plan_ratio_session(user_turns: List[Any]) -> bool:
    """Did this session plan/outline before acting? Heuristic on opening turns."""
    if not user_turns:
        return False
    opening = user_turns[: max(1, min(3, len(user_turns)))]
    return any(_keyword_hit(t.text_excerpt, _PLAN_KEYWORDS) for t in opening)


def _revise_session(user_turns: List[Any]) -> bool:
    return any(_keyword_hit(t.text_excerpt, _REVISE_KEYWORDS) for t in user_turns)


def _parallel_agents(evidence: EvidencePacket) -> Optional[int]:
    """Best-effort: explicit local_stats, else distinct repo roots in files_touched."""
    stats = evidence.local_stats or {}
    for key in ("subagent_count", "subagents_dispatched", "agents_ran",
                "parallel_agents", "max_parallel_agents", "agents", "concurrent_agents"):
        if isinstance(stats.get(key), (int, float)):
            return int(stats[key])
    repos = set()
    for f in evidence.files_touched:
        path = f.path.replace("\\", "/")
        root = path.split("/", 1)[0] if "/" in path else path
        if root:
            repos.add(root)
    return len(repos) if repos else None


def _turn_tokens(turn: Any) -> int:
    """Token estimate for one turn: explicit token_est, else ~chars/4."""
    est = getattr(turn, "token_est", None)
    if isinstance(est, (int, float)) and est > 0:
        return int(est)
    return max(1, len((turn.text_excerpt or "")) // 4)


def _fmt_tokens(n: float) -> str:
    """Compact token count, rolled over by magnitude so it reads the same as the
    frontend (lib/aura/format.ts): 1_250_000 -> '1.2M', 12_400 -> '12.4K',
    950 -> '950'."""
    n = int(round(n))
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def _token_usage(turns: List[Any]) -> Dict[str, Any]:
    """Total/human token counts + human share for a set of turns (ESTIMATE from
    per-turn token_est). Used only when the agent didn't supply real counts."""
    total = sum(_turn_tokens(t) for t in turns)
    human = sum(_turn_tokens(t) for t in turns if t.role == "user")
    pct = round(100 * human / total) if total else 0
    return {"total": total, "human": human, "pct": pct}


def _real_tokens(evidence: EvidencePacket) -> Optional[Dict[str, Any]]:
    """Prefer REAL token counts the agent MEASURED (e.g. Claude Code's /context)
    over summed per-turn token_est. A truncated/redacted transcript drastically
    under-counts (the packet only carries excerpts), so when the agent supplies
    `local_stats['tokens'] = {total, human, [context_window], [subagents],
    [measured]}` we use that instead. Returns None if absent/invalid."""
    tok = (evidence.local_stats or {}).get("tokens")
    if not isinstance(tok, dict):
        return None
    total = tok.get("total")
    if not isinstance(total, (int, float)) or total <= 0:
        return None
    human = tok.get("human")
    human = int(human) if isinstance(human, (int, float)) and human >= 0 else 0
    out: Dict[str, Any] = {
        "total": int(total),
        "human": human,
        "pct": round(100 * human / total) if total else 0,
        "measured": bool(tok.get("measured", True)),
    }
    for k in ("context_window", "subagents", "cumulative"):
        v = tok.get(k)
        if isinstance(v, (int, float)) and v >= 0:
            out[k] = int(v)
    return out


def session_tokens(evidence: EvidencePacket) -> Dict[str, Any]:
    """SINGLE SOURCE OF TRUTH for a session's token usage, tagged with a
    three-tier `provenance` (spec §1.6) so the UI never shows an estimate as a
    measured fact:
      - `measured`     — the agent supplied REAL counts (local_stats['tokens']
                         from /context etc.).
      - `estimated`    — no telemetry, so derived from the redacted per-turn
                         volume (approximate; labelled; never feeds scoring).
      - `unavailable`  — nothing meaningful to even estimate from.
    Used by the session cards, overall cards, AND the profile-stats chip so they
    never disagree. `measured` (bool) is kept for back-compat == provenance=='measured'.
    """
    real = _real_tokens(evidence)
    if real:
        # Honour the agent's own measured flag: a real /context figure →
        # "measured"; an agent-computed estimate it flagged → "estimated".
        real["provenance"] = "measured" if real.get("measured") else "estimated"
        return real
    est = {**_token_usage(evidence.turns), "measured": False}
    est["provenance"] = "estimated" if est.get("total", 0) > 0 else "unavailable"
    return est


def _tools_used(evidence: EvidencePacket) -> Optional[Dict[str, Any]]:
    """Tool usage for the session. Prefer explicit `local_stats['tools_used']`
    (dict tool->count, or a flat list); fall back to counting turn `.tool_name`."""
    counts: Dict[str, int] = {}
    tu = (evidence.local_stats or {}).get("tools_used")
    if isinstance(tu, dict):
        for k, v in tu.items():
            if isinstance(v, (int, float)) and v > 0:
                counts[str(k)] = int(v)
    elif isinstance(tu, list):
        for name in tu:
            if name:
                counts[str(name)] = counts.get(str(name), 0) + 1
    if not counts:
        for t in evidence.turns:
            tn = getattr(t, "tool_name", None)
            if tn:
                counts[str(tn)] = counts.get(str(tn), 0) + 1
    if not counts:
        return None
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return {"counts": counts, "total": sum(counts.values()),
            "distinct": len(counts), "top": [name for name, _ in ordered[:3]]}


def _skills_used(evidence: EvidencePacket) -> Optional[Dict[str, Any]]:
    """Skills / slash-commands invoked, from `local_stats['skills_used']`
    (list or dict). De-duped, order preserved."""
    sk = (evidence.local_stats or {}).get("skills_used")
    raw: List[str] = []
    if isinstance(sk, list):
        raw = [str(s) for s in sk if s]
    elif isinstance(sk, dict):
        raw = [str(k) for k in sk.keys()]
    seen, uniq = set(), []
    for s in raw:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return {"skills": uniq, "count": len(uniq)} if uniq else None


def _plan_mode(evidence: EvidencePacket) -> Optional[bool]:
    """Whether the agent used an explicit plan/architect mode this session
    (real signal from `local_stats`). None when the agent didn't report it —
    callers fall back to the keyword heuristic."""
    stats = evidence.local_stats or {}
    for key in ("plan_mode", "plan_mode_used", "used_plan_mode"):
        v = stats.get(key)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v > 0
    return None


def _primary_model(evidence: EvidencePacket) -> Optional[str]:
    """Primary model for a session, normalised (None/blank → None)."""
    model = (evidence.model or "").strip()
    return model or None


def _session_telemetry(evidence: EvidencePacket, modality: str) -> Dict[str, Any]:
    """Compute all deterministic telemetry for ONE session."""
    user_turns = [t for t in evidence.turns if t.role == "user"]
    tel: Dict[str, Any] = {
        "time_of_day": _time_of_day(user_turns, evidence.turns),
        "prompt_length": _prompt_length(user_turns),
        "politeness": _politeness(user_turns),
        "redirect_rate": _redirect_rate(user_turns),
        "planned": _plan_ratio_session(user_turns),       # bool for this session
        "revised": _revise_session(user_turns),           # bool (noncoding)
        # Single source of truth: MEASURED counts when supplied, else estimate.
        "tokens": session_tokens(evidence),
        "model": _primary_model(evidence),
        "tools_used": _tools_used(evidence),
        "skills_used": _skills_used(evidence),
        "plan_mode": _plan_mode(evidence),
    }
    if modality == MODALITY_CODING:
        tel["parallel_agents"] = _parallel_agents(evidence)
    return tel


# ===========================================================================
# Card construction
# ===========================================================================

def _card(sig: Dict[str, Any], scope: str, modality: str, headline: str,
          detail: str, stat: Any) -> Card:
    """Build a Card from a card-signal template entry."""
    card: Card = {
        "id": sig["id"],
        "scope": scope,
        "klass": sig["klass"],
        "modality": modality,
        "question": sig.get("question", ""),
        "headline": headline,
        "detail": detail,
        "stat": stat,
    }
    return card


def _fmt(sig: Dict[str, Any], **kwargs) -> str:
    """Render a card-signal template, tolerating missing placeholders."""
    template = sig.get("template", "")
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        logger.warning("[aura] card template %s missing fmt args %s", sig.get("id"), kwargs)
        return template


# ── Lifecycle detector ("Ships it" card) ─────────────────────────────────────
# Deterministic FLOOR for the lifecycle card. Coding = SDLC (build/test/deploy/
# verify/ci/infra); writing = content lifecycle (research/outline/revise/
# fact_check/deliver). Classified from the redacted turn excerpts, tool names and
# file paths — a BEHAVIORAL signal, NOT the agent self-grading. The scoring LLM
# detects nuanced cases on top (union, see build_session_cards `llm_lifecycle`),
# and the agent may report exact counts in local_stats['sdlc'|'writing'].
_SDLC_PATTERNS: Dict[str, List[str]] = {
    "deploy": [r"fly(?:ctl)?\s+deploy", r"vercel\s+(?:deploy|--prod)", r"kubectl\s+apply",
               r"docker\s+push", r"terraform\s+apply", r"netlify\s+deploy",
               r"serverless\s+deploy", r"gcloud\s+\w+\s+deploy", r"npm\s+run\s+deploy",
               r"\bdeployed?\b"],
    "test": [r"\bpytest\b", r"\bjest\b", r"npm\s+(?:run\s+)?test", r"yarn\s+test",
             r"go\s+test", r"cargo\s+test", r"\bvitest\b", r"py_compile",
             r"tsc\b[^\n]*--noemit", r"\bphpunit\b", r"\bran the tests?\b"],
    "vcs": [r"git\s+push", r"git\s+commit", r"gh\s+pr\s+create", r"\bpushed\b"],
    "verify": [r"fly\s+(?:logs|status|ssh)", r"vercel\s+(?:logs|inspect)",
               r"kubectl\s+logs", r"curl\s+[^\n]*(?:health|/api|https?)", r"health\s*-?check"],
    "ci": [r"\.github/workflows", r"gh\s+workflow", r"circleci", r"gitlab-ci", r"\bci/cd\b"],
    "infra": [r"\bdockerfile\b", r"docker-compose", r"\.tf\b", r"\bterraform\b",
              r"fly\.[\w.-]*toml", r"\bkubernetes\b", r"\bk8s\b"],
}
_WRITING_PATTERNS: Dict[str, List[str]] = {
    "research": [r"\bresearch", r"\bsources?\b", r"\bcit(?:e|ed|ation)", r"\breferenc",
                 r"\blooked? up\b", r"\bweb ?search", r"\bstud(?:y|ies)\b", r"\bsurvey\b"],
    "outline": [r"\boutlin", r"\bstructur", r"\bsections?\b", r"\bheadings?\b",
                r"\btable of contents\b", r"\btoc\b"],
    "revise": [r"\brevis", r"\bedit(?:ed|ing)?\b", r"\brewr(?:ite|ote)", r"\btighten",
               r"\btrim(?:med)?\b", r"\bredraft", r"\bpolish", r"\bproofread"],
    "fact_check": [r"\bfact[- ]?check", r"\bverif(?:y|ied|ication)", r"\bcitation",
                   r"\baccuracy", r"\bconfirm(?:ed)?\b"],
    "deliver": [r"\bfinaliz", r"\bpublish", r"\bexport", r"\bdeck\b", r"\bship",
                r"created? (?:the )?(?:doc|document|file|draft|post)"],
}
_LIFECYCLE: Dict[str, Dict[str, Any]] = {
    "coding": {
        "patterns": _SDLC_PATTERNS,
        "order": ["deploy", "test", "vcs", "verify", "ci", "infra"],
        "ship": "deploy",
        "reported_key": "sdlc",
        "labels": {"deploy": "deployed", "test": "ran tests", "vcs": "committed & pushed",
                   "verify": "verified", "ci": "CI / workflow", "infra": "infra / IaC"},
        "heads": {"deploy": "Ships it", "test": "Runs the tests", "vcs": "Commits & pushes",
                  "verify": "Verifies the work", "ci": "Works the pipeline", "infra": "Works the pipeline"},
    },
    "noncoding": {
        "patterns": _WRITING_PATTERNS,
        "order": ["deliver", "research", "outline", "revise", "fact_check"],
        "ship": "deliver",
        "reported_key": "writing",
        "labels": {"deliver": "delivered", "research": "researched", "outline": "outlined",
                   "revise": "revised", "fact_check": "fact-checked"},
        "heads": {"deliver": "Ships it", "research": "Researches deeply", "outline": "Outlines first",
                  "revise": "Drafts & revises", "fact_check": "Fact-checks"},
    },
}
# Document artifacts whose CREATION is the writing "deliver" signal (email demoted).
_DOC_RE = re.compile(r"\.(md|markdown|docx?|pdf|txt|rtf|tex|pptx?|key)$", re.IGNORECASE)


def _lifecycle_activity(
    evidence: EvidencePacket, modality: str, llm_lifecycle: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """Detect the session's lifecycle stages → a "Ships it" card payload (or None).
    Deterministic floor (commands/files/reported) ∪ the scoring LLM's stages."""
    cfg = _LIFECYCLE["coding" if modality == MODALITY_CODING else "noncoding"]
    patterns: Dict[str, List[str]] = cfg["patterns"]

    parts: List[str] = []
    for t in evidence.turns:
        if t.text_excerpt:
            parts.append(t.text_excerpt)
        if getattr(t, "tool_name", None):
            parts.append(t.tool_name or "")
    for ft in evidence.files_touched:
        if getattr(ft, "path", None):
            parts.append(ft.path or "")
    corpus = " \n ".join(parts).lower()

    buckets: Dict[str, int] = {}
    for name, pats in patterns.items():
        n = sum(len(re.findall(p, corpus, re.IGNORECASE)) for p in pats)
        if n:
            buckets[name] = n

    # Writing "deliver" = a document was CREATED (the hardest deliver signal).
    if modality != MODALITY_CODING:
        for ft in evidence.files_touched:
            path = getattr(ft, "path", "") or ""
            ops = getattr(ft, "ops", "") or ""
            if _DOC_RE.search(path) and ops in ("created", "edited", ""):
                buckets["deliver"] = max(buckets.get("deliver", 0), 1)
                break

    # Agent-reported exact counts (measured) win per bucket.
    reported = (evidence.local_stats or {}).get(cfg["reported_key"])
    if isinstance(reported, dict):
        for k, v in reported.items():
            if k in patterns and isinstance(v, (int, float)) and v > 0:
                buckets[k] = int(v)

    # Scoring LLM's detected stages (robust to phrasing) — union, floor of 1.
    if llm_lifecycle:
        for s in llm_lifecycle:
            if isinstance(s, str) and s in patterns:
                buckets[s] = max(buckets.get(s, 0), 1)

    if not buckets:
        return None

    active = [b for b in cfg["order"] if b in buckets]
    ships_it = cfg["ship"] in buckets
    head = cfg["heads"].get(active[0], "Ships it") if active else "Ships it"
    detail = "Lifecycle this session — " + " · ".join(cfg["labels"][b] for b in active) + "."
    return {"headline": head, "detail": detail,
            "stat": {"buckets": buckets, "categories": active, "ships_it": ships_it}}


def _attach_growth_nudges(
    cards: List[Card], tel: Dict[str, Any], dims: Dict[str, Any]
) -> None:
    """Attach a one-sentence prescriptive `growth_nudge` to matching session
    cards from deterministic thresholds (spec §1.1). No LLM, no aggregation."""
    by_id = {c["id"]: c for c in cards}

    def _score(key: str) -> float:
        try:
            return float((dims.get(key) or {}).get("score", 10) or 10)
        except (TypeError, ValueError):
            return 10.0

    # Prompt length: terse prompts + a weak prompting score.
    pl = tel.get("prompt_length") or {}
    c = by_id.get("prompt_length")
    if c and pl.get("n", 99) < 15 and _score("prompting") < 6:
        c["growth_nudge"] = (
            "Short prompts plus a low Prompting score — add one sentence of task "
            "context (goal, constraints, desired output) when you start a session."
        )

    # Redirect rate: lots of mid-session corrections → reframe; else low AI-pairing.
    rr = tel.get("redirect_rate") or {}
    try:
        per_ten = float(rr.get("n", 0) or 0)
    except (TypeError, ValueError):
        per_ten = 0.0
    c = by_id.get("redirect_rate")
    if c and per_ten > 1.5:
        c["growth_nudge"] = (
            "High redirects suggest unclear initial framing — state the desired "
            "output format and constraints upfront."
        )
    elif c and "growth_nudge" not in c and _score("ai_pairing") < 5.5:
        c["growth_nudge"] = (
            "You're accepting AI output without much iteration — push back, ask "
            "for alternatives, and compare approaches."
        )

    # Plan/outline: dove straight in.
    planned = tel.get("plan_mode")
    if planned is None:
        planned = tel.get("planned")
    c = by_id.get("plan_ratio") or by_id.get("outline_ratio")
    if c and not planned:
        c["growth_nudge"] = (
            "Try plan-mode on your next architecture or multi-step task — planning "
            "first tends to lift output quality."
        )

    # Human token share: only when MEASURED + genuinely low (little tool activity).
    tok = tel.get("tokens") or {}
    tools_tel = tel.get("tools_used") or {}
    tool_total = tools_tel.get("total", 0) if isinstance(tools_tel, dict) else 0
    c = by_id.get("human_token_share")
    if (c and tok.get("provenance") == "measured"
            and tok.get("pct", 100) < 3 and tool_total < 5):
        c["growth_nudge"] = (
            "Low contribution with little hands-on steering this session — try "
            "driving more of the reasoning yourself."
        )


def build_session_cards(
    evidence: EvidencePacket,
    dimension_scores: Dict[str, Any],
    modality: str,
    llm_lifecycle: Optional[List[str]] = None,
) -> List[Card]:
    """Telemetry + score cards for ONE session (scope='session').

    Only emits cards whose card-signal `scope` includes session ("session"/"both")
    and whose `source` is deterministic ('telemetry' or 'score'). LLM-sourced
    cards (go_to_phrase, signature, growth_edge) are filled by the scoring service.
    """
    sigs = _card_signal_map(modality)
    tel = _session_telemetry(evidence, modality)
    cards: List[Card] = []

    def _scoped(sig: Dict[str, Any]) -> bool:
        return sig.get("scope") in ("session", "both")

    # ---- telemetry cards ----
    tod = tel.get("time_of_day")
    if tod and "time_of_day" in sigs and _scoped(sigs["time_of_day"]):
        sig = sigs["time_of_day"]
        cards.append(_card(sig, "session", modality,
                           headline=tod["label"],
                           detail=_fmt(sig, label=tod["label"], pct=tod["pct"], window=tod["window"]),
                           stat=tod["stat"]))

    pl = tel.get("prompt_length")
    if pl and "prompt_length" in sigs and _scoped(sigs["prompt_length"]):
        sig = sigs["prompt_length"]
        cards.append(_card(sig, "session", modality,
                           headline=pl["label"],
                           detail=_fmt(sig, label=pl["label"], n=pl["n"]),
                           stat=pl["stat"]))

    pol = tel.get("politeness")
    if pol and "politeness" in sigs and _scoped(sigs["politeness"]):
        sig = sigs["politeness"]
        cards.append(_card(sig, "session", modality,
                           headline="Polite" if pol["n"] else "All business",
                           detail=_fmt(sig, n=pol["n"]),
                           stat=pol["stat"]))

    rr = tel.get("redirect_rate")
    if rr and "redirect_rate" in sigs and _scoped(sigs["redirect_rate"]):
        sig = sigs["redirect_rate"]
        cards.append(_card(sig, "session", modality,
                           headline="Hands-on steerer",
                           detail=_fmt(sig, n=rr["n"]),
                           stat=rr["stat"]))

    # plan/outline ratio — single session is binary (0% or 100%).
    plan_id = "plan_ratio" if modality == MODALITY_CODING else "outline_ratio"
    if plan_id in sigs and _scoped(sigs[plan_id]):
        sig = sigs[plan_id]
        # Prefer the real plan/architect-mode signal; fall back to the keyword
        # heuristic on opening turns when the agent didn't report it.
        planned = tel.get("plan_mode")
        if planned is None:
            planned = tel.get("planned")
        pct = 100 if planned else 0
        cards.append(_card(sig, "session", modality,
                           headline="Planned first" if planned else "Dove right in",
                           detail=_fmt(sig, pct=pct),
                           stat={"pct": pct, "planned": bool(planned),
                                 "measured": tel.get("plan_mode") is not None}))

    # revise (noncoding) habit — binary for one session. Coding's verify habit
    # was dropped in the lighter v1.0 model.
    if modality != MODALITY_CODING:
        habit_id, did = "revision_habit", tel.get("revised")
        head_yes, head_no = "Revised", "First draft shipped"
        if habit_id in sigs and _scoped(sigs[habit_id]):
            sig = sigs[habit_id]
            pct = 100 if did else 0
            cards.append(_card(sig, "session", modality,
                               headline=head_yes if did else head_no,
                               detail=_fmt(sig, pct=pct),
                               stat={"pct": pct, "did": bool(did)}))

    # ---- token-usage cards (provenance-aware — spec §1.6) ----
    tok = tel.get("tokens") or {}
    prov = tok.get("provenance", "measured" if tok.get("measured") else "estimated")
    if "token_footprint" in sigs and _scoped(sigs["token_footprint"]):
        sig = sigs["token_footprint"]
        total = tok.get("total", 0)
        tok_str = _fmt_tokens(total)
        if prov == "measured":
            head, det = f"{tok_str} tokens", _fmt(sig, tokens=tok_str, per="this session")
        elif prov == "estimated":
            head = f"~{tok_str} est."
            det = ("Estimated from session activity — this source doesn't report "
                   "token usage. Approximate; not used in your score.")
        else:
            head = "N/A"
            det = ("Token usage isn't available for this source. The session is "
                   "still scored on behavioral signals.")
        cards.append(_card(sig, "session", modality, headline=head, detail=det,
                           stat={"tokens": total, "measured": prov == "measured", "provenance": prov}))

    if "human_token_share" in sigs and _scoped(sigs["human_token_share"]):
        sig = sigs["human_token_share"]
        pct = tok.get("pct", 0)
        if prov == "measured":
            head, det = f"{pct}% you", _fmt(sig, pct=pct)
        elif prov == "estimated":
            head = f"~{pct}% est."
            det = ("Estimated share — this source doesn't report token usage. "
                   "Approximate; not used in your score.")
        else:
            head = "N/A"
            det = "Token usage isn't available for this source."
        cards.append(_card(sig, "session", modality, headline=head, detail=det,
                           stat={"pct": pct, "human": tok.get("human", 0), "total": tok.get("total", 0),
                                 "measured": prov == "measured", "provenance": prov}))

    # ---- tooling / orchestration cards (real telemetry the agent supplies) ----
    tools = tel.get("tools_used")
    if tools and "tools_used" in sigs and _scoped(sigs["tools_used"]):
        sig = sigs["tools_used"]
        cards.append(_card(sig, "session", modality,
                           headline=f"{tools['distinct']} tools",
                           detail=_fmt(sig, distinct=tools["distinct"], n=tools["total"], top=", ".join(tools["top"])),
                           stat=tools))

    skills = tel.get("skills_used")
    if skills and "skills_used" in sigs and _scoped(sigs["skills_used"]):
        sig = sigs["skills_used"]
        cards.append(_card(sig, "session", modality,
                           headline=f"{skills['count']} skill{'' if skills['count'] == 1 else 's'}",
                           detail=_fmt(sig, n=skills["count"], top=", ".join(skills["skills"][:3])),
                           stat=skills))

    agents = tel.get("parallel_agents")
    if isinstance(agents, (int, float)) and agents > 1 and "parallel_agents" in sigs and _scoped(sigs["parallel_agents"]):
        sig = sigs["parallel_agents"]
        cards.append(_card(sig, "session", modality,
                           headline=f"{int(agents)} agents",
                           detail=_fmt(sig, n=int(agents)),
                           stat={"agents": int(agents)}))

    # ---- Lifecycle / "Ships it" card (coding: SDLC; writing: content lifecycle) ----
    life = _lifecycle_activity(evidence, modality, llm_lifecycle)
    if life:
        q = "Do you ship it?" if modality == MODALITY_CODING else "Do you take it all the way?"
        sig = {"id": "lifecycle", "klass": "credibility", "question": q}
        cards.append(_card(sig, "session", modality,
                           headline=life["headline"], detail=life["detail"],
                           stat=life["stat"]))

    # model_mix is overall-only (scope), so it is NOT emitted per session.

    # ---- score cards ----
    top = _top_dimension(dimension_scores, modality)
    if top and "top_dimension" in sigs and _scoped(sigs["top_dimension"]):
        sig = sigs["top_dimension"]
        cards.append(_card(sig, "session", modality,
                           headline=top["name"],
                           detail=_fmt(sig, dim=top["name"], score=top["score"]),
                           stat={"dimension": top["key"], "score": top["score"]}))

    # ---- growth nudges (deterministic next-step recs; spec §1.1) ----
    _attach_growth_nudges(cards, tel, dimension_scores)

    return cards


def build_overall_cards(sessions: List[Dict[str, Any]], modality: str) -> List[Card]:
    """Aggregate telemetry cards across many AuraSession rows (scope='overall').

    Each `sessions` entry is dict-like with `.evidence` (an EvidencePacket or a
    dict coercible to one) and `.dimension_scores` (dict). Cards whose scope is
    "overall"/"both" and source is deterministic are emitted.
    """
    sigs = _card_signal_map(modality)
    cards: List[Card] = []
    if not sessions:
        return cards

    evidences: List[EvidencePacket] = []
    dim_score_rows: List[Dict[str, Any]] = []
    for s in sessions:
        ev = _coerce_evidence(_get(s, "evidence"))
        if ev is not None:
            evidences.append(ev)
        dim_score_rows.append(_get(s, "dimension_scores") or {})

    if not evidences:
        return cards

    all_user_turns = [t for ev in evidences for t in ev.turns if t.role == "user"]
    all_turns = [t for ev in evidences for t in ev.turns]

    def _scoped(sig: Dict[str, Any]) -> bool:
        return sig.get("scope") in ("overall", "both")

    # ---- archetype card (emitted FIRST; not a card_signals entry) ----
    # The headline IS the archetype; the detail is its evocative tagline. This is
    # the hero card of the overall profile, so it leads the deck.
    avg_for_archetype = _average_dimension_scores(dim_score_rows)
    # HC-driven assignment ignores telemetry; pass {} (signature kept for callers).
    archetype_name = assign_archetype(avg_for_archetype, {}, modality)
    if archetype_name:
        n = len(evidences)
        tagline = _archetype_tagline(modality, archetype_name)
        detail = f"{tagline} across {n} session{'s' if n != 1 else ''}"
        cards.append({
            "id": "archetype",
            "scope": "overall",
            "klass": "credibility",
            "modality": modality,
            "question": "Which archetype are you?",
            "headline": archetype_name,
            "detail": detail,
            "stat": {"archetype": archetype_name, "sessions": n},
        })

    # time_of_day — across all turns.
    tod = _time_of_day(all_user_turns, all_turns)
    if tod and "time_of_day" in sigs and _scoped(sigs["time_of_day"]):
        sig = sigs["time_of_day"]
        cards.append(_card(sig, "overall", modality,
                           headline=tod["label"],
                           detail=_fmt(sig, label=tod["label"], pct=tod["pct"], window=tod["window"]),
                           stat=tod["stat"]))

    # prompt_length — averaged across all user turns.
    pl = _prompt_length(all_user_turns)
    if pl and "prompt_length" in sigs and _scoped(sigs["prompt_length"]):
        sig = sigs["prompt_length"]
        cards.append(_card(sig, "overall", modality,
                           headline=pl["label"],
                           detail=_fmt(sig, label=pl["label"], n=pl["n"]),
                           stat=pl["stat"]))

    # politeness — total across sessions.
    pol = _politeness(all_user_turns)
    if pol and "politeness" in sigs and _scoped(sigs["politeness"]):
        sig = sigs["politeness"]
        cards.append(_card(sig, "overall", modality,
                           headline="Polite" if pol["n"] else "All business",
                           detail=_fmt(sig, n=pol["n"]),
                           stat=pol["stat"]))

    # redirect_rate — pooled across all user turns.
    rr = _redirect_rate(all_user_turns)
    if rr and "redirect_rate" in sigs and _scoped(sigs["redirect_rate"]):
        sig = sigs["redirect_rate"]
        cards.append(_card(sig, "overall", modality,
                           headline="Hands-on steerer",
                           detail=_fmt(sig, n=rr["n"]),
                           stat=rr["stat"]))

    # plan/outline ratio — share of SESSIONS that planned.
    plan_id = "plan_ratio" if modality == MODALITY_CODING else "outline_ratio"
    if plan_id in sigs and _scoped(sigs[plan_id]):
        sig = sigs[plan_id]

        def _ev_planned(ev: EvidencePacket) -> bool:
            pm = _plan_mode(ev)
            return pm if pm is not None else _plan_ratio_session([t for t in ev.turns if t.role == "user"])

        planned = sum(1 for ev in evidences if _ev_planned(ev))
        pct = round(100 * planned / len(evidences))
        cards.append(_card(sig, "overall", modality,
                           headline=f"{pct}% plan-first",
                           detail=_fmt(sig, pct=pct),
                           stat={"pct": pct, "sessions": len(evidences), "planned": planned}))

    # revise habit — share of SESSIONS that did it (noncoding only; coding's
    # verify habit was dropped in the lighter v1.0 model).
    if modality != MODALITY_CODING:
        habit_id, pred = "revision_habit", _revise_session
        if habit_id in sigs and _scoped(sigs[habit_id]):
            sig = sigs[habit_id]
            did = sum(1 for ev in evidences if pred([t for t in ev.turns if t.role == "user"]))
            pct = round(100 * did / len(evidences))
            cards.append(_card(sig, "overall", modality,
                               headline=f"{pct}% of sessions",
                               detail=_fmt(sig, pct=pct),
                               stat={"pct": pct, "sessions": len(evidences), "did": did}))

    # ---- token-usage cards (aggregate — MEASURED sessions only; spec §1.6) ----
    per_session_tokens = [session_tokens(ev) for ev in evidences]
    measured_toks = [t for t in per_session_tokens if t.get("provenance") == "measured"]
    n_measured, n_total = len(measured_toks), len(per_session_tokens)
    # Verified aggregates use measured sessions only; estimated/unavailable are
    # never blended into a "verified" total.
    agg = measured_toks or per_session_tokens
    overall_prov = "measured" if measured_toks else (
        "estimated" if any(t.get("provenance") == "estimated" for t in per_session_tokens)
        else "unavailable")
    total_tokens = sum(t["total"] for t in agg)
    total_human = sum(t["human"] for t in agg)
    coverage = f" ({n_measured} of {n_total} sessions verified)" if 0 < n_measured < n_total else ""

    # token_footprint — AVERAGE tokens per session.
    if "token_footprint" in sigs and _scoped(sigs["token_footprint"]):
        sig = sigs["token_footprint"]
        avg = total_tokens / len(agg) if agg else 0
        avg_str = _fmt_tokens(avg)
        if overall_prov == "measured":
            head, det = f"{avg_str} tokens", _fmt(sig, tokens=avg_str, per="per session") + coverage
        elif overall_prov == "estimated":
            head = f"~{avg_str} est."
            det = "Estimated from session activity — no source reported token usage. Not used in your score."
        else:
            head, det = "N/A", "Token usage isn't available for your sources yet."
        cards.append(_card(sig, "overall", modality, headline=head, detail=det,
                           stat={"avg_tokens": round(avg), "total_tokens": total_tokens,
                                 "sessions": len(agg), "measured_sessions": n_measured,
                                 "provenance": overall_prov}))

    # human_token_share — aggregate across all turns.
    if "human_token_share" in sigs and _scoped(sigs["human_token_share"]):
        sig = sigs["human_token_share"]
        pct = round(100 * total_human / total_tokens) if total_tokens else 0
        if overall_prov == "measured":
            head, det = f"{pct}% you", _fmt(sig, pct=pct) + coverage
        elif overall_prov == "estimated":
            head = f"~{pct}% est."
            det = "Estimated share — no source reported token usage. Not used in your score."
        else:
            head, det = "N/A", "Token usage isn't available for your sources yet."
        cards.append(_card(sig, "overall", modality, headline=head, detail=det,
                           stat={"pct": pct, "human": total_human, "total": total_tokens,
                                 "measured_sessions": n_measured, "provenance": overall_prov}))

    # model_mix — most-common model across sessions (overall-only).
    if "model_mix" in sigs and _scoped(sigs["model_mix"]):
        sig = sigs["model_mix"]
        models = [m for m in (_primary_model(ev) for ev in evidences) if m]
        if models:
            top_model = max(set(models), key=models.count)
            cards.append(_card(sig, "overall", modality,
                               headline=top_model,
                               detail=_fmt(sig, model=top_model),
                               stat={"model": top_model, "sessions": len(models)}))

    # parallel_agents — coding only, max observed.
    if modality == MODALITY_CODING and "parallel_agents" in sigs and _scoped(sigs["parallel_agents"]):
        sig = sigs["parallel_agents"]
        observed = [n for n in (_parallel_agents(ev) for ev in evidences) if n]
        if observed:
            mx = max(observed)
            cards.append(_card(sig, "overall", modality,
                               headline=f"Up to {mx} agents",
                               detail=_fmt(sig, n=mx),
                               stat={"max": mx}))

    # tools_used — pooled across sessions, top by call count.
    if "tools_used" in sigs and _scoped(sigs["tools_used"]):
        agg: Dict[str, int] = {}
        for ev in evidences:
            tu = _tools_used(ev)
            if tu:
                for name, c in tu["counts"].items():
                    agg[name] = agg.get(name, 0) + c
        if agg:
            sig = sigs["tools_used"]
            ordered = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
            top = [n for n, _ in ordered[:3]]
            cards.append(_card(sig, "overall", modality,
                               headline=f"{len(agg)} tools",
                               detail=_fmt(sig, distinct=len(agg), n=sum(agg.values()), top=", ".join(top)),
                               stat={"counts": agg, "distinct": len(agg), "total": sum(agg.values()), "top": top}))

    # skills_used — union across sessions.
    if "skills_used" in sigs and _scoped(sigs["skills_used"]):
        seen, uniq = set(), []
        for ev in evidences:
            sk = _skills_used(ev)
            if sk:
                for s in sk["skills"]:
                    if s not in seen:
                        seen.add(s)
                        uniq.append(s)
        if uniq:
            sig = sigs["skills_used"]
            cards.append(_card(sig, "overall", modality,
                               headline=f"{len(uniq)} skill{'' if len(uniq) == 1 else 's'}",
                               detail=_fmt(sig, n=len(uniq), top=", ".join(uniq[:3])),
                               stat={"skills": uniq, "count": len(uniq)}))

    # top_dimension — averaged across sessions.
    avg_scores = _average_dimension_scores(dim_score_rows)
    top = _top_dimension(avg_scores, modality)
    if top and "top_dimension" in sigs and _scoped(sigs["top_dimension"]):
        sig = sigs["top_dimension"]
        cards.append(_card(sig, "overall", modality,
                           headline=top["name"],
                           detail=_fmt(sig, dim=top["name"], score=top["score"]),
                           stat={"dimension": top["key"], "score": top["score"]}))

    return cards


# ===========================================================================
# Archetype assignment
# ===========================================================================

# Human Contribution band thresholds (0-10). HC is the spine of the archetype
# framework (decision: Human Contribution spectrum, NOT Paxel work-habits):
#   < 3   → low HC, leans on the AI                       → Delegator
#   >= 7  → top HC, balanced excellence                   → Vibe Coder / Craftsperson
#   3-7   → mid HC, classified by the dominant scored dim → Collaborator / etc.
_HC_LOW = 3.0
_HC_HIGH = 7.0
_HC_DEFAULT = 5.0  # used when human_contribution is missing from the scores
# Mid-band Craftsperson floor: design & product both strong AND HC at least this.
_CRAFT_HC_FLOOR = 5.0

# Dominant-dimension → archetype-id map (used for the mid HC band, and as the
# Vibe-tier Craftsperson check). Keyed by modality so coding/writing share logic.
_DOMINANT_DIM_TO_ARCHETYPE = {
    MODALITY_CODING: {
        "ai_pairing": "collaborator",
        "prompting": "director",
        "product_thinking": "product_builder",
        "design_thinking": "architect",
    },
    MODALITY_NONCODING: {
        "ai_pairing": "collaborator",
        "prompting": "director",
        "strategic_thinking": "strategist",
        "structured_thinking": "structurer",
        "deliverable_quality": "craftsperson",
    },
}

# The two "design + product" dims whose joint dominance signals craft, per modality.
_CRAFT_DIM_PAIR = {
    MODALITY_CODING: ("design_thinking", "product_thinking"),
    MODALITY_NONCODING: ("structured_thinking", "deliverable_quality"),
}


def _archetype_name(modality: str, archetype_id: str) -> str:
    """Resolve a catalog archetype id to its display NAME for the given modality."""
    for arch in _model_for(modality).get_archetypes():
        if arch.get("id") == archetype_id:
            return arch.get("name", archetype_id)
    return archetype_id


def _archetype_tagline(modality: str, archetype_name: str) -> str:
    """Look up an archetype's evocative tagline by its display NAME (catalog match)."""
    for arch in _model_for(modality).get_archetypes():
        if arch.get("name") == archetype_name:
            return arch.get("tagline", "")
    return ""


def _craft_pair_is_top(dimension_scores: Dict[str, Any], modality: str) -> bool:
    """True when the design & product (craft) dims are clearly the top scored pair.

    "Clearly the top pair" = both craft dims occupy the top two ranked slots
    (excluding human_contribution), so neither another dim outranks them.
    """
    pair = _CRAFT_DIM_PAIR.get(modality, ())
    ranked = _ranked_dimension_keys(dimension_scores)
    if len(ranked) < 2 or len(pair) < 2:
        return False
    return set(ranked[:2]) == set(pair)


def assign_archetype(
    dimension_scores: Dict[str, Any],
    telemetry: Dict[str, Any],
    modality: str,
) -> str:
    """Assign an archetype from the Human Contribution spectrum.

    Returns the archetype NAME (e.g. "The Vibe Coder"). HC is the spine:
      1. hc = human_contribution score (0-10; default 5 if missing).
      2. hc < 3            → Delegator (leans on the AI, light steering).
      3. hc >= 7           → Vibe Coder — the pinnacle (balanced excellence),
                             but the Craftsperson when design & product are
                             clearly the top scored pair.
      4. else (3-7)        → Craftsperson when hc >= 5 AND design & product are
                             both top-tier; otherwise the single dominant scored
                             dim picks: ai_pairing→Collaborator, prompting→
                             Director, product/deliverable→Product Builder/
                             Craftsperson, design/structure→Architect/Architect.

    Catalog comes from the matching model module (coding vs writing). Falls back
    to the first catalog archetype's name when no usable scores are present.
    """
    archetypes = _model_for(modality).get_archetypes()
    if not archetypes:
        return ""

    hc = _score_of((dimension_scores or {}).get("human_contribution"))
    if hc is None:
        hc = _HC_DEFAULT

    # 2. Low HC → leans on the AI.
    if hc < _HC_LOW:
        return _archetype_name(modality, "delegator")

    craft_top = _craft_pair_is_top(dimension_scores, modality)

    # 3. Top HC → the pinnacle, unless craft is unmistakably the story.
    if hc >= _HC_HIGH:
        target = "craftsperson" if craft_top else _vibe_archetype_id(modality)
        return _archetype_name(modality, target)

    # 4. Mid HC (3-7): craft wins when HC is solid AND design+product are top-tier;
    #    otherwise the single dominant scored dim decides.
    if hc >= _CRAFT_HC_FLOOR and craft_top:
        return _archetype_name(modality, "craftsperson")

    ranked = _ranked_dimension_keys(dimension_scores)
    dim_map = _DOMINANT_DIM_TO_ARCHETYPE.get(modality, {})
    # Pick the highest-ranked dim that ACTUALLY maps to an archetype in THIS
    # modality. A mixed coding+writing profile unions all dims, so an off-modality
    # dim (e.g. strategic_thinking for a coding profile) can rank top; using it
    # blindly fell through to archetypes[0] — which is "The Delegator" (the lowest
    # archetype, listed first) — mislabeling strong profiles. Skip to the first
    # mapped dim, and default to the neutral Collaborator, never the lowest.
    target = next((dim_map[d] for d in ranked if d in dim_map), None)
    if not target:
        target = "collaborator"
    return _archetype_name(modality, target)


def _vibe_archetype_id(modality: str) -> str:
    """The top-HC pinnacle archetype id for the modality."""
    return "vibe_coder" if modality == MODALITY_CODING else "vibe_writer"


# ===========================================================================
# Internal helpers
# ===========================================================================

def _get(obj: Any, attr: str) -> Any:
    """Read `attr` from an object (attribute) or a dict (key)."""
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)


def _coerce_evidence(raw: Any) -> Optional[EvidencePacket]:
    """Coerce a stored evidence value (EvidencePacket | dict | None) into a packet."""
    if raw is None:
        return None
    if isinstance(raw, EvidencePacket):
        return raw
    if isinstance(raw, dict):
        try:
            return EvidencePacket(**raw)
        except Exception as exc:  # malformed stored row — skip, don't crash aggregation
            logger.warning("[aura] could not coerce stored evidence to packet: %s", exc)
            return None
    return None


def _score_of(entry: Any) -> Optional[float]:
    """Extract a numeric score from a DimensionScore dict or a raw number."""
    if isinstance(entry, dict):
        val = entry.get("score")
    else:
        val = entry
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _ranked_dimension_keys(dimension_scores: Dict[str, Any]) -> List[str]:
    """Weighted dimension keys sorted by score desc (excludes human_contribution
    and any non-weighted/meta dim)."""
    pairs = []
    for k, v in (dimension_scores or {}).items():
        if k == "human_contribution":
            continue
        sc = _score_of(v)
        if sc is not None:
            pairs.append((k, sc))
    pairs.sort(key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in pairs]


def _top_dimension(dimension_scores: Dict[str, Any], modality: str) -> Optional[Dict[str, Any]]:
    """The highest-scoring weighted dimension, with its display name."""
    ranked = _ranked_dimension_keys(dimension_scores)
    if not ranked:
        return None
    key = ranked[0]
    score = _score_of(dimension_scores.get(key))
    dims = _model_for(modality).get_active_dimensions()
    name = dims.get(key, {}).get("name", key.replace("_", " ").title())
    return {"key": key, "name": name, "score": round(score, 1) if score is not None else None}


def _average_dimension_scores(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Average per-dimension scores across many sessions' dimension_scores dicts."""
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for row in rows:
        for k, v in (row or {}).items():
            sc = _score_of(v)
            if sc is None:
                continue
            totals[k] = totals.get(k, 0.0) + sc
            counts[k] = counts.get(k, 0) + 1
    return {k: {"score": totals[k] / counts[k]} for k in totals if counts[k]}


def _active_signal_ids(telemetry: Dict[str, Any]) -> set:
    """Map computed telemetry to the card-signal ids that are 'present' enough to
    act as archetype tiebreakers."""
    active: set = set()
    if not telemetry:
        return active

    tod = telemetry.get("time_of_day")
    if tod:
        active.add("time_of_day")
    if telemetry.get("prompt_length"):
        active.add("prompt_length")
    pol = telemetry.get("politeness")
    if pol and pol.get("n"):
        active.add("politeness")
    rr = telemetry.get("redirect_rate")
    if rr and rr.get("n"):
        active.add("redirect_rate")
    if telemetry.get("planned"):
        active.add("plan_ratio")
        active.add("outline_ratio")
    if telemetry.get("revised"):
        active.add("revision_habit")
    pa = telemetry.get("parallel_agents")
    if isinstance(pa, (int, float)) and pa and pa > 1:
        active.add("parallel_agents")
    # go_to_phrase is an LLM signal but archetypes may list it; treat presence of
    # any user turns as "has a go-to phrase candidate".
    if telemetry.get("prompt_length"):
        active.add("go_to_phrase")
    return active
