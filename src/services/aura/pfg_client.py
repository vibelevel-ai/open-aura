"""Aura × PFG resolution layer — operational insights (Open Aura POC).

Resolves evidence-derived ``PfgTag``s against a Product Feature Graph (PFG) and
produces grounded *check-tips*. Server-side, READ-ONLY, best-effort.

What's different in Open Aura
-----------------------------
The hosted edition can only ever see a REDACTED evidence packet, so it had to ask
the *agent* to self-report tags — and weak, guessed tags produced weak grounding.
Open Aura runs locally, so it sees the **real git diff + full transcript** and
derives the tags itself (``pfg_local_extractor``). This module is the second half:
it takes those high-quality tags and grounds them against the graph.

Why this resolution layer exists
---------------------------------
PFG ``search_nodes`` is a LITERAL substring match, so a single phrase query
("database connection pool") often returns nothing even when the node exists
("Backend-Only Database Access via Connection Pool"). This layer beats that with
**token + synonym expansion** and **category-aware ranking**, then computes a
**3-factor confidence** (match / evidence / authority) and emits a **check-tip**
(never a verdict, never a score input).

Design notes
------------
- The PFG transport is INJECTED (``search_fn``) so this module is unit-testable
  with no live MCP, and the live path is a thin urllib client built from env.
- Read-only: we never propose or write to the graph. A genuine gap (high-evidence
  ``not_found``) is surfaced for the human to take to PFG themselves.
- Tags NEVER feed the LLM score; findings are advisory only.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Optional

from .contracts import PfgTag

logger = logging.getLogger(__name__)

# Search transport: (query, limit) -> list[node dict] with at least
# {id, name, type, status, tags, workspace_slug, description}.
SearchFn = Callable[[str, int], list[dict]]

# Category → preferred PFG node types (drives disambiguation ranking).
CATEGORY_NODE_TYPES: dict[str, list[str]] = {
    "library": ["product", "product_line", "feature", "sub_feature"],
    "service": ["external_system"],
    "model": ["external_system"],
    "infra": ["tech_component"],
    "capability": ["capability", "feature"],
    "pattern": ["capability", "feature"],
    "work_area": ["standard", "agent_skill"],
    "product_area": ["feature", "sub_feature", "product_line", "capability"],
}

# Workspaces that are "owned" ground truth (your product / the PFG product), so a
# match there can speak with AUTHORITY (esp. for work_area / product_area).
OWNED_WORKSPACES: set[str] = {"vibelevel", "contactgptsocial"}

# Synonym / token expansion — the heart of the "fixed resolution". A tag name is
# expanded into several substring-friendly query tokens so PFG's substring search
# actually hits. Keep entries short and contiguous (they're substring queries).
SYNONYMS: dict[str, list[str]] = {
    "db": ["database", "connection pool", "psycopg2", "postgres"],
    "db-access": ["database", "connection pool", "psycopg2"],
    "database": ["database", "connection pool", "postgres"],
    "postgres": ["postgres", "database", "neon"],
    "auth": ["auth", "oauth", "authentication"],
    "mcp": ["mcp", "model context protocol"],
    "streamable-http": ["streamable", "transport", "mcp"],
    "rag": ["rag", "retrieval"],
    "vector-db": ["vector", "embedding"],
    "backend-endpoint": ["endpoint", "backend", "fastapi"],
    "ui-page": ["page", "ui", "frontend"],
    "migration": ["migration", "schema"],
    "sandbox": ["sandbox", "e2b"],
    "scoring": ["scoring", "grading"],
}

# Statuses that mean "don't build new on this" → power the currency-check.
_LEGACY_STATUSES = {"deprecated", "legacy", "removed", "sunset"}
# Statuses that are a clean, current target.
_CURRENT_STATUSES = {"ga", "shipped", "beta", "stable"}
# Approaches that mean "hand-rolled" — eligible for an "improve" tip when the graph
# maps an established SDK/framework/pattern for the same capability.
_MANUAL_APPROACHES = {"direct-api", "manual", "custom"}
# Categories where a high-evidence "not found" is a MEANINGFUL gap worth adding to
# the graph (you built something the graph doesn't yet map). A missing third-party
# library/service/model/infra node just means it's untracked — NOT that you're ahead
# of the graph — so those not-founds are never surfaced (precision over noise).
_GAP_CATEGORIES = {"capability", "product_area"}
# Tokens too generic to be a real match on their own — a lone hit on one of these
# (e.g. "cache" matching an unrelated node that merely mentions caching) must NOT
# create a check-tip. Precision guardrail: real matches need specific overlap.
_GENERIC_TOKENS = {
    "cache", "api", "app", "core", "base", "util", "utils", "main", "test", "tests",
    "file", "files", "code", "node", "item", "list", "view", "page", "panel", "tool",
    "tools", "user", "name", "type", "http", "json", "data", "sync", "async", "config",
    "manager", "handler", "service", "system", "module", "server", "client", "engine",
    "store", "model", "agent", "db", "sdk", "library", "framework", "build", "run",
}


def query_tokens(name: str) -> list[str]:
    """Expand a tag name into substring-friendly query tokens (synonyms + parts)."""
    name = (name or "").lower().strip()
    toks: set[str] = set()
    if name:
        toks.add(name)
        toks.update(SYNONYMS.get(name, []))
        # split compound names so each part can substring-match a node
        for part in re.split(r"[\s\-_/.]+", name):
            if len(part) >= 3:
                toks.add(part)
    return sorted(toks)


def _norm_status(node: dict) -> str:
    return str(node.get("status") or "").strip().lower()


def _candidate_score(node: dict, tag: PfgTag, toks: list[str]) -> int:
    """Rank a candidate node for a tag: category-fit + token overlap + ownership."""
    score = 0
    preferred = CATEGORY_NODE_TYPES.get(tag.category, [])
    ntype = node.get("type")
    if ntype in preferred:
        score += 20 - preferred.index(ntype)  # earlier in the list = better fit
    haystack = " ".join([
        str(node.get("name", "")), str(node.get("id", "")),
        str(node.get("description", "")), " ".join(node.get("tags") or []),
    ]).lower()
    for t in toks:
        if t in haystack:
            score += 3
    # exact-ish name/id hit is a strong signal
    nid = str(node.get("id", "")).lower()
    nname = str(node.get("name", "")).lower()
    if tag.name.lower() in (nid, nname) or nid.endswith("." + tag.name.lower()):
        score += 8
    if node.get("workspace_slug") in OWNED_WORKSPACES and tag.category in ("work_area", "product_area"):
        score += 4
    return score


def _distinctive_tokens(toks: list[str], tag_name: str) -> list[str]:
    """Tokens specific enough that a hit means a REAL match — not a common word."""
    return [t for t in toks
            if t != tag_name and len(t) >= 4 and t not in _GENERIC_TOKENS]


def _match_strength(node: dict, tag: PfgTag, toks: list[str]) -> str:
    """How sure we are this is the RIGHT node (precision-first):
      high — exact/suffix id-or-name hit, the full tag name appears in the node,
             OR >=2 distinctive (specific, non-generic) token hits.
      med  — exactly 1 distinctive hit.
      low  — only generic-token hits (e.g. 'cache') or none. NEVER surfaced."""
    name = tag.name.lower()
    nid = str(node.get("id", "")).lower()
    nname = str(node.get("name", "")).lower()
    haystack = " ".join([
        nname, nid, str(node.get("description", "")), " ".join(node.get("tags") or []),
    ]).lower()
    if name in (nid, nname) or nid.endswith("." + name):
        return "high"
    if len(name) >= 5 and name in haystack:
        return "high"
    distinct = _distinctive_tokens(toks, name)
    # A distinctive token in the node's NAME or curated TAGS is a strong signal;
    # a hit only in the free-text description is weaker (one alone = med).
    strong_text = nname + " " + " ".join(node.get("tags") or []).lower()
    strong_hits = sum(1 for t in distinct if t in strong_text)
    any_hits = sum(1 for t in distinct if t in haystack)
    if strong_hits >= 1 or any_hits >= 2:
        return "high"
    if any_hits == 1:
        return "med"
    return "low"


def _confidence(node: Optional[dict], tag: PfgTag, toks: list[str]) -> dict:
    """3-factor confidence: match / evidence / authority."""
    match = "none" if node is None else _match_strength(node, tag, toks)
    evidence = "high" if tag.evidence_basis in ("import", "file", "command") else "low"
    authority = "low"
    if node is not None:
        owned = node.get("workspace_slug") in OWNED_WORKSPACES
        definitive = _norm_status(node) in (_LEGACY_STATUSES | _CURRENT_STATUSES)
        authority = "high" if (owned and definitive) else ("med" if definitive else "low")
    return {"match": match, "evidence": evidence, "authority": authority}


def _surfaceable(conf: dict) -> bool:
    """Surface ONLY high-confidence checks (precision over recall): we must be
    confident WHICH node it is (match=high) AND that it was really used
    (evidence=high). Everything else is stored/logged but NOT shown to the client."""
    return conf["match"] == "high" and conf["evidence"] == "high"


def _direction_and_message(node: dict, tag: PfgTag, conf: dict) -> tuple[str, str]:
    """Pick the check-tip direction + a check-worded (not verdict) message."""
    status = _norm_status(node)
    name = node.get("name") or node.get("id")
    ntype = node.get("type")

    # currency-check: graph marks this legacy/deprecated.
    if status in _LEGACY_STATUSES:
        return ("currency", f"Graph marks '{name}' as {status}; confirm you're on the "
                            f"current path — or flag the graph if you've already moved.")
    # improve-check: you hand-rolled this, but the graph maps an established tool/SDK
    # for the same capability — suggest it (e.g. direct API calls vs an agent SDK).
    approach = (getattr(tag, "approach", "") or "").lower()
    if approach in _MANUAL_APPROACHES and ntype in ("product", "product_line", "feature", "capability"):
        return ("improve", f"You built '{tag.name}' via {approach} — the graph maps "
                          f"'{name}' ({status or 'an established tool'}); consider it "
                          f"instead of rolling your own.")
    # compliance (good-design) check: a standard governs this work area.
    if ntype == "standard":
        return ("compliance", f"Relevant standard: '{name}'. Confirm your "
                              f"{tag.name} work follows it.")
    # adopt-check: a skill/doc exists for what you did.
    if ntype == "agent_skill":
        return ("adopt", f"There's a skill for this — '{name}'. Worth a look.")
    # default: a current/known node — informational confirmation.
    return ("confirm", f"Maps to '{name}' ({status or 'known'}) in the graph.")


def _active_workspace_is_owned() -> bool:
    """True when the configured PFG workspace is one you CURATE (your product
    graph). Graph-gap tips ("add it to PFG") only make sense there — not against a
    public reference catalog of SDKs/skills you don't own."""
    import os
    ws = (os.environ.get("PFG_WORKSPACE", "vibelevel").strip() or "vibelevel")
    return ws in OWNED_WORKSPACES


def resolve_tag(tag: PfgTag, search_fn: SearchFn) -> dict:
    """Resolve ONE tag → a finding (always returns a dict; never raises)."""
    toks = query_tokens(tag.name)
    candidates: dict[tuple, dict] = {}
    for tok in toks:
        try:
            for node in (search_fn(tok, 10) or []):
                key = (node.get("workspace_slug"), node.get("id"))
                if key not in candidates:
                    candidates[key] = node
        except Exception as exc:  # one bad query shouldn't kill resolution
            logger.debug("[pfg] search '%s' failed: %s", tok, exc)

    if not candidates:
        # graph-gap: nothing found. First-class signal — strong evidence = the user
        # is likely ahead of / beyond the graph. Surfaced ONLY for capability/
        # product_area tags (where a gap is real), and ONLY when grounding against a
        # workspace you OWN (a public SDK/skills catalog isn't yours to add to).
        # Never for untracked third-party libraries. We never write; the human takes
        # it to PFG themselves.
        evidence = "high" if tag.evidence_basis in ("import", "file", "command") else "low"
        surfaced = (evidence == "high" and tag.category in _GAP_CATEGORIES
                    and _active_workspace_is_owned())
        return {
            "tag": tag.name, "category": tag.category, "node_id": None,
            "confidence": {"match": "none", "evidence": evidence, "authority": "low"},
            "direction": "graph_gap", "surfaced": surfaced,
            "message": (f"'{tag.name}' isn't in the graph — possibly new/ahead, or "
                        f"unmapped. Consider adding it in PFG.") if surfaced else "",
            "node_status": None, "workspace": None,
        }

    ranked = sorted(candidates.values(), key=lambda n: _candidate_score(n, tag, toks), reverse=True)
    best = ranked[0]
    conf = _confidence(best, tag, toks)
    surfaced = _surfaceable(conf)
    direction, message = _direction_and_message(best, tag, conf) if surfaced else ("", "")
    return {
        "tag": tag.name, "category": tag.category,
        "node_id": best.get("id"), "workspace": best.get("workspace_slug"),
        "node_status": _norm_status(best) or None,
        "confidence": conf, "direction": direction,
        "surfaced": surfaced, "message": message,
    }


def resolve_tags(tags: list[PfgTag], search_fn: SearchFn, max_tips: int = 3) -> dict:
    """Resolve all tags → {findings, check_tips}. Best-effort; never raises.

    check_tips = the surfaced subset, capped at ``max_tips``, ordered by
    usefulness (improve/currency/compliance before bare confirmations, then by
    confidence). These are advisory only.
    """
    findings = [resolve_tag(t, search_fn) for t in (tags or [])]
    rank = {"none": 0, "low": 1, "med": 2, "high": 3}
    dir_priority = {"improve": 5, "currency": 4, "compliance": 3, "graph_gap": 2,
                    "adopt": 1, "confirm": 0, "": -1}
    tips = [f for f in findings if f.get("surfaced") and f.get("message")]
    tips.sort(key=lambda f: (dir_priority.get(f["direction"], 0),
                             rank[f["confidence"]["match"]]), reverse=True)
    return {"findings": findings, "check_tips": tips[:max_tips]}


# ---------------------------------------------------------------------------
# Live PFG transport (optional, env-gated). Open Aura talks to a PFG MCP over
# streamable-HTTP. Gated by config so nothing runs until it's wired:
#   PFG_GROUNDING_ENABLED=true  PFG_MCP_URL=https://…/mcp  PFG_MCP_TOKEN=…
#   PFG_WORKSPACE=vibelevel   (the graph workspace to read; passed per call)
# Read-only; one handshake is cached per process and reused across queries.
# ---------------------------------------------------------------------------
import json as _json
import os as _os
import urllib.request as _urllib

_pfg_session: dict = {"search": None, "tried": False}


def _env_flag(name: str) -> bool:
    return _os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _build_pfg_search() -> Optional[SearchFn]:
    """Return a search_fn(query, limit) backed by the PFG MCP, or None if not
    configured. The MCP session is established once and reused. ``search_nodes``
    is called with the configured ``workspace_slug`` (the PFG MCP scopes reads to
    one workspace per call)."""
    url = _os.environ.get("PFG_MCP_URL")  # must include the /mcp path
    token = _os.environ.get("PFG_MCP_TOKEN")
    workspace = _os.environ.get("PFG_WORKSPACE", "vibelevel").strip() or "vibelevel"
    if not url:
        return None
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream",
               # Cloudflare WAF (Error 1010) bans the default Python-urllib UA, so
               # the request never reaches the PFG MCP — send a normal User-Agent.
               "User-Agent": "open-aura/1.0"}
    if token:
        headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    sid = {"v": None}

    def _post(body: dict, timeout: int = 30):
        h = dict(headers)
        if sid["v"]:
            h["Mcp-Session-Id"] = sid["v"]
        req = _urllib.Request(url, data=_json.dumps(body).encode(), headers=h, method="POST")
        resp = _urllib.urlopen(req, timeout=timeout)
        if resp.headers.get("Mcp-Session-Id"):
            sid["v"] = resp.headers.get("Mcp-Session-Id")
        raw = resp.read().decode("utf-8", "replace")
        if "text/event-stream" in (resp.headers.get("Content-Type") or ""):
            out = None
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        out = _json.loads(line[5:].strip())
                    except Exception:
                        pass
            return out
        return _json.loads(raw) if raw.strip() else {}

    # handshake
    _post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                      "clientInfo": {"name": "open-aura-pfg", "version": "1.0"}}})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def search_fn(query: str, limit: int = 10) -> list[dict]:
        r = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                   "params": {"name": "search_nodes",
                              "arguments": {"workspace_slug": workspace,
                                            "query": query, "limit": limit}}})
        res = (r or {}).get("result", r) or {}
        sc = res.get("structuredContent")
        data = sc if isinstance(sc, dict) else None
        if data is None:
            for b in res.get("content", []) or []:
                if isinstance(b, dict) and b.get("type") == "text":
                    try:
                        data = _json.loads(b["text"])
                    except Exception:
                        data = {}
        rows = (data or {}).get("result", []) if isinstance(data, dict) else (data or [])
        if not isinstance(rows, list):
            return []
        # Stamp the workspace so authority/ownership ranking works even if the MCP
        # row omits it (we only ever queried this one workspace).
        for row in rows:
            if isinstance(row, dict):
                row.setdefault("workspace_slug", workspace)
        return [r for r in rows if isinstance(r, dict)]

    return search_fn


def _get_search() -> Optional[SearchFn]:
    """Lazily build + cache the live PFG search transport for this process."""
    if not _pfg_session["tried"]:
        try:
            _pfg_session["search"] = _build_pfg_search()
        except Exception as exc:
            logger.debug("[pfg] transport init failed: %s", exc)
            _pfg_session["search"] = None
        _pfg_session["tried"] = True
    return _pfg_session["search"]


def pfg_status(probe: bool = False, timeout: int = 6) -> dict:
    """Describe the PFG grounding config for startup/diagnostics. Never raises.

    Returns {enabled, configured, url, host, workspace, extract_llm, reachable}.
    ``reachable`` is None unless ``probe=True`` AND it's configured, in which case
    a bounded best-effort handshake+search decides True/False (a hung endpoint is
    reported unreachable after ``timeout`` seconds; startup is never blocked longer).
    """
    enabled = _env_flag("PFG_GROUNDING_ENABLED")
    url = (_os.environ.get("PFG_MCP_URL") or "").strip()
    workspace = (_os.environ.get("PFG_WORKSPACE") or "vibelevel").strip() or "vibelevel"
    extract_llm = (_os.environ.get("PFG_EXTRACT_LLM", "true").strip().lower()
                   not in ("0", "false", "no", "off"))
    host = url
    if url:
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc or url
        except Exception:
            host = url
    status = {
        "enabled": enabled, "configured": bool(enabled and url),
        "url": url, "host": host, "workspace": workspace,
        "extract_llm": extract_llm, "reachable": None,
    }
    if probe and status["configured"]:
        status["reachable"] = _probe_reachable(timeout)
    return status


def _probe_reachable(timeout: int) -> bool:
    """Bounded reachability check: build a transport + one cheap search in a
    daemon thread, bounded by ``timeout`` (a hung connection can't stall startup)."""
    import threading
    out = {"ok": False}

    def _run():
        try:
            fn = _build_pfg_search()
            if fn is None:
                return
            fn("mcp", 1)  # any cheap query; success = handshake + call worked
            out["ok"] = True
        except Exception as exc:
            logger.debug("[pfg] reachability probe failed: %s", exc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    return out["ok"]


def ground_session(local_context, meta=None, search_fn: Optional[SearchFn] = None) -> list[dict]:
    """Best-effort PFG grounding for ONE session from its LOCAL context.

    Open Aura's divergence: extract high-quality tags from the REAL local context
    (git diff + full transcript + manifests) — not an agent's redacted guess — then
    resolve them against the graph. Returns the advisory check-tips, or [] if
    disabled / unconfigured / nothing extracted. NEVER raises and NEVER affects the
    score. ``search_fn`` may be injected for tests; otherwise the env transport is
    used (and grounding is skipped when ``PFG_GROUNDING_ENABLED`` is off).
    """
    try:
        if search_fn is None and not _env_flag("PFG_GROUNDING_ENABLED"):
            return []
        if local_context is None:
            return []
        from .pfg_local_extractor import extract_tags  # lazy: avoid import cycle
        tags = extract_tags(local_context, meta)
        if not tags:
            return []
        fn = search_fn or _get_search()
        if fn is None:
            return []
        return resolve_tags(tags, fn).get("check_tips", [])
    except Exception as exc:
        logger.debug("[pfg] ground_session skipped: %s", exc)
        return []
