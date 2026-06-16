"""Open Aura — local profile viewer, styled after the VibeLevel Aura profile page.

Read-only dashboard for the local-first OSS edition. It reads your scored
sessions straight from local Postgres (reusing the same `build_profile`
aggregation the MCP server uses — no scoring, no writes) and renders them with
the VibeLevel Aura look: a sidebar (Profile · Getting started · Leaderboard ·
your recent sessions), the hero score block, flip-able insight cards, dimension
bars, and a read-only pull of the hosted leaderboard. CTAs funnel to
vibelevel.ai to sign up, share, and get on the leaderboard.

Run as part of the stack (`docker compose up`) → http://localhost:3000, or
bare-metal: `streamlit run streamlit_app.py`.
"""
from __future__ import annotations

import asyncio
import html
import json
import os
import urllib.request
from string import Template

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from psycopg2.extras import RealDictCursor  # noqa: E402

from src.core.database_sync import get_conn_with_retry  # noqa: E402
from src.services.aura.aura_profile import build_profile  # noqa: E402

USER_ID = os.environ.get("AURA_LOCAL_USER_ID", "local")
SITE = os.environ.get("AURA_PUBLIC_WEB_URL", "https://vibelevel.ai").rstrip("/")
SIGNUP_URL = f"{SITE}/login?persona=builder&source=aura-oss"
LEADERBOARD_WEB = f"{SITE}/aura"
LEADERBOARD_API = os.environ.get("AURA_LEADERBOARD_API", f"{SITE}/api/aura/leaderboard")

LOGO_SVG = (
    '<svg viewBox="0 0 28 28" fill="none" width="26" height="26" style="flex-shrink:0">'
    '<path d="M14 2L16.5 10.5H25L18.25 15.5L20.75 24L14 19L7.25 24L9.75 15.5L3 10.5H11.5L14 2Z" fill="#00e676" opacity="0.15"/>'
    '<path d="M12.5 4L15 12H10L14 7L12.5 4Z" fill="#00e676"/>'
    '<path d="M10 13L7 22L14 17L10 13Z" fill="#00e676" opacity="0.7"/>'
    '<path d="M18 13L21 22L14 17L18 13Z" fill="#00e676" opacity="0.7"/></svg>'
)

DIM_ORDER = ["prompting", "ai_pairing", "product_thinking", "design_thinking", "human_contribution"]
DIM_LABELS = {
    "prompting": "PROMPTING", "ai_pairing": "AI COLLABORATION", "product_thinking": "PRODUCT THINKING",
    "design_thinking": "DESIGN SENSE", "human_contribution": "YOU VS AI",
}
SOURCE_LABELS = {
    "claude_code": "Claude Code", "cursor": "Cursor", "codex": "Codex", "windsurf": "Windsurf",
    "gemini_cli": "Gemini CLI", "vscode": "VS Code", "claude_desktop": "Claude Desktop",
    "claude_ai": "Claude", "chatgpt": "ChatGPT", "web": "Web",
}
# Short "what this measures" lines for the card flip-side (generic fallback below).
CARD_GUIDE = {
    "prompt_length": "Average words per prompt — terse directives vs. detailed context.",
    "redirect_rate": "How often you course-correct the AI mid-task.",
    "plan_ratio": "Share of sessions where you planned before building.",
    "time_of_day": "When your sessions tend to happen.",
    "politeness": "Pleasantries to the agent — purely for fun, not scored.",
    "token_footprint": "Total tokens exchanged — your session's footprint.",
    "human_token_share": "How much you wrote vs. the AI.",
    "tools_used": "The spread of tools you reached for.",
    "model_mix": "Which model you leaned on most.",
    "lifecycle": "Whether you took the work through to a shipped outcome.",
    "top_dimension": "Your strongest dimension this profile.",
    "go_to_phrase": "The phrase you open sessions with.",
    "signature": "Your signature move across sessions.",
    "growth_edge": "The dimension with the most room to grow.",
}

PALETTES = {
    "dark": {
        "bg": "#0a0e17", "hero": "rgba(13,18,30,0.97)", "card": "rgba(14,20,33,0.85)",
        "text": "#f0f2f5", "muted": "#8899aa", "accent": "#00e676",
        "border": "rgba(255,255,255,0.08)", "line": "rgba(139,146,184,0.14)",
        "chip_bg": "rgba(139,146,184,0.06)", "chip_bd": "rgba(139,146,184,0.18)",
        "track": "rgba(139,146,184,0.15)", "sidebar": "#0c111c", "shadow": "0 8px 40px rgba(0,0,0,0.45)",
        "pill_bg": "rgba(255,255,255,0.12)", "pill_bd": "rgba(255,255,255,0.35)", "glow": "rgba(255,255,255,0.05)",
        "green": "#00e676", "blue": "#7dd3fc", "amber": "#f59e0b", "red": "#ef4444", "gray": "#6b7280",
    },
    "light": {
        "bg": "#f4f7fb", "hero": "#ffffff", "card": "#ffffff",
        "text": "#0f1722", "muted": "#5b6b7d", "accent": "#0a6b34",
        "border": "#e2e8f0", "line": "#e8edf3",
        "chip_bg": "#eef2f7", "chip_bd": "#d8e0ea",
        "track": "#e2e8f0", "sidebar": "#ffffff", "shadow": "0 6px 22px rgba(20,40,80,0.07)",
        "pill_bg": "#eef2f7", "pill_bd": "#cfd9e6", "glow": "rgba(10,107,52,0.06)",
        "green": "#0a6b34", "blue": "#2b7fb0", "amber": "#b5730a", "red": "#c63333", "gray": "#8a97a6",
    },
}

CSS_TMPL = Template("""
<style>
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], #MainMenu, footer { display:none !important; }
[data-testid="stHeader"] { background:transparent !important; }
/* keep the sidebar collapse/expand control visible (the expand button lives in the header). */
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] { display:flex !important; visibility:visible !important; z-index:1000; }
[data-testid="stExpandSidebarButton"] button, [data-testid="stSidebarCollapseButton"] button { color:${muted} !important; }
.stApp, [data-testid="stAppViewContainer"] { background:${bg}; }
[data-testid="stMain"] .block-container, .block-container { max-width:100% !important; padding:0.9rem 2.2rem 3rem !important; }
.stApp, .block-container, p, span, div, h1, h2, h3 { color:${text}; }
a { text-decoration:none; }
button:focus, button:focus-visible, .stButton > button:focus, .stButton > button:active { outline:none !important; box-shadow:none !important; }
[data-testid="stSidebar"] { background:${sidebar}; border-right:1px solid ${border}; }
[data-testid="stSidebar"] .block-container { padding-top:0.9rem; }
[data-testid="stSidebar"] .stButton > button { background:transparent; color:${text}; border:none;
  border-radius:9px; font-size:13px; font-weight:600; text-align:left; justify-content:flex-start; padding:8px 12px; }
[data-testid="stSidebar"] .stButton > button:hover { background:${chip_bg}; color:${accent}; }
[data-testid="stSidebar"] .stButton > button[kind="primary"] { background:${accent}1f; color:${accent}; }

.vl-top { display:flex; align-items:center; justify-content:space-between; gap:1rem;
  padding:.2rem 0 .8rem; border-bottom:1px solid ${border}; margin-bottom:1.1rem; }
.vl-tt { font-size:15px; font-weight:600; color:${text}; }
.vl-tt .s { color:${muted}; font-weight:400; font-size:13px; margin-left:.5rem; }
.vl-ctas { display:flex; gap:.5rem; flex-shrink:0; }
.vl-btn { font-size:13px; font-weight:600; border-radius:8px; padding:8px 14px; white-space:nowrap; border:none; }
.vl-btn.primary { background:${accent}26; color:${accent}; }
.vl-btn.ghost { background:${chip_bg}; color:${text}; }

.vl-side-brand { display:flex; align-items:center; gap:.55rem; padding:.15rem .1rem .9rem; min-height:34px; }
.vl-wordmark { font-size:18px; font-weight:700; letter-spacing:-0.4px; color:${text}; }
.vl-wordmark em { font-style:normal; color:${accent}; }
.vl-pill { display:inline-flex; border:1px solid ${pill_bd}; background:${pill_bg}; border-radius:5px; padding:1px 5px;
  font-size:8px; font-weight:700; text-transform:uppercase; letter-spacing:.12em; color:${text}; }
.vl-side-h { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.14em; color:${muted};
  margin:1.1rem .2rem .5rem; }

.vl-hero { position:relative; overflow:hidden; border-radius:18px; border:1px solid ${border};
  background:${hero}; box-shadow:${shadow}; padding:1.7rem 1.7rem; display:flex; flex-wrap:wrap; gap:1.4rem 2.2rem; align-items:center; }
.vl-hero::before { content:""; position:absolute; right:-90px; top:-110px; height:300px; width:300px;
  border-radius:50%; background:${glow}; filter:blur(60px); pointer-events:none; }
.vl-id { display:flex; flex-direction:column; gap:.7rem; min-width:300px; flex:1 1 46%; }
.vl-id-row { display:flex; align-items:center; gap:.9rem; }
.vl-avatar { height:56px; width:56px; border-radius:13px; display:flex; align-items:center; justify-content:center;
  font-size:21px; font-weight:700; color:${accent}; border:1px solid ${accent}59; background:${accent}1a; flex-shrink:0; }
.vl-name { font-size:23px; font-weight:700; color:${text}; margin:0; line-height:1.1; }
.vl-handle { font-size:13px; color:${muted}; margin:3px 0 0; }
.vl-arch { font-size:15px; font-weight:600; color:${accent}; line-height:1.4; margin:.1rem 0 0; max-width:40rem; }
.vl-arch .t { font-weight:400; color:${muted}; }

.vl-score { display:flex; flex-direction:column; gap:.8rem; margin-left:auto; flex:1 1 440px; min-width:440px;
  border-left:1px solid ${line}; padding-left:2.2rem; }
.vl-score-row { display:flex; gap:2rem; flex-wrap:wrap; align-items:flex-start; }
.vl-slabel { font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.16em; color:${text}; }
.vl-snum { font-size:54px; font-weight:800; line-height:1; color:${accent}; letter-spacing:-1px; }
.vl-sden { font-size:24px; font-weight:600; color:${muted}; }
.vl-vdiv { width:1px; align-self:stretch; background:${line}; }
.vl-badges { display:flex; gap:.4rem; flex-wrap:wrap; margin-top:.3rem; }
.vl-badge { display:inline-flex; align-items:center; gap:5px; border-radius:999px; padding:5px 12px;
  font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
.vl-chips { display:grid; grid-template-columns:repeat(auto-fit,minmax(0,1fr)); gap:.5rem; }
.vl-chip { display:flex; justify-content:center; align-items:center; border-radius:7px; border:1px solid ${chip_bd};
  background:${chip_bg}; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.09em; color:${muted}; padding:7px 9px; text-align:center; }
.vl-publish { font-size:12px; color:${muted}; }
.vl-publish a { color:${accent}; font-weight:600; }

.vl-h2 { font-size:18px; font-weight:700; color:${text}; margin:1.7rem 0 .9rem; }
.vl-note { font-size:11px; color:${muted}; opacity:.9; margin-top:.9rem; }

.vl-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(244px,1fr)); gap:.85rem; }
.vl-flip { perspective:1300px; min-height:214px; }
.vl-inner { position:relative; width:100%; min-height:214px; transition:transform .55s; transform-style:preserve-3d; }
.vl-flip:hover .vl-inner { transform:rotateY(180deg); }
.vl-face { position:absolute; inset:0; -webkit-backface-visibility:hidden; backface-visibility:hidden;
  border-radius:13px; background:${card}; padding:15px 15px 16px; overflow:hidden; display:flex; flex-direction:column; }
.vl-back { transform:rotateY(180deg); gap:.45rem; }
.vl-ln { position:absolute; top:0; left:0; right:0; height:2px; }
.vl-cat { display:inline-flex; align-self:flex-start; border-radius:6px; padding:3px 8px; font-size:9px; font-weight:700;
  text-transform:uppercase; letter-spacing:.1em; }
.vl-q { font-size:11px; color:${muted}; margin:.65rem 0 .2rem; }
.vl-hl { font-size:16px; font-weight:700; color:${text}; line-height:1.25; margin:0 0 .35rem; }
.vl-dt { font-size:12.5px; color:${muted}; line-height:1.45; margin:0; }
.vl-mt { margin-top:auto; padding-top:.5rem; font-size:9px; color:${muted}; opacity:.8; text-transform:uppercase; letter-spacing:.1em; }

.vl-dims { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:.7rem; }
.vl-dim { border-radius:10px; border:1px solid ${line}; background:${card}; padding:13px 15px; }
.vl-dtop { display:flex; justify-content:space-between; align-items:center; }
.vl-dlabel { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.12em; color:${muted}; }
.vl-dscore { font-size:15px; font-weight:800; }
.vl-track { margin-top:11px; height:8px; border-radius:999px; background:${track}; overflow:hidden; }
.vl-fill { height:100%; border-radius:999px; }
.vl-tele { color:${accent}; font-size:10px; letter-spacing:.12em; text-transform:uppercase; font-weight:700; }
.vl-ug { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:11px; }
.vl-un { font-size:14px; font-weight:800; color:${text}; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.vl-ul { font-size:9px; color:${muted}; text-transform:uppercase; letter-spacing:.1em; margin-top:3px; }

.vl-lb { border-radius:12px; border:1px solid ${border}; background:${hero}; overflow:hidden; }
.vl-lr { display:flex; align-items:center; gap:1rem; padding:12px 16px; border-top:1px solid ${line}; }
.vl-lr:first-child { border-top:0; }
.vl-rank { width:34px; text-align:center; font-size:16px; font-weight:800; color:${muted}; flex-shrink:0; }
.vl-lname { font-size:14px; font-weight:600; color:${text}; margin:0; }
.vl-larch { font-size:11px; color:${muted}; margin:2px 0 0; }
.vl-lscore { margin-left:auto; font-size:18px; font-weight:800; flex-shrink:0; }

.vl-cta { border-radius:14px; border:1px solid ${border}; background:${card}; padding:1.9rem 1.6rem; text-align:center; margin-top:1.8rem; }
.vl-cta-t { font-size:21px; font-weight:700; color:${text}; margin:0 0 .45rem; }
.vl-cta-s { font-size:13.5px; color:${muted}; margin:0 auto 1.2rem; max-width:34rem; line-height:1.5; }
.vl-cta-b { display:inline-flex; align-items:center; gap:6px; border-radius:9px; border:none;
  background:${accent}26; color:${accent}; font-size:14px; font-weight:700; padding:11px 22px; }
.vl-gs { border-radius:14px; border:1px solid ${border}; background:${hero}; padding:1.6rem 1.8rem; box-shadow:${shadow}; }
.vl-gs h3 { font-size:16px; color:${text}; margin:1.2rem 0 .4rem; }
.vl-gs h3:first-child { margin-top:0; }
.vl-gs p, .vl-gs li { font-size:13.5px; color:${muted}; line-height:1.6; }
.vl-gs code { background:${chip_bg}; border:1px solid ${chip_bd}; border-radius:5px; padding:1px 6px; color:${accent}; font-size:12.5px; }
.vl-foot { margin-top:1.6rem; font-size:11px; color:${muted}; opacity:.7; text-align:center; }
</style>
""")


# ── helpers ──────────────────────────────────────────────────────────────────
def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def score_color(s: float) -> str:
    if s >= 8: return P["blue"]
    if s >= 7: return P["green"]
    if s >= 4: return P["amber"]
    return P["red"]


def level_color(level: str) -> str:
    return {"Emerging": P["gray"], "Capable": P["green"], "Strong": P["green"],
            "Exceptional": P["blue"]}.get(level, P["accent"])


def fmt_tokens(n) -> str:
    n = float(n or 0)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(int(n))


def initials(name: str) -> str:
    parts = [p for p in (name or "").strip().split() if p]
    if not parts: return "?"
    if len(parts) == 1: return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def pretty_source(src: str) -> str:
    return SOURCE_LABELS.get(src, (src or "").replace("_", " ")).upper()


def modality_chip(m: str) -> str:
    return "CODING" if m == "coding" else "WRITING"


def as_obj(v):
    if isinstance(v, str):
        try: return json.loads(v)
        except (ValueError, TypeError): return None
    return v


def render(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


# ── data ─────────────────────────────────────────────────────────────────────
def load_profile() -> dict:
    return asyncio.run(build_profile(USER_ID))


def load_session_detail(session_id: str) -> dict | None:
    pool = conn = None
    try:
        pool, conn = get_conn_with_retry()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT id, title, cards, dimension_scores FROM "AuraSession" '
                    "WHERE user_id = %s AND id = %s", (USER_ID, session_id))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        if conn and pool:
            pool.putconn(conn)


@st.cache_data(ttl=300, show_spinner=False)
def load_leaderboard(limit: int = 20) -> list:
    """Read-only pull of the hosted, PUBLIC Aura leaderboard. Sends no profile
    data — only a GET. Returns [] on any error (offline, blocked, etc.)."""
    url = f"{LEADERBOARD_API}?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "open-aura-viewer/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    if isinstance(data, list):
        return data
    return data.get("entries") or data.get("leaderboard") or []


# ── html builders ────────────────────────────────────────────────────────────
def badge(text: str, color: str, icon: str = "") -> str:
    pre = f"{icon} " if icon else ""
    return (f'<span class="vl-badge" style="color:{color};background:{color}1f;border:1px solid {color}66;">'
            f'{pre}{esc(text)}</span>')


def top_bar_html(title: str, subtitle: str = "") -> str:
    sub = f'<span class="s">{esc(subtitle)}</span>' if subtitle else ""
    return (
        '<div class="vl-top">'
        f'<div class="vl-tt">{esc(title)}{sub}</div>'
        '<div class="vl-ctas">'
        f'<a class="vl-btn ghost" href="{LEADERBOARD_WEB}" target="_blank">Leaderboard ↗</a>'
        f'<a class="vl-btn primary" href="{SIGNUP_URL}" target="_blank">Sign up ↗</a>'
        '</div></div>'
    )


def hero_html(p: dict) -> str:
    avg = float(p.get("aura_score") or 0)
    best = float(p.get("best_score") or 0)
    show_best = best > 0 and abs(best - avg) > 0.01
    sources = p.get("sources") or {}
    primary = max(sources, key=sources.get) if sources else None
    mods = {s.get("modality") for s in (p.get("sessions") or [])}
    overall_mod = ("CODING + WRITING" if "coding" in mods and (mods - {"coding"})
                   else "CODING" if "coding" in mods else "WRITING" if mods else None)
    total_tokens = (p.get("stats") or {}).get("total_tokens") or 0

    handle = p.get("handle")
    handle_html = (f'<p class="vl-handle">{SITE.split("//")[-1]}/u/{esc(handle)}</p>' if handle
                   else '<p class="vl-handle">local profile · not yet published</p>')
    arch = esc(p.get("archetype") or "")
    tag = p.get("archetype_tagline")
    arch_html = (f'<p class="vl-arch">{arch}'
                 + (f'<span class="t"> — {esc(tag)}</span>' if tag else "") + '</p>') if arch else ""

    badges = ""
    lvl = p.get("aura_level")
    if lvl: badges += badge(lvl, level_color(lvl))
    if p.get("ships_it"): badges += badge("Ships it", P["green"], icon="🚀")

    best_block = ""
    if show_best:
        bl = p.get("best_level")
        best_block = (
            '<div class="vl-vdiv"></div>'
            '<div style="display:flex;flex-direction:column;gap:.5rem;">'
            '<span class="vl-slabel">Best session</span>'
            f'<div><span class="vl-snum">{best:.1f}</span><span class="vl-sden">/10</span></div>'
            + (f'<div class="vl-badges">{badge(bl, level_color(bl))}</div>' if bl else "") + '</div>'
        )

    chips = [f'{p.get("session_count", 0)} SESSION{"" if p.get("session_count")==1 else "S"}']
    if primary: chips.append(pretty_source(primary))
    if overall_mod: chips.append(overall_mod)
    if total_tokens > 0: chips.append(f"{fmt_tokens(total_tokens)} TOKENS")
    chips_html = "".join(f'<span class="vl-chip">{esc(c)}</span>' for c in chips)

    return (
        '<div class="vl-hero">'
        '<div class="vl-id">'
        '<div class="vl-id-row">'
        f'<div class="vl-avatar">{esc(initials(p.get("display_name") or ""))}</div>'
        f'<div style="min-width:0;"><p class="vl-name">{esc(p.get("display_name") or "Builder")}</p>{handle_html}</div>'
        '</div>'
        f'{arch_html}</div>'
        '<div class="vl-score">'
        '<div class="vl-score-row">'
        '<div style="display:flex;flex-direction:column;gap:.5rem;">'
        '<span class="vl-slabel">Avg of all sessions</span>'
        f'<div><span class="vl-snum">{avg:.1f}</span><span class="vl-sden">/10</span></div>'
        f'<div class="vl-badges">{badges}</div></div>'
        f'{best_block}</div>'
        f'<div class="vl-chips">{chips_html}</div>'
        f'<div class="vl-publish">🔗 <a href="{SIGNUP_URL}" target="_blank">Publish &amp; share on vibelevel.ai →</a></div>'
        '</div></div>'
    )


def session_hero_html(s: dict, tokens: int = 0) -> str:
    score = float(s.get("aura_score") or 0)
    badges = badge(s.get("aura_level"), level_color(s.get("aura_level"))) if s.get("aura_level") else ""
    if s.get("ships_it"): badges += badge("Ships it", P["green"], icon="🚀")
    chips = [x for x in ((s.get("created_at") or "")[:10], pretty_source(s.get("source")),
                         modality_chip(s.get("modality")), f"{fmt_tokens(tokens)} TOKENS" if tokens else "") if x]
    chips_html = "".join(f'<span class="vl-chip">{esc(c)}</span>' for c in chips)
    arch = esc(s.get("archetype") or "")
    return (
        '<div class="vl-hero">'
        '<div class="vl-id">'
        f'<p class="vl-name" style="font-size:19px;">{esc(s.get("title") or "Untitled session")}</p>'
        + (f'<p class="vl-arch" style="margin-top:.3rem;">{arch}</p>' if arch else "") +
        '</div>'
        '<div class="vl-score">'
        '<div class="vl-score-row"><div style="display:flex;flex-direction:column;gap:.5rem;">'
        '<span class="vl-slabel">Session score</span>'
        f'<div><span class="vl-snum">{score:.1f}</span><span class="vl-sden">/10</span></div>'
        f'<div class="vl-badges">{badges}</div></div></div>'
        f'<div class="vl-chips">{chips_html}</div>'
        '</div></div>'
    )


KLASS = {"credibility": (lambda: P["green"], "Behavioral", "how you steer, plan & verify"),
         "personality": (lambda: P["blue"], "Personality", "your style & habits")}


def insight_card_html(c: dict) -> str:
    if not (c.get("headline") or c.get("detail")):
        return ""
    acc_fn, label, klass_meaning = KLASS.get(c.get("klass"), (lambda: P["accent"], "Insight", "a signal from your session"))
    accent = acc_fn()
    mod = c.get("modality")
    modtag = "CODING" if mod == "coding" else "WRITING" if mod == "noncoding" else "BOTH"
    q = f'<p class="vl-q">{esc(c["question"])}</p>' if c.get("question") else ""
    dt = f'<p class="vl-dt">{esc(c["detail"])}</p>' if c.get("detail") else ""
    guide = CARD_GUIDE.get(c.get("id"), "Derived from your session's telemetry &amp; transcript signals — no rubric, no test cases.")
    front = (
        f'<div class="vl-face" style="border:1px solid {accent}33;">'
        f'<div class="vl-ln" style="background:linear-gradient(90deg,{accent}00,{accent}99,{accent}00);"></div>'
        f'<span class="vl-cat" style="color:{accent};background:{accent}1f;border:1px solid {accent}59;">{label}</span>'
        f'{q}<p class="vl-hl">{esc(c.get("headline") or "")}</p>{dt}'
        f'<div class="vl-mt">{modtag} · hover to flip ↻</div></div>'
    )
    back = (
        f'<div class="vl-face vl-back" style="border:1px solid {accent}59;background:{accent}0f;">'
        f'<span class="vl-cat" style="color:{accent};background:{accent}1f;border:1px solid {accent}59;">What this measures</span>'
        f'<p class="vl-hl" style="font-size:14px;">{esc(c.get("headline") or "")}</p>'
        f'<p class="vl-dt">{guide}</p>'
        f'<div class="vl-mt">{esc(label)} — {esc(klass_meaning)}</div></div>'
    )
    return f'<div class="vl-flip"><div class="vl-inner">{front}{back}</div></div>'


def insights_grid_html(cards: list) -> str:
    items = "".join(insight_card_html(c) for c in cards if c.get("id") != "archetype")
    if not items:
        return '<div class="vl-dim" style="text-align:center;color:#8899aa;">No insights yet.</div>'
    return f'<div class="vl-grid">{items}</div>'


def dim_bar_html(label: str, score: float) -> str:
    c = score_color(score)
    return (
        '<div class="vl-dim"><div class="vl-dtop">'
        f'<span class="vl-dlabel">{esc(label)}</span><span class="vl-dscore" style="color:{c}">{score:.1f}</span></div>'
        f'<div class="vl-track"><div class="vl-fill" style="width:{max(0,min(100,score*10))}%;background:{c}"></div></div></div>'
    )


def usage_tile_html(stats: dict) -> str:
    return (
        '<div class="vl-dim"><div class="vl-dtop"><span class="vl-dlabel">Usage</span><span class="vl-tele">Telemetry</span></div>'
        '<div class="vl-ug">'
        f'<div><div class="vl-un">{fmt_tokens(stats.get("avg_tokens_per_session"))}</div><div class="vl-ul">tok/session</div></div>'
        f'<div><div class="vl-un">{float(stats.get("avg_prompts_per_session") or 0):.1f}</div><div class="vl-ul">prompts/sn</div></div>'
        f'<div><div class="vl-un">{esc(stats.get("top_model") or "—")}</div><div class="vl-ul">model</div></div>'
        '</div></div>'
    )


def dims_grid_html(dim_scores: dict, stats: dict | None) -> str:
    rows = "".join(dim_bar_html(DIM_LABELS.get(k, k.replace("_", " ").title()), float(dim_scores[k].get("score") or 0))
                   for k in DIM_ORDER if dim_scores.get(k) is not None)
    rows += "".join(dim_bar_html(DIM_LABELS.get(k, k.replace("_", " ").title()), float((v or {}).get("score") or 0))
                    for k, v in dim_scores.items() if k not in DIM_ORDER)
    if not rows:
        return '<div class="vl-dim" style="text-align:center;color:#8899aa;">No dimension scores yet.</div>'
    if stats:
        rows += usage_tile_html(stats)
    return f'<div class="vl-dims">{rows}</div>'


def cta_html(title: str, sub: str) -> str:
    return (
        '<div class="vl-cta">'
        f'<p class="vl-cta-t">{esc(title)}</p><p class="vl-cta-s">{esc(sub)}</p>'
        f'<a class="vl-cta-b" href="{SIGNUP_URL}" target="_blank">Reveal your Aura on vibelevel.ai →</a></div>'
    )


def leaderboard_html(entries: list) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    rows = ""
    for e in entries:
        rank = e.get("rank") or 0
        name = e.get("handle") or e.get("display_name") or "—"
        score = float(e.get("aura_score") or e.get("avg_aura_score") or 0)
        href = f'{SITE}/u/{e.get("handle")}' if e.get("handle") else SITE
        sub = " · ".join(x for x in [esc(e.get("archetype") or ""),
              f'{e.get("session_count")} sessions' if e.get("session_count") else ""] if x)
        rows += (
            '<div class="vl-lr">'
            f'<div class="vl-rank">{medals.get(rank, rank)}</div>'
            f'<div style="min-width:0;flex:1;"><a class="vl-lname" href="{href}" target="_blank">{esc(name)}</a>'
            f'<p class="vl-larch">{sub}</p></div>'
            f'<span class="vl-lscore" style="color:{level_color(e.get("aura_level"))}">{score:.1f}</span></div>'
        )
    return f'<div class="vl-lb">{rows}</div>'


GETTING_STARTED = (
    '<div class="vl-gs">'
    '<h3>1 · Start the stack</h3>'
    '<p><code>docker compose up</code> — Postgres + the app (MCP server on <code>:8090</code>, this viewer on <code>:3000</code>). '
    'Set one provider key in <code>.env</code> (e.g. <code>GROQ_API_KEY</code>) so scoring can run.</p>'
    '<h3>2 · Connect your agent</h3>'
    '<p>Point your MCP client (Claude Code, Cursor, Claude Desktop…) at the local server — no auth in local mode:</p>'
    '<p><code>{ "mcpServers": { "aura": { "url": "http://localhost:8090/mcp" } } }</code></p>'
    '<h3>3 · Score a session</h3>'
    '<p>After a real piece of work, ask your agent: <b>“score this session with Aura.”</b> '
    'It sends a redacted evidence packet (truncated excerpts + file metadata — never raw code) and your profile appears here.</p>'
    '<h3>4 · Go public (optional)</h3>'
    '<p>This Aura lives only on your machine. Sign up at VibeLevel to claim a handle, share your profile, '
    'and get on the leaderboard.</p>'
    '</div>'
)


# ── page ─────────────────────────────────────────────────────────────────────
_ICON = "assets/aura-logo.svg"
st.set_page_config(page_title="Open Aura", page_icon=_ICON if os.path.exists(_ICON) else "✨",
                   layout="wide", initial_sidebar_state="expanded")

ss = st.session_state
ss.setdefault("view", "profile")
ss.setdefault("session_id", None)
ss.setdefault("theme", "dark")

try:
    profile = load_profile()
except Exception as e:  # noqa: BLE001
    P = PALETTES["dark"]
    render(CSS_TMPL.substitute(P))
    st.error(f"Couldn't load your profile from local Postgres: {e}")
    st.caption("Is the database up and POSTGRES_URL set? In Docker: `docker compose up`.")
    st.stop()

sessions = profile.get("sessions") or []

# ── sidebar (sets view / session / theme before CSS is chosen) ──
with st.sidebar:
    render('<div class="vl-side-brand">' + LOGO_SVG
           + '<span class="vl-wordmark">Vibe<em>Level</em></span><span class="vl-pill">Aura</span></div>')
    if st.button(("☀️  Light mode" if ss.theme == "dark" else "🌙  Dark mode"), key="theme_btn", use_container_width=True):
        ss.theme = "light" if ss.theme == "dark" else "dark"
        st.rerun()
    render('<div class="vl-side-h">Navigate</div>')
    for label, view in [("📊  Profile", "profile"), ("🚀  Getting started", "getting_started"), ("🏆  Leaderboard", "leaderboard")]:
        if st.button(label, key=f"nav_{view}", use_container_width=True,
                     type="primary" if ss.view == view else "secondary"):
            ss.view, ss.session_id = view, None
    if sessions:
        render('<div class="vl-side-h">Recent sessions</div>')
        for s in sessions[:12]:
            lab = f'{(s.get("created_at") or "")[:10]} · {(s.get("title") or "Untitled")[:26]}'
            if st.button(lab, key=f"sess_{s['id']}", use_container_width=True,
                         type="primary" if (ss.view == "session" and ss.session_id == s["id"]) else "secondary"):
                ss.view, ss.session_id = "session", s["id"]

P = PALETTES.get(ss.theme, PALETTES["dark"])
render(CSS_TMPL.substitute(P))

# ── main ──
if ss.view == "getting_started":
    render(top_bar_html("Getting started", "Connect an agent and score your first session"))
    render(GETTING_STARTED)
    render(cta_html("Get on the leaderboard",
                    "Sign up at VibeLevel to claim a handle, share your profile, and rank against other builders."))

elif ss.view == "leaderboard":
    render(top_bar_html("Aura leaderboard", "Live, read-only — top builders on VibeLevel"))
    try:
        entries = load_leaderboard(20)
    except Exception:
        entries = None
    if entries:
        render(leaderboard_html(entries))
    elif entries == []:
        render('<div class="vl-dim" style="text-align:center;color:#8899aa;">The leaderboard is empty right now.</div>')
    else:
        render('<div class="vl-dim" style="text-align:center;color:#8899aa;">'
               'Couldn\'t reach the live leaderboard from here. It lives at vibelevel.ai.</div>')
    render(cta_html("Join the leaderboard",
                    "This profile is local. Publish your Aura on VibeLevel to appear here and rank against other builders."))

elif ss.view == "session" and ss.session_id:
    summary = next((s for s in sessions if s["id"] == ss.session_id), None)
    detail = load_session_detail(ss.session_id) if summary else None
    if not summary or not detail:
        render(top_bar_html("Session", ""))
        st.info("That session couldn't be loaded. Pick another from the sidebar.")
    else:
        cards = as_obj(detail.get("cards")) or []
        tokens = next((c.get("stat", {}).get("tokens", 0) for c in cards if c.get("id") == "token_footprint"), 0)
        render(top_bar_html("Session report", summary.get("title") or ""))
        render(session_hero_html(summary, tokens))
        dims = as_obj(detail.get("dimension_scores")) or {}
        if dims:
            render('<div class="vl-h2">Dimensions</div>')
            render(dims_grid_html(dims, None))
        render('<div class="vl-h2">Insights</div>')
        render(insights_grid_html(cards))

else:  # profile
    if int(profile.get("session_count") or 0) == 0:
        render(top_bar_html("Your Aura", "No scored sessions yet"))
        render('<div class="vl-hero" style="display:block;text-align:center;">'
               '<div class="vl-avatar" style="margin:0 auto .9rem;">?</div>'
               '<p class="vl-name">No Aura yet</p>'
               '<p class="vl-arch" style="max-width:none;margin-top:.5rem;"><span class="t">Connect your agent to the Aura MCP '
               'server (<code>http://localhost:8090/mcp</code>) and ask it to “score this session with Aura.”</span></p></div>')
        render(cta_html("Get on the leaderboard",
                        "Sign up at VibeLevel to claim a handle, share your profile, and rank against other builders."))
    else:
        render(top_bar_html("Your Aura", "How you work with AI, from your real sessions"))
        render(hero_html(profile))
        render('<div class="vl-h2">Insights</div>')
        render(insights_grid_html(profile.get("cards") or []))
        render('<p class="vl-note">Behavioral (green) = how you steer, plan &amp; verify · '
               'Personality (ice blue) = style &amp; habits · hover a card to flip it</p>')
        render('<div class="vl-h2">Dimensions</div>')
        render(dims_grid_html(profile.get("dimension_scores") or {}, profile.get("stats")))

render('<div class="vl-foot">Open Aura · local, read-only viewer — nothing is scored or written here.</div>')
