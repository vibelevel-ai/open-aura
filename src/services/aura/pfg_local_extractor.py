"""Local PFG tag extractor (Open Aura POC).

Turns the UNREDACTED ``LocalContext`` (real git diff + full transcript + dependency
manifests + commands) into high-quality ``PfgTag``s for graph grounding. This is
Open Aura's divergence from the hosted edition: the hosted scorer only ever sees a
redacted packet, so it had to ask the agent to *guess* tags. Running locally, we
read the actual artifacts and derive them.

Two passes, merged:
  1. DETERMINISTIC — parse dependency manifests + added imports in the diff +
     touched file paths + commands. High precision for libraries/services/infra.
  2. LOCAL LLM — read the FULL transcript + diff and name the capabilities,
     patterns and work-areas, AND (the point) HOW they were built: hand-rolled
     (direct-api/manual/custom) vs an established SDK/framework. The hand-rolled
     signal is what lets the graph suggest the tool you could have used.

Best-effort: every step is guarded; a failure degrades to fewer tags, never an
exception. Tags NEVER affect the Aura score.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from .contracts import ApproachType, EvidenceBasis, LocalContext, PfgTag, TagCategory

logger = logging.getLogger(__name__)

MAX_TAGS = 12
# Char budgets for the LLM pass (the diff/transcript can be large). Generous —
# we want real signal — but bounded so the extraction call stays cheap.
_TRANSCRIPT_BUDGET = int(os.getenv("PFG_EXTRACT_TRANSCRIPT_CHARS", "24000"))
_DIFF_BUDGET = int(os.getenv("PFG_EXTRACT_DIFF_CHARS", "16000"))

_VALID_CATEGORIES = set(TagCategory.__args__)            # type: ignore[attr-defined]
_VALID_APPROACHES = set(ApproachType.__args__)           # type: ignore[attr-defined]
_VALID_BASES = set(EvidenceBasis.__args__)               # type: ignore[attr-defined]

# Strength order so dedup keeps the better-grounded duplicate.
_BASIS_RANK = {"import": 3, "command": 2, "file": 1, "discussion": 0}

# Light name normalization for common package aliases → the bare name PFG nodes
# tend to use. Keeps deterministic library tags matchable.
_NAME_ALIASES = {
    "psycopg2-binary": "psycopg2",
    "psycopg": "psycopg2",
    "@anthropic-ai/sdk": "anthropic",
    "@langchain/core": "langchain",
    "langchain-core": "langchain",
    "langchain-groq": "langchain",
    "openai-python": "openai",
}

# Commands → (tag name, category). Detected in local_context.commands and the diff.
_COMMAND_TAGS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\b(docker compose|docker-compose|docker)\b", re.I), "docker", "infra"),
    (re.compile(r"\b(flyctl|fly deploy|fly )\b", re.I), "fly", "service"),
    (re.compile(r"\bvercel\b", re.I), "vercel", "service"),
    (re.compile(r"\b(pytest|jest|vitest|playwright)\b", re.I), "testing", "work_area"),
    (re.compile(r"\b(alembic|migrate|migration)\b", re.I), "migration", "work_area"),
    (re.compile(r"\bgh\b|\bgit push\b", re.I), "git", "work_area"),
]

# Touched-path → work_area inference (weak, file-basis).
_PATH_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(^|/)migrations?/|\.sql$", re.I), "migration"),
    (re.compile(r"(^|/)(api|routes?|endpoints?)/|_endpoints?\.py$|router", re.I), "backend-endpoint"),
    (re.compile(r"\.(tsx|jsx)$|(^|/)(pages|app|components)/", re.I), "ui-page"),
    (re.compile(r"(^|/)(auth|oauth)", re.I), "auth"),
]


# ---------------------------------------------------------------------------
# Normalization / dedup
# ---------------------------------------------------------------------------

def _norm_name(raw: str) -> str:
    n = (raw or "").strip().lower()
    # npm scope: keep the package part (@scope/pkg -> pkg) unless aliased.
    if n in _NAME_ALIASES:
        return _NAME_ALIASES[n]
    if n.startswith("@") and "/" in n:
        n = n.split("/", 1)[1]
    # python extras / version specifiers
    n = re.split(r"[\[=<>~!;\s]", n, 1)[0]
    n = n.strip().strip("/").strip()
    return _NAME_ALIASES.get(n, n)


def _mk(name: str, category: str, basis: str = "file",
        approach: Optional[str] = None) -> Optional[PfgTag]:
    name = _norm_name(name)
    if not name or len(name) < 2 or category not in _VALID_CATEGORIES:
        return None
    if basis not in _VALID_BASES:
        basis = "file"
    if approach is not None and approach not in _VALID_APPROACHES:
        approach = None
    try:
        return PfgTag(name=name, category=category, evidence_basis=basis, approach=approach)
    except Exception:
        return None


def _merge(tags: list[PfgTag]) -> list[PfgTag]:
    """Dedup by (name, category); keep the stronger-evidence / approach-bearing one."""
    best: dict[tuple, PfgTag] = {}
    for t in tags:
        if t is None:
            continue
        key = (t.name, t.category)
        cur = best.get(key)
        if cur is None:
            best[key] = t
            continue
        # prefer a tag that carries an approach, then stronger evidence basis
        if (t.approach and not cur.approach) or (
            _BASIS_RANK.get(t.evidence_basis, 0) > _BASIS_RANK.get(cur.evidence_basis, 0)
        ):
            # keep the approach if either had one
            t.approach = t.approach or cur.approach
            best[key] = t
        elif cur.approach is None and t.approach:
            cur.approach = t.approach
    return list(best.values())[:MAX_TAGS]


# ---------------------------------------------------------------------------
# Deterministic pass
# ---------------------------------------------------------------------------

def _from_manifests(manifests: dict[str, str]) -> list[PfgTag]:
    out: list[PfgTag] = []
    for fname, content in (manifests or {}).items():
        base = os.path.basename(fname).lower()
        try:
            if base == "package.json":
                data = json.loads(content)
                for sect in ("dependencies", "devDependencies", "peerDependencies"):
                    for dep in (data.get(sect) or {}):
                        out.append(_mk(dep, "library", "import"))
            elif base in ("requirements.txt", "requirements-dev.txt"):
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith(("#", "-")):
                        out.append(_mk(line, "library", "import"))
            elif base == "pyproject.toml":
                out.extend(_parse_pyproject(content))
            elif base == "go.mod":
                for m in re.finditer(r"^\s*(?:require\s+)?([\w./-]+/[\w./-]+)\s+v", content, re.M):
                    out.append(_mk(m.group(1).rsplit("/", 1)[-1], "library", "import"))
            elif base == "cargo.toml":
                out.extend(_parse_cargo(content))
        except Exception as exc:
            logger.debug("[pfg-extract] manifest %s parse failed: %s", fname, exc)
    return [t for t in out if t]


def _parse_pyproject(content: str) -> list[PfgTag]:
    out: list[PfgTag] = []
    try:
        import tomllib  # py3.11+
        data = tomllib.loads(content)
        proj = (data.get("project") or {}).get("dependencies") or []
        for dep in proj:
            out.append(_mk(dep, "library", "import"))
        poetry = (((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {})
        for dep in poetry:
            if dep.lower() != "python":
                out.append(_mk(dep, "library", "import"))
    except Exception:
        # crude fallback: lines that look like `name = "..."` under a deps table
        for m in re.finditer(r'^\s*"?([A-Za-z0-9_.\-]+)"?\s*[=>]', content, re.M):
            out.append(_mk(m.group(1), "library", "import"))
    return [t for t in out if t]


def _parse_cargo(content: str) -> list[PfgTag]:
    out: list[PfgTag] = []
    in_deps = False
    for line in content.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_deps = "dependencies" in s.lower()
            continue
        if in_deps:
            m = re.match(r"([A-Za-z0-9_\-]+)\s*=", s)
            if m:
                out.append(_mk(m.group(1), "library", "import"))
    return [t for t in out if t]


def _from_diff(git_diff: str) -> list[PfgTag]:
    """Added imports + touched-path work-areas from the diff."""
    out: list[PfgTag] = []
    if not git_diff:
        return out
    for line in git_diff.splitlines():
        # touched files
        m = re.match(r"^\+\+\+ b/(.+)$", line)
        if m:
            path = m.group(1)
            for rule, area in _PATH_RULES:
                if rule.search(path):
                    out.append(_mk(area, "work_area", "file"))
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        # python imports
        m = re.match(r"\s*(?:from|import)\s+([A-Za-z0-9_][A-Za-z0-9_.]*)", added)
        if m:
            top = m.group(1).split(".")[0]
            if top not in ("__future__",):
                out.append(_mk(top, "library", "import"))
            continue
        # js/ts imports + requires
        m = re.search(r"""\bfrom\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)""", added)
        if m:
            mod = m.group(1) or m.group(2) or ""
            if mod and not mod.startswith("."):  # skip relative imports
                out.append(_mk(mod, "library", "import"))
    return [t for t in out if t]


def _from_commands(commands: list[str], extra_text: str = "") -> list[PfgTag]:
    out: list[PfgTag] = []
    blob = "\n".join(commands or []) + "\n" + (extra_text or "")
    if not blob.strip():
        return out
    for rule, name, category in _COMMAND_TAGS:
        if rule.search(blob):
            out.append(_mk(name, category, "command"))
    return [t for t in out if t]


# ---------------------------------------------------------------------------
# Local-LLM pass — capabilities / patterns / approach (the differentiator)
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """You are a code-and-session analyst for VibeLevel Aura (Open Aura, local mode).

You are given the REAL git diff and the FULL transcript of one AI work session
(this stays on the user's machine). Extract a SHORT list (max 8) of evidence-derived
signals about WHAT was used/built and HOW it was built, for grounding against a
Product Feature Graph.

Rules:
- EVIDENCE-DERIVED ONLY. Every tag must trace to something actually in the diff or
  transcript (an import, a file, a command, code you can see). Never guess.
- Focus on what a simple import-scan would MISS: capabilities built, architecture
  patterns, work-areas, external services/models, and especially the APPROACH.
- APPROACH is the point: for anything built BY HAND that an established
  SDK/framework/pattern usually handles, set a hand-rolled approach so the graph
  can suggest the tool. Generic examples:
    agent loop / orchestration via raw LLM calls -> direct-api
    tool / function-calling wired by hand        -> manual
    retrieval / RAG glued together yourself       -> manual or custom
    retries / backoff / rate-limiting hand-coded  -> manual
    raw SQL + hand-managed connections            -> manual
    custom caching / queue / auth                 -> custom
  If an established tool WAS used, set sdk | library | framework (no nag).
- NAMES ONLY (normalized, lowercase, kebab-case). No code or prompt text.

category MUST be one of: library, service, model, infra, capability, pattern, work_area, product_area
approach (optional) MUST be one of: sdk, library, framework, direct-api, manual, custom
evidence_basis MUST be one of: import, file, command, discussion

Respond with ONLY a JSON array, e.g.:
[
  {"name":"agent-orchestration","category":"capability","approach":"direct-api","evidence_basis":"file"},
  {"name":"groq","category":"model","evidence_basis":"import"},
  {"name":"db-access","category":"work_area","approach":"manual","evidence_basis":"file"}
]

## GIT DIFF
{diff}

## TRANSCRIPT
{transcript}
"""


def _llm_extract(local_context: LocalContext, meta: Any = None) -> list[PfgTag]:
    if os.getenv("PFG_EXTRACT_LLM", "true").strip().lower() in ("0", "false", "no", "off"):
        return []
    diff = (local_context.git_diff or "")[:_DIFF_BUDGET]
    transcript = (local_context.full_transcript or "")[:_TRANSCRIPT_BUDGET]
    if not diff.strip() and not transcript.strip():
        return []
    prompt = (_EXTRACT_PROMPT
              .replace("{diff}", diff or "(no diff provided)")
              .replace("{transcript}", transcript or "(no transcript provided)"))
    try:
        from ...core.model_config import model_config_manager
        from langchain_core.messages import HumanMessage
        model = os.getenv("AURA_SCORING_MODEL", "openai/gpt-oss-120b")
        # SYNCHRONOUS on purpose — ground_session runs this whole module inside
        # asyncio.to_thread, so a blocking invoke is correct here.
        llm = model_config_manager.create_llm(model, temperature=0.2, max_tokens=2048, streaming=False)
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        return _parse_llm_tags(text)
    except Exception as exc:
        logger.debug("[pfg-extract] llm pass skipped: %s", exc)
        return []


def _parse_llm_tags(text: str) -> list[PfgTag]:
    text = (text or "").strip()
    if not text:
        return []
    # strip code fences
    if "```" in text:
        seg = text.split("```", 1)[1]
        seg = seg[4:] if seg.lower().startswith("json") else seg
        text = seg.split("```", 1)[0].strip()
    # isolate the JSON array
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        rows = json.loads(text[start:end + 1])
    except Exception as exc:
        logger.debug("[pfg-extract] llm json parse failed: %s", exc)
        return []
    out: list[PfgTag] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        tag = _mk(
            r.get("name", ""), str(r.get("category", "")),
            str(r.get("evidence_basis", "file")) or "file",
            r.get("approach"),
        )
        if tag:
            out.append(tag)
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_tags(local_context: LocalContext, meta: Any = None) -> list[PfgTag]:
    """Extract grounded PfgTags from the real local context. Never raises."""
    try:
        if local_context is None:
            return []
        # accept a dict too (defensive — the MCP layer may hand us either)
        if isinstance(local_context, dict):
            local_context = LocalContext(**local_context)
        deterministic: list[PfgTag] = []
        deterministic += _from_manifests(local_context.manifests)
        deterministic += _from_diff(local_context.git_diff or "")
        deterministic += _from_commands(
            local_context.commands, extra_text=local_context.git_diff or "")
        llm_tags = _llm_extract(local_context, meta)
        merged = _merge(deterministic + llm_tags)
        logger.info(
            "[pfg-extract] %d tag(s) (deterministic=%d, llm=%d) repo=%s",
            len(merged), len(deterministic), len(llm_tags), local_context.repo or "?",
        )
        return merged
    except Exception as exc:
        logger.debug("[pfg-extract] extract_tags failed: %s", exc)
        return []
