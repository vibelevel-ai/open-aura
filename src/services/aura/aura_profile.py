"""VibeLevel Aura — profile aggregation (read side).

Aggregates a user's scored `"AuraSession"` rows into the `ProfileResponse`
shape (contracts.py).

Reuses only platform infra — the DB pool (`database_sync.get_conn_with_retry`)
and the Aura model/signal helpers.
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from ...core.database_sync import get_conn_with_retry
from .aura_model_coding import get_aura_label
from .aura_signal_extractor import (
    assign_archetype,
    build_overall_cards,
    _archetype_tagline,
    _coerce_evidence,
    _session_telemetry,
    session_tokens,
)
from .contracts import (
    Card,
    DimensionScore,
    ProfileResponse,
    SessionSummary,
    WhoAmIResponse,
)
from .aura_profile_facts import aggregate_profile_facts


# ─── shared-session label (PUBLIC surfaces only) ─────────────────────────────
# A generic, NON-REVEALING title for shared session/profile links. Derived ONLY
# from enum-like inputs — modality + the session's time-of-day + a stable hash of
# its id — never the real title, prompts, or files, so it can't leak what the
# work actually was. Fully deterministic + stable per session (a shared link's
# label never changes). No agent input, no LLM: there's nothing to trust.
_SHARE_NOUNS = {
    "coding": ["coding session", "build session", "dev sprint", "pairing session", "hack session"],
    "noncoding": ["writing session", "drafting session", "writing sprint", "research session"],
}


def _share_hour(created_at: Any) -> Optional[int]:
    """Hour-of-day from a datetime or ISO string; None if unparseable."""
    if not created_at:
        return None
    if isinstance(created_at, str):
        try:
            return datetime.fromisoformat(created_at.replace("Z", "+00:00")).hour
        except ValueError:
            return None
    return getattr(created_at, "hour", None)


def _time_of_day(hour: Optional[int]) -> Optional[str]:
    if hour is None:
        return None
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "late-night"


def aura_share_title(modality: Any, created_at: Any, session_id: Any) -> str:
    """Generic, non-revealing label for a SHARED session (public surfaces only).

    e.g. "An evening build session", "A late-night writing session". Built only
    from modality + time-of-day + a stable id hash — never the real title — so
    public links convey vibe without exposing what the work was.
    """
    key = "noncoding" if str(modality or "").lower() == "noncoding" else "coding"
    nouns = _SHARE_NOUNS[key]
    digest = int(hashlib.md5(str(session_id).encode()).hexdigest(), 16)
    noun = nouns[digest % len(nouns)]
    tod = _time_of_day(_share_hour(created_at))
    if tod:
        article = "An" if tod[0] in "aeiou" else "A"
        return f"{article} {tod} {noun}"
    return f"A {noun}"

logger = logging.getLogger(__name__)

# Base URL for the public web profile (`/u/<handle>`). The MCP host differs from
# the web host, so whoami returns a fully-qualified web URL the agent can show.
AURA_WEB_BASE = os.getenv("AURA_PUBLIC_WEB_URL", "https://vibelevel.ai").rstrip("/")


def _display_name_from_row(row: dict[str, Any]) -> str:
    """Shown name: display_name → 'First L.' → first → 'Anonymous'."""
    display_name = row.get("display_name")
    if display_name and str(display_name).strip():
        return str(display_name).strip()
    first = (row.get("firstName") or "").strip()
    last = (row.get("lastName") or "").strip()
    if first and last:
        return f"{first} {last[0]}."
    if first:
        return first
    return "Anonymous"


def _to_float(value: Any) -> Optional[float]:
    """psycopg2 returns NUMERIC as Decimal; normalise to float (or None)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _aura_level_for(score: Optional[float]) -> Optional[str]:
    """Map an aggregate Aura score to its band, clamped defensively.

    `get_aura_label` raises outside [0, 10.01); an averaged score should
    always be in range, but clamp so aggregation never 500s on a stray value.
    """
    if score is None:
        return None
    clamped = max(0.0, min(score, 10.0))
    try:
        return get_aura_label(clamped)
    except ValueError:
        logger.warning("[Aura] Could not map score %s to a level band", score)
        return None


def _average_dimension_scores(
    rows: list[dict[str, Any]],
) -> dict[str, DimensionScore]:
    """Average each dimension's score across the user's scored sessions.

    Each row's `dimension_scores` is `{dim_key: {score, reasoning}}` (JSONB).
    We average the numeric `score` per dim over the sessions that contain it;
    the aggregate `reasoning` notes how many sessions fed the average (the
    per-session reasoning lives on each SessionSummary's source rows).
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}

    for row in rows:
        dims = row.get("dimension_scores") or {}
        if not isinstance(dims, dict):
            continue
        for dim_key, payload in dims.items():
            if not isinstance(payload, dict):
                continue
            score = _to_float(payload.get("score"))
            if score is None:
                continue
            sums[dim_key] = sums.get(dim_key, 0.0) + score
            counts[dim_key] = counts.get(dim_key, 0) + 1

    averaged: dict[str, DimensionScore] = {}
    for dim_key, total in sums.items():
        n = counts[dim_key]
        avg = round(total / n, 2)
        averaged[dim_key] = DimensionScore(
            score=avg,
            reasoning=f"Averaged across {n} scored session{'s' if n != 1 else ''}.",
        )
    return averaged


def _ships_it(cards: Any) -> bool:
    """True when the session's lifecycle card marks the work as shipped/delivered
    (deploy for coding, document delivered for writing). Safe on missing cards."""
    if not isinstance(cards, list):
        return False
    for c in cards:
        if isinstance(c, dict) and c.get("id") == "lifecycle":
            stat = c.get("stat")
            if isinstance(stat, dict):
                return bool(stat.get("ships_it"))
    return False


def _session_summary(row: dict[str, Any]) -> SessionSummary:
    return SessionSummary(
        id=str(row["id"]),
        title=row.get("title") or "Untitled session",
        share_title=aura_share_title(row.get("modality"), row.get("created_at"), row.get("id")),
        source=row.get("source") or "",
        modality=row.get("modality") or "",
        aura_score=_to_float(row.get("aura_score")) or 0.0,
        aura_level=row.get("aura_level") or "",
        archetype=row.get("archetype") or "",
        created_at=row["created_at"].isoformat() if row.get("created_at") else "",
        ships_it=_ships_it(row.get("cards")),
    )


def _dominant_modality(rows: list[dict[str, Any]]) -> str:
    """Most common modality across the user's sessions (default 'coding').

    Drives archetype assignment + overall card selection, which are
    modality-specific.
    """
    counts: dict[str, int] = {}
    for row in rows:
        m = row.get("modality")
        if m:
            counts[m] = counts.get(m, 0) + 1
    if not counts:
        return "coding"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _aggregate_telemetry(
    rows: list[dict[str, Any]], modality: str
) -> dict[str, Any]:
    """Merge deterministic per-session telemetry into one overall dict.

    The signal extractor's `assign_archetype` reads a telemetry dict to break
    ties between archetypes (worth far less than dimension coverage). We OR the
    boolean habit signals across sessions and keep the first present dict-valued
    signal so `_active_signal_ids` registers them. Best-effort: a bad evidence
    row is skipped, and on total failure we return `{}` (archetype then ranks
    purely on dimension scores).
    """
    agg: dict[str, Any] = {}
    bool_keys = ("planned", "verified", "revised")
    dict_keys = ("time_of_day", "prompt_length", "politeness", "redirect_rate")
    max_parallel = 0

    for row in rows:
        ev = _coerce_evidence(row.get("evidence"))
        if ev is None:
            continue
        try:
            tel = _session_telemetry(ev, modality)
        except Exception:
            continue
        for k in bool_keys:
            if tel.get(k):
                agg[k] = True
        for k in dict_keys:
            if tel.get(k) and k not in agg:
                agg[k] = tel[k]
        pa = tel.get("parallel_agents")
        if isinstance(pa, (int, float)) and pa:
            max_parallel = max(max_parallel, int(pa))

    if max_parallel:
        agg["parallel_agents"] = max_parallel
    return agg


def _empty_stats() -> dict[str, Any]:
    """Zeroed usage-telemetry block for the no-sessions profile branch."""
    return {
        "avg_tokens_per_session": 0.0,
        "avg_prompts_per_session": 0.0,
        "top_model": None,
        "total_tokens": 0,
    }


def _compute_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Usage telemetry (NOT a 0-10 score) aggregated from session evidence.

    Reads each row's `evidence` JSONB defensively (may come back as a dict or a
    JSON string) via the shared `_coerce_evidence` packet coercion, then reuses
    the signal extractor's `session_tokens` (the agent's MEASURED local_stats
    counts when supplied, else the per-turn estimate) so the stats chip and the
    token_footprint card never disagree.

    Returns:
      - avg_tokens_per_session: mean over sessions of summed turn tokens (rounded int-ish float).
      - avg_prompts_per_session: mean over sessions of the count of role=='user' turns (1dp).
      - top_model: most-common `evidence.model` across sessions (or None).
      - total_tokens: int sum of turn tokens across all sessions.
    """
    per_session_tokens: list[int] = []
    per_session_prompts: list[int] = []
    model_counts: dict[str, int] = {}

    for row in rows:
        ev = _coerce_evidence(row.get("evidence"))
        if ev is None:
            continue
        per_session_tokens.append(session_tokens(ev)["total"])
        per_session_prompts.append(sum(1 for t in ev.turns if t.role == "user"))
        model = (ev.model or "").strip()
        if model:
            model_counts[model] = model_counts.get(model, 0) + 1

    if not per_session_tokens:
        return _empty_stats()

    n = len(per_session_tokens)
    total_tokens = sum(per_session_tokens)
    avg_tokens = round(total_tokens / n)
    avg_prompts = round(sum(per_session_prompts) / n, 1)
    top_model = (
        max(model_counts.items(), key=lambda kv: kv[1])[0] if model_counts else None
    )

    return {
        "avg_tokens_per_session": float(avg_tokens),
        "avg_prompts_per_session": float(avg_prompts),
        "top_model": top_model,
        "total_tokens": int(total_tokens),
    }


async def whoami_summary(user_id: str) -> WhoAmIResponse:
    """Lightweight identity + connection check for the MCP ``whoami`` tool.

    Cheaper than ``build_profile`` (no per-session aggregation): just the identity
    row from "User" plus a scored-session count. Used to confirm the agent is
    connected and to greet the user by name.
    """
    pool = None
    conn = None
    try:
        pool, conn = get_conn_with_retry()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT aura_handle, aura_visibility, email,
                   display_name, "firstName", "lastName"
            FROM "User"
            WHERE id = %s
            """,
            (user_id,),
        )
        user_row = cur.fetchone()
        if not user_row:
            cur.close()
            raise ValueError(f"User {user_id} not found")

        cur.execute(
            'SELECT COUNT(*) AS n FROM "AuraSession" '
            "WHERE user_id = %s AND status = 'scored'",
            (user_id,),
        )
        count_row = cur.fetchone()
        cur.close()

        handle = user_row.get("aura_handle") or ""
        visibility = user_row.get("aura_visibility") or "private"
        session_count = int(count_row["n"]) if count_row else 0
        # Always hand back a website link to funnel the user in: their public
        # profile when it's shareable, otherwise their own Aura dashboard (where
        # they can claim a handle / go public). whoami deliberately returns NO
        # scores — the score, archetype and cards live on the web.
        profile_url = (
            f"{AURA_WEB_BASE}/u/{handle}"
            if handle and visibility == "public"
            else f"{AURA_WEB_BASE}/aura"
        )
        return WhoAmIResponse(
            connected=True,
            handle=handle,
            display_name=_display_name_from_row(user_row),
            email=user_row.get("email") or "",
            visibility=visibility,
            session_count=session_count,
            profile_url=profile_url,
        )
    finally:
        if conn and pool:
            pool.putconn(conn)


def _compute_dimension_trends(rows: list[dict], n: int = 10) -> dict[str, list[float]]:
    """Per-dimension score series over the last `n` sessions (oldest→newest), for
    inline sparklines. `rows` are newest-first."""
    recent = list(reversed(rows[:n]))
    trends: dict[str, list[float]] = {}
    for r in recent:
        ds = r.get("dimension_scores") or {}
        if not isinstance(ds, dict):
            continue
        for k, v in ds.items():
            score = _to_float(v.get("score") if isinstance(v, dict) else v)
            if score is not None:
                trends.setdefault(k, []).append(round(score, 1))
    return trends


def _compute_benchmarks(rows: list[dict]) -> dict:
    """Personal-relative benchmarks from the user's OWN history — no
    cross-user data. `rows` are newest-first (created_at DESC)."""
    from datetime import datetime, timedelta, timezone

    pairs: list[tuple] = []
    for r in rows:
        s = _to_float(r.get("aura_score"))
        if s is not None:
            pairs.append((r.get("created_at"), s))
    if not pairs:
        return {}

    latest_t, latest = pairs[0]
    now = latest_t if isinstance(latest_t, datetime) else datetime.now(timezone.utc)

    def _norm(t):
        """Coerce a row timestamp to the same aware/naive-ness as `now`."""
        if not isinstance(t, datetime):
            return None
        if t.tzinfo is None and now.tzinfo is not None:
            return t.replace(tzinfo=now.tzinfo)
        if t.tzinfo is not None and now.tzinfo is None:
            return t.replace(tzinfo=None)
        return t

    out: dict = {"this_session_score": round(latest, 2)}

    cutoff = now - timedelta(days=30)
    last30 = [s for t, s in pairs if (nt := _norm(t)) is not None and nt >= cutoff]
    if last30:
        avg30 = sum(last30) / len(last30)
        out["thirty_day_avg"] = round(avg30, 2)
        out["vs_30d_avg"] = round(latest - avg30, 2)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month = [s for t, s in pairs if (nt := _norm(t)) is not None and nt >= month_start]
    if len(month) >= 2:
        below = sum(1 for s in month if s <= latest)
        out["month_percentile"] = round(100 * below / len(month))

    weeks: dict[tuple, list[float]] = {}
    for t, s in pairs:
        nt = _norm(t)
        if nt is None:
            continue
        iso = nt.isocalendar()
        weeks.setdefault((iso[0], iso[1]), []).append(s)
    best = None
    for (yr, wk), vals in weeks.items():
        avg = sum(vals) / len(vals)
        if best is None or avg > best[0]:
            try:
                mon = datetime.fromisocalendar(yr, wk, 1)
                sun = mon + timedelta(days=6)
                label = (
                    f"{mon.strftime('%b')} {mon.day}–{sun.day}"
                    if mon.month == sun.month
                    else f"{mon.strftime('%b %d')}–{sun.strftime('%b %d')}"
                )
            except Exception:
                label = f"{yr}-W{wk:02d}"
            best = (avg, label)
    if best:
        out["best_week"] = {"avg": round(best[0], 1), "label": best[1]}

    return out


async def build_profile(user_id: str) -> ProfileResponse:
    """Aggregate a user's scored Aura sessions into a ProfileResponse.

    - overall aura_score  = avg of per-session aura_score
    - dimension_scores    = per-dimension average across sessions
    - archetype           = assign_archetype over the aggregated dims
    - cards               = build_overall_cards over the sessions
    - sources             = {source: count}
    - sessions            = newest-first SessionSummary list

    Identity (handle / display_name / visibility) is read from "User".
    Returns a profile with `session_count=0` and empty aggregates if the
    user has no scored sessions yet (the identity row still resolves).
    """
    pool = None
    conn = None
    try:
        pool, conn = get_conn_with_retry()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Identity from "User" (handle/visibility are the additive Aura columns).
        cur.execute(
            """
            SELECT id, aura_handle, aura_visibility,
                   display_name, "firstName", "lastName",
                   COALESCE(aura_likes_count, 0) AS aura_likes_count
            FROM "User"
            WHERE id = %s
            """,
            (user_id,),
        )
        user_row = cur.fetchone()
        if not user_row:
            cur.close()
            raise ValueError(f"User {user_id} not found")

        # Scored sessions, newest first.
        cur.execute(
            """
            SELECT id, source, modality, title, aura_score, aura_level,
                   dimension_scores, archetype, cards, evidence, telemetry,
                   created_at
            FROM "AuraSession"
            WHERE user_id = %s AND status = 'scored'
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        cur.close()

        handle = user_row.get("aura_handle") or ""
        visibility = user_row.get("aura_visibility") or "private"
        display_name = _display_name_from_row(user_row)
        like_count = int(user_row.get("aura_likes_count") or 0)

        if not rows:
            return ProfileResponse(
                handle=handle,
                display_name=display_name,
                visibility=visibility,
                aura_score=0.0,
                aura_level="",
                best_score=0.0,
                best_level="",
                archetype="",
                archetype_tagline="",
                dimension_scores={},
                cards=[],
                session_count=0,
                like_count=like_count,
                sources={},
                sessions=[],
                stats=_empty_stats(),
                benchmarks={},
                dimension_trends={},
                ships_it=False,
                profile_facts={},
                toolkit={},
                projects=[],
            )

        # Overall aura_score = mean of per-session scores.
        per_session_scores = [
            s for s in (_to_float(r.get("aura_score")) for r in rows) if s is not None
        ]
        overall_score = (
            round(sum(per_session_scores) / len(per_session_scores), 2)
            if per_session_scores
            else 0.0
        )
        overall_level = _aura_level_for(overall_score) or ""

        # Best single-session score + its level. Derived on read (cheap — rows are
        # already loaded) rather than denormalized: session scores are mutable via
        # re-score/upsert, so a stored best would need a full re-scan on every
        # upsert anyway. Mirrors how the average is computed.
        best_score = (
            round(max(per_session_scores), 2) if per_session_scores else 0.0
        )
        best_level = _aura_level_for(best_score) or ""

        dimension_scores = _average_dimension_scores(rows)
        modality = _dominant_modality(rows)

        # Archetype over aggregated dims, with telemetry merged across sessions
        # for tiebreaking (assign_archetype expects a telemetry DICT, not rows).
        # assign_archetype returns the archetype NAME (e.g. "The Vibe Coder");
        # we look up its evocative tagline from the matching model catalog.
        try:
            telemetry = _aggregate_telemetry(rows, modality)
            archetype = assign_archetype(dimension_scores, telemetry, modality) or ""
        except Exception as e:  # archetype is best-effort, never fatal
            logger.warning("[Aura] assign_archetype failed for %s: %s", user_id, e)
            archetype = ""
        archetype_tagline = _archetype_tagline(modality, archetype) if archetype else ""

        try:
            cards: list[Card] = build_overall_cards(rows, modality) or []
        except Exception as e:  # cards are best-effort, never fatal
            logger.warning("[Aura] build_overall_cards failed for %s: %s", user_id, e)
            cards = []

        sources: dict[str, int] = {}
        for r in rows:
            src = r.get("source") or "unknown"
            sources[src] = sources.get(src, 0) + 1

        sessions = [_session_summary(r) for r in rows]
        # Overall "Ships it" flag for the hero badge — true when the user takes
        # the majority of their sessions through to a shipped/delivered outcome.
        ship_n = sum(1 for s in sessions if s.get("ships_it"))
        overall_ships_it = bool(rows) and ship_n * 2 >= len(rows)

        # Usage telemetry (token/prompt stats) — a profile-level summary, NOT a
        # 0-10 score. Best-effort: never fatal to profile aggregation.
        try:
            stats = _compute_stats(rows)
        except Exception as e:
            logger.warning("[Aura] _compute_stats failed for %s: %s", user_id, e)
            stats = _empty_stats()

        # Personal benchmarks + per-dimension trend series. Both
        # best-effort: never fatal to profile aggregation.
        try:
            benchmarks = _compute_benchmarks(rows)
        except Exception as e:
            logger.warning("[Aura] _compute_benchmarks failed for %s: %s", user_id, e)
            benchmarks = {}
        try:
            dimension_trends = _compute_dimension_trends(rows)
        except Exception as e:
            logger.warning("[Aura] _compute_dimension_trends failed for %s: %s", user_id, e)
            dimension_trends = {}

        try:
            profile_sections = aggregate_profile_facts(rows)
        except Exception as e:
            logger.warning(
                "[Aura] aggregate_profile_facts failed for %s: %s", user_id, e
            )
            profile_sections = {
                "profile_facts": {},
                "toolkit": {},
                "projects": [],
            }


        return ProfileResponse(
            handle=handle,
            display_name=display_name,
            visibility=visibility,
            aura_score=overall_score,
            aura_level=overall_level,
            best_score=best_score,
            best_level=best_level,
            archetype=archetype,
            archetype_tagline=archetype_tagline,
            dimension_scores=dimension_scores,
            cards=cards,
            session_count=len(rows),
            like_count=like_count,
            sources=sources,
            sessions=sessions,
            stats=stats,
            benchmarks=benchmarks,
            dimension_trends=dimension_trends,
            ships_it=overall_ships_it,
            profile_facts=profile_sections["profile_facts"],
            toolkit=profile_sections["toolkit"],
            projects=profile_sections["projects"],
        )
    finally:
        if conn and pool:
            pool.putconn(conn)
