"""Open Aura — REST endpoints for the web viewer (profile · session · leaderboard).

Mounted at ``/api/aura``; the Next.js viewer consumes them. Open Aura is
local single-user, so there's no auth — every request is the single local user.
Reuses only the vendored Aura services (``build_profile`` etc.).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request

from fastapi import APIRouter, HTTPException, Query
from psycopg2.extras import RealDictCursor

from ..aura_mcp.local_auth import LOCAL_USER_ID
from ..core.database_sync import get_conn_with_retry
from ..services.aura.aura_profile import aura_share_title, build_profile
from ..services.aura.aura_signal_extractor import _archetype_tagline

logger = logging.getLogger(__name__)
router = APIRouter(tags=["aura"])

# The viewer's Leaderboard tab is a read-only pull of the PUBLIC hosted
# leaderboard. Configurable; sends no data.
_LEADERBOARD_UPSTREAM = os.environ.get(
    "AURA_LEADERBOARD_UPSTREAM",
    os.environ.get("AURA_PUBLIC_WEB_URL", "https://vibelevel.ai").rstrip("/") + "/api/aura/leaderboard",
)


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _session_payload(row: dict) -> dict:
    dimension_scores = row.get("dimension_scores")
    if not isinstance(dimension_scores, dict):
        dimension_scores = {}
    cards = row.get("cards")
    if not isinstance(cards, list):
        cards = []
    return {
        "id": str(row["id"]),
        "source": row.get("source") or "",
        "modality": row.get("modality") or "",
        "aura_score": _to_float(row.get("aura_score")) or 0.0,
        "aura_level": row.get("aura_level") or "",
        "archetype": row.get("archetype") or "",
        "dimension_scores": dimension_scores,
        "cards": cards,
        "human_contribution_label": row.get("human_contribution_label") or "",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
    }


# ── profiles ──────────────────────────────────────────────────────────────────
@router.get("/me/profile")
async def get_my_profile():
    """The local user's Aura profile."""
    try:
        return await build_profile(LOCAL_USER_ID)
    except ValueError as e:  # build_profile raises if the user row is missing
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/profile/{handle}")
async def get_public_profile(handle: str):
    """Public Aura profile by handle. Mostly 404s in the local edition (no
    handles), kept for contract parity with the hosted API."""
    pool = conn = None
    try:
        pool, conn = get_conn_with_retry()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT id, aura_visibility FROM "User" WHERE LOWER(aura_handle) = LOWER(%s)', (handle,))
        row = cur.fetchone()
        cur.close()
    finally:
        if conn and pool:
            pool.putconn(conn)
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found.")
    if (row.get("aura_visibility") or "private") != "public":
        raise HTTPException(status_code=403, detail="This Aura profile is private.")
    profile = await build_profile(str(row["id"]))
    # Automatically inferred identity, workspace, toolkit, and project facts are
    # local-owner evidence. They require an explicit hosted publication flow
    # before becoming public and must never leak through this compatibility URL.
    profile.pop("profile_facts", None)
    profile.pop("toolkit", None)
    profile.pop("projects", None)
    for s in profile.get("sessions", []):
        s["title"] = s.get("share_title") or s.get("title")
    return profile


# ── sessions ──────────────────────────────────────────────────────────────────
@router.get("/session/{session_id}")
async def get_session_detail(session_id: str):
    """One Aura session's detail (its cards + dimensions), for the local user."""
    user_id = LOCAL_USER_ID
    pool = conn = None
    try:
        pool, conn = get_conn_with_retry()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, title, source, modality, aura_score, aura_level, archetype,
                   dimension_scores, cards, human_contribution_label, created_at
            FROM "AuraSession"
            WHERE id = %s AND user_id = %s
            """,
            (session_id, user_id),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        if conn and pool:
            pool.putconn(conn)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found.")
    payload = _session_payload(row)
    payload["title"] = row.get("title") or "Untitled session"
    return payload


@router.get("/session/{session_id}/public")
async def get_session_public(session_id: str):
    """One scored session by id — PUBLIC (unguessable-link sharing, any visibility)."""
    pool = conn = None
    try:
        pool, conn = get_conn_with_retry()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT s.id, s.title, s.source, s.modality, s.aura_score, s.aura_level,
                   s.archetype, s.dimension_scores, s.cards, s.human_contribution_label,
                   s.created_at, u.display_name, u."firstName", u."lastName",
                   u.aura_handle, u.aura_visibility
            FROM "AuraSession" s
            JOIN "User" u ON s.user_id = u.id
            WHERE s.id = %s AND s.status = 'scored'
            """,
            (session_id,),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        if conn and pool:
            pool.putconn(conn)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found.")
    payload = _session_payload(row)
    # Public surface: generic non-revealing label, never the real title.
    payload["title"] = aura_share_title(row.get("modality"), row.get("created_at"), row["id"])
    payload["archetype_tagline"] = (
        _archetype_tagline(row.get("modality") or "coding", row["archetype"]) if row.get("archetype") else ""
    )
    payload["display_name"] = (
        row.get("display_name")
        or f"{row.get('firstName') or ''} {row.get('lastName') or ''}".strip()
        or "A VibeLevel builder"
    )
    payload["owner_handle"] = (
        (row.get("aura_handle") or "") if (row.get("aura_visibility") or "private") == "public" else ""
    )
    return payload


# ── leaderboard (read-only pull of the public hosted leaderboard) ─────────────
@router.get("/leaderboard")
async def get_leaderboard(limit: int = Query(default=20, ge=1, le=100)):
    """Read-only pull of the PUBLIC hosted Aura leaderboard. Sends no user data;
    returns [] if the upstream is unreachable (offline edition still works)."""
    url = f"{_LEADERBOARD_UPSTREAM}?limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "open-aura/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return data if isinstance(data, list) else (data.get("entries") or data.get("leaderboard") or [])
    except Exception as e:  # noqa: BLE001 — never fatal; the viewer shows a fallback
        logger.warning("[Aura] leaderboard upstream unavailable: %s", e)
        return []
