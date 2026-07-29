"""Pure sanitization and evidence-weighted profile-fact aggregation."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlsplit


SCALAR_FACT_KEYS = ("headline", "location", "experience", "availability")
SOURCE_WEIGHTS = {"measured": 1.0, "inferred": 0.7}
_SECRET_MARKERS = ("api_key", "apikey", "secret", "token=", "password", "bearer ")
_GITHUB_OWNER_RE = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"
)
_GITHUB_REPOSITORY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _clean_label(value: Any, *, limit: int = 80) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned or len(cleaned) > limit:
        return None
    lowered = cleaned.casefold()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return None
    return cleaned


def sanitize_repository_name(value: Any) -> str | None:
    """Return only a safe repository basename, never a local path or remote."""
    cleaned = _clean_label(value, limit=500)
    if not cleaned:
        return None
    normalized = cleaned.replace("\\", "/").rstrip("/")
    if ":" in normalized and normalized.startswith("git@"):
        normalized = normalized.split(":", 1)[1]
    name = normalized.rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", name):
        return None
    return name


def sanitize_github_repository_url(value: Any) -> str | None:
    """Return a canonical GitHub repository root for a supported remote."""
    cleaned = _clean_label(value, limit=500)
    if not cleaned:
        return None

    if cleaned.startswith("git@github.com:"):
        repository_path = cleaned.removeprefix("git@github.com:")
    else:
        try:
            parsed = urlsplit(cleaned)
            port = parsed.port
        except ValueError:
            return None
        if (
            parsed.scheme not in {"https", "ssh"}
            or (parsed.hostname or "").casefold() != "github.com"
            or port is not None
            or parsed.query
            or parsed.fragment
        ):
            return None
        if parsed.scheme == "https" and (parsed.username or parsed.password):
            return None
        if parsed.scheme == "ssh" and (
            parsed.username != "git" or parsed.password is not None
        ):
            return None
        repository_path = parsed.path.lstrip("/")

    repository_path = repository_path.rstrip("/")
    parts = repository_path.split("/")
    if len(parts) != 2:
        return None
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not _GITHUB_OWNER_RE.fullmatch(owner):
        return None
    if not _GITHUB_REPOSITORY_RE.fullmatch(repository):
        return None
    return f"https://github.com/{owner.casefold()}/{repository.casefold()}"


def sanitize_mcp_name(value: Any) -> str | None:
    """Keep a display name only; reject URLs, paths, and configuration values."""
    cleaned = _clean_label(value, limit=60)
    if not cleaned or "://" in cleaned or "=" in cleaned:
        return None
    if "/" in cleaned or "\\" in cleaned or "@" in cleaned:
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._+-]{0,59}", cleaned):
        return None
    return cleaned


def sanitize_summary(value: Any) -> str | None:
    """Return a short redacted description or None when it looks secret-like."""
    return _clean_label(value, limit=240)


def normalize_inferred_profile_facts(value: Any) -> dict[str, dict[str, Any]]:
    """Validate the scoring model's scalar facts before local persistence."""
    raw = _dict(value)
    normalized: dict[str, dict[str, Any]] = {}
    for key in SCALAR_FACT_KEYS:
        payload = _dict(raw.get(key))
        fact_value = _clean_label(payload.get("value"), limit=160)
        if not fact_value:
            continue
        try:
            confidence = max(0.0, min(float(payload.get("confidence", 0)), 1.0))
        except (TypeError, ValueError):
            continue
        evidence = _clean_label(payload.get("evidence"), limit=240) or ""
        normalized[key] = {
            "value": fact_value,
            "confidence": confidence,
            "source": "inferred",
            "evidence": evidence,
        }
    return normalized


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recency_weight(created_at: Any, now: datetime) -> float:
    parsed = _parse_timestamp(created_at)
    if parsed is None:
        return 0.75
    age_days = max(0.0, (now - parsed).total_seconds() / 86400)
    return 1.0 - min(age_days, 365.0) * (0.25 / 365.0)


def _sorted_counts(counts: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _iter_string_values(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key in value:
            if isinstance(key, str):
                yield key
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


def aggregate_profile_facts(
    rows: list[dict[str, Any]], *, now: datetime | None = None
) -> dict[str, Any]:
    """Aggregate optional legacy/new session rows into stable profile sections."""
    safe_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    scalar_candidates: dict[str, dict[str, dict[str, Any]]] = {
        key: {} for key in SCALAR_FACT_KEYS
    }
    source_counts: dict[str, int] = defaultdict(int)
    model_counts: dict[str, int] = defaultdict(int)
    tool_counts: dict[str, int] = defaultdict(int)
    skill_counts: dict[str, int] = defaultdict(int)
    mcp_counts: dict[str, int] = defaultdict(int)
    projects: dict[str, dict[str, Any]] = {}

    for row in rows:
        evidence = _dict(row.get("evidence"))
        telemetry = _dict(row.get("telemetry"))
        facts = _dict(telemetry.get("profile_facts"))
        recency = _recency_weight(row.get("created_at"), safe_now)

        for key in SCALAR_FACT_KEYS:
            payload = _dict(facts.get(key))
            value = _clean_label(payload.get("value"), limit=160)
            if not value:
                continue
            try:
                confidence = max(0.0, min(float(payload.get("confidence", 0)), 1.0))
            except (TypeError, ValueError):
                continue
            fact_source = str(payload.get("source") or "inferred").casefold()
            source_weight = SOURCE_WEIGHTS.get(fact_source, SOURCE_WEIGHTS["inferred"])
            canonical = value.casefold()
            candidate = scalar_candidates[key].setdefault(
                canonical,
                {
                    "value": value,
                    "weight": 0.0,
                    "confidence_total": 0.0,
                    "observations": 0,
                    "source": fact_source,
                },
            )
            candidate["weight"] += confidence * source_weight * recency
            candidate["confidence_total"] += confidence
            candidate["observations"] += 1
            if source_weight > SOURCE_WEIGHTS.get(candidate["source"], 0.0):
                candidate["source"] = fact_source

        source = _clean_label(row.get("source") or evidence.get("source"), limit=60)
        if source:
            source_counts[source] += 1
        model = _clean_label(evidence.get("model"), limit=100)
        if model:
            model_counts[model] += 1

        local_stats = _dict(evidence.get("local_stats"))
        tools = local_stats.get("tools_used")
        if isinstance(tools, dict):
            for raw_name, raw_count in tools.items():
                name = _clean_label(raw_name, limit=60)
                if not name:
                    continue
                try:
                    count = max(0, int(raw_count))
                except (TypeError, ValueError):
                    continue
                tool_counts[name] += count
        elif isinstance(tools, list):
            for raw_name in tools:
                name = _clean_label(raw_name, limit=60)
                if name:
                    tool_counts[name] += 1

        for raw_name in _iter_string_values(local_stats.get("skills_used")):
            name = _clean_label(raw_name, limit=80)
            if name:
                skill_counts[name] += 1

        workspace = _dict(evidence.get("workspace_context"))
        for raw_name in _iter_string_values(workspace.get("mcp_servers")):
            name = sanitize_mcp_name(raw_name)
            if name:
                mcp_counts[name] += 1

        repository = sanitize_repository_name(workspace.get("repository"))
        if repository:
            canonical = repository.casefold()
            project = projects.setdefault(
                canonical,
                {
                    "name": repository,
                    "summaries": [],
                    "scores": [],
                    "github_urls": set(),
                    "session_count": 0,
                },
            )
            project["session_count"] += 1
            repository_url = sanitize_github_repository_url(
                workspace.get("repository_url")
            )
            if repository_url:
                project["github_urls"].add(repository_url)
            summary = sanitize_summary(workspace.get("project_summary"))
            if summary:
                project["summaries"].append(summary)
            try:
                project["scores"].append(float(row.get("aura_score")))
            except (TypeError, ValueError):
                pass

    aggregated_scalars: dict[str, Any] = {}
    for key, candidates in scalar_candidates.items():
        if not candidates:
            continue
        winner = sorted(
            candidates.values(),
            key=lambda candidate: (-candidate["weight"], candidate["value"]),
        )[0]
        aggregated_scalars[key] = {
            "value": winner["value"],
            "confidence": round(
                winner["confidence_total"] / winner["observations"], 2
            ),
            "source": winner["source"],
            "observations": winner["observations"],
        }

    toolkit: dict[str, Any] = {}
    if source_counts:
        toolkit["sources"] = dict(sorted(source_counts.items()))
    if model_counts:
        toolkit["models"] = dict(sorted(model_counts.items()))
    if tool_counts:
        toolkit["tools"] = _sorted_counts(tool_counts)
    if skill_counts:
        toolkit["skills"] = _sorted_counts(skill_counts)
    if mcp_counts:
        toolkit["mcp_servers"] = _sorted_counts(mcp_counts)

    project_list: list[dict[str, Any]] = []
    for project in projects.values():
        scores = project.pop("scores")
        summaries = project.pop("summaries")
        github_urls = project.pop("github_urls")
        if summaries:
            project["summary"] = summaries[0]
        if len(github_urls) == 1:
            project["github_url"] = next(iter(github_urls))
        project["aura_score"] = (
            round(sum(scores) / len(scores), 2) if scores else 0.0
        )
        project_list.append(project)
    project_list.sort(key=lambda project: (-project["session_count"], project["name"]))

    return {
        "profile_facts": aggregated_scalars,
        "toolkit": toolkit,
        "projects": project_list,
    }
