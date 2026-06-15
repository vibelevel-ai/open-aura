"""Open Aura — local, read-only profile viewer.

A lightweight Streamlit dashboard for the local-first OSS edition: it reads your
scored sessions straight from local Postgres and shows your Aura profile, the
per-dimension scores, your insight cards, and a session-by-session breakdown.

It REUSES the same aggregation the MCP server uses (`build_profile`), so the
numbers here always match what your agent sees — no scoring or writes happen
here. Opt-in: run it with `docker compose --profile ui up` (or, bare-metal,
`streamlit run streamlit_app.py`).
"""
from __future__ import annotations

import asyncio
import json
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # bare-metal runs pick up .env; in Docker the env is already set.

from psycopg2.extras import RealDictCursor  # noqa: E402

from src.core.database_sync import get_conn_with_retry  # noqa: E402
from src.services.aura.aura_profile import build_profile  # noqa: E402

USER_ID = os.environ.get("AURA_LOCAL_USER_ID", "local")

# Friendly labels for the score dimensions; unknown keys fall back to title-case
# so writing-modality (or future) dimensions still render.
DIM_LABELS = {
    "prompting": "Prompting",
    "ai_pairing": "AI Collaboration",
    "design_thinking": "Design Thinking",
    "product_thinking": "Product Thinking",
    "human_contribution": "Human Contribution",
}


def _dim_label(key: str) -> str:
    return DIM_LABELS.get(key, key.replace("_", " ").title())


def _as_obj(value):
    """JSONB columns come back parsed by psycopg2, but tolerate a raw string."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    return value


def load_profile() -> dict:
    return asyncio.run(build_profile(USER_ID))


def load_session_detail(session_id: str) -> dict | None:
    """Per-session cards + dimension reasoning aren't in the profile feed, so read
    the single AuraSession row directly (read-only)."""
    pool = None
    conn = None
    try:
        pool, conn = get_conn_with_retry()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, title, source, modality, aura_score, aura_level, archetype,
                   dimension_scores, cards, human_contribution_label,
                   engagement_level, created_at
            FROM "AuraSession"
            WHERE user_id = %s AND id = %s
            """,
            (USER_ID, session_id),
        )
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        if conn and pool:
            pool.putconn(conn)


def render_dimensions(dim_scores: dict, show_reasoning: bool = False) -> None:
    if not dim_scores:
        return
    for key, val in dim_scores.items():
        score = float((val or {}).get("score") or 0)
        st.progress(min(score / 10.0, 1.0), text=f"{_dim_label(key)} — {score:g}/10")
        if show_reasoning:
            reasoning = (val or {}).get("reasoning")
            if reasoning:
                st.caption(reasoning)


def render_cards(cards: list, columns: int = 2) -> None:
    cards = [c for c in (cards or []) if c.get("headline") or c.get("detail")]
    if not cards:
        st.caption("No cards for this view.")
        return
    cols = st.columns(columns)
    for i, card in enumerate(cards):
        with cols[i % columns].container(border=True):
            st.markdown(f"**{card.get('headline', '')}**")
            if card.get("detail"):
                st.write(card["detail"])
            if card.get("growth_nudge"):
                st.caption(f"💡 {card['growth_nudge']}")


# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Open Aura", page_icon="✨", layout="centered")

top = st.container()
with top:
    left, right = st.columns([4, 1])
    left.title("✨ Open Aura")
    if right.button("↻ Refresh", use_container_width=True):
        st.rerun()

try:
    profile = load_profile()
except Exception as e:  # noqa: BLE001 — surface DB/config errors plainly
    st.error(f"Couldn't load your profile from local Postgres: {e}")
    st.caption("Is the database up and POSTGRES_URL set? In Docker: `docker compose --profile ui up`.")
    st.stop()

display_name = profile.get("display_name") or "Local Builder"
session_count = int(profile.get("session_count") or 0)

if session_count == 0:
    st.subheader(display_name)
    st.info(
        "No scored sessions yet. Connect your agent to the Aura MCP server "
        "(`http://localhost:8090/mcp`) and ask it to **“score this session with "
        "Aura.”** Your profile will appear here."
    )
    st.stop()

# Header -------------------------------------------------------------------- #
st.subheader(display_name)
archetype = profile.get("archetype")
if archetype:
    line = f"**{archetype}**"
    if profile.get("archetype_tagline"):
        line += f" — {profile['archetype_tagline']}"
    st.markdown(line)

m1, m2, m3 = st.columns(3)
m1.metric("Aura score", f"{profile.get('aura_score', 0):g}", profile.get("aura_level") or None)
m2.metric("Best session", f"{profile.get('best_score', 0):g}", profile.get("best_level") or None)
m3.metric("Sessions", session_count)

st.divider()

# Dimensions ---------------------------------------------------------------- #
st.subheader("Dimensions")
st.caption("Averaged across all scored sessions.")
render_dimensions(profile.get("dimension_scores") or {})

# Overall insight cards ----------------------------------------------------- #
overall_cards = [c for c in (profile.get("cards") or []) if c.get("id") != "archetype"]
if overall_cards:
    st.subheader("Your insight cards")
    render_cards(overall_cards)

st.divider()

# Sessions ------------------------------------------------------------------ #
st.subheader("Sessions")
sessions = profile.get("sessions") or []

table = [
    {
        "Date": (s.get("created_at") or "")[:10],
        "Session": s.get("title") or s.get("share_title") or "(untitled)",
        "Score": s.get("aura_score"),
        "Level": s.get("aura_level"),
        "Archetype": s.get("archetype"),
        "Ships": "✓" if s.get("ships_it") else "",
    }
    for s in sessions
]
st.dataframe(table, use_container_width=True, hide_index=True)

if sessions:
    def _label(s: dict) -> str:
        return f"{(s.get('created_at') or '')[:10]} · {s.get('title') or s.get('share_title') or s.get('id')}"

    chosen = st.selectbox("Open a session", sessions, format_func=_label)
    if chosen:
        detail = load_session_detail(chosen["id"])
        if not detail:
            st.warning("Couldn't load that session.")
        else:
            d1, d2, d3 = st.columns(3)
            d1.metric("Score", f"{detail.get('aura_score', 0):g}", detail.get("aura_level") or None)
            d2.metric("Archetype", detail.get("archetype") or "—")
            d3.metric("Engagement", detail.get("engagement_level") or "—")

            dims = _as_obj(detail.get("dimension_scores")) or {}
            if dims:
                st.markdown("**Dimension breakdown**")
                render_dimensions(dims, show_reasoning=True)

            cards = _as_obj(detail.get("cards")) or []
            st.markdown("**Session cards**")
            render_cards(cards)

st.divider()
st.caption("Open Aura · local, read-only viewer — nothing is scored or written here.")
