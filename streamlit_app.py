"""Open Aura — local profile viewer, styled after the VibeLevel Aura profile page.

A read-only dashboard for the local-first OSS edition. It reads your scored
sessions straight from local Postgres (reusing the same `build_profile`
aggregation the MCP server uses — no scoring, no writes) and renders them with
the VibeLevel Aura look: the hero score block, insight cards, dimension bars,
and a session feed. CTAs funnel to vibelevel.ai to sign up, share, and get on
the leaderboard — none of which the local edition does on its own.

Run as part of the stack (`docker compose up`) → http://localhost:3000, or
bare-metal: `streamlit run streamlit_app.py`.
"""
from __future__ import annotations

import asyncio
import html
import json
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from psycopg2.extras import RealDictCursor  # noqa: E402

from src.core.database_sync import get_conn_with_retry  # noqa: E402
from src.services.aura.aura_profile import build_profile  # noqa: E402

USER_ID = os.environ.get("AURA_LOCAL_USER_ID", "local")

# Funnel targets — the local edition has no account/leaderboard of its own.
SITE = os.environ.get("AURA_PUBLIC_WEB_URL", "https://vibelevel.ai").rstrip("/")
SIGNUP_URL = f"{SITE}/login?persona=builder&source=aura-oss"
LEADERBOARD_URL = f"{SITE}/aura"

# Palette (lifted from the frontend's --vibecoder-* theme).
ACCENT = "#00e676"
BLUE = "#7dd3fc"
AMBER = "#f59e0b"
RED = "#ef4444"
MUTED = "#8899aa"

LEVEL_COLORS = {"Emerging": "#6b7280", "Capable": ACCENT, "Strong": ACCENT, "Exceptional": BLUE}

DIM_ORDER = ["prompting", "ai_pairing", "product_thinking", "design_thinking", "human_contribution"]
DIM_LABELS = {
    "prompting": "PROMPTING",
    "ai_pairing": "AI COLLABORATION",
    "product_thinking": "PRODUCT THINKING",
    "design_thinking": "DESIGN SENSE",
    "human_contribution": "YOU VS AI",
}
SOURCE_LABELS = {
    "claude_code": "Claude Code", "cursor": "Cursor", "codex": "Codex",
    "windsurf": "Windsurf", "gemini_cli": "Gemini CLI", "vscode": "VS Code",
    "claude_desktop": "Claude Desktop", "claude_ai": "Claude", "chatgpt": "ChatGPT", "web": "Web",
}

LOGO_SVG = (
    '<svg viewBox="0 0 28 28" fill="none" width="26" height="26" style="flex-shrink:0">'
    '<path d="M14 2L16.5 10.5H25L18.25 15.5L20.75 24L14 19L7.25 24L9.75 15.5L3 10.5H11.5L14 2Z" fill="#00e676" opacity="0.15"/>'
    '<path d="M12.5 4L15 12H10L14 7L12.5 4Z" fill="#00e676"/>'
    '<path d="M10 13L7 22L14 17L10 13Z" fill="#00e676" opacity="0.7"/>'
    '<path d="M18 13L21 22L14 17L18 13Z" fill="#00e676" opacity="0.7"/></svg>'
)

CSS = """
<style>
header[data-testid="stHeader"], [data-testid="stToolbar"] { display:none !important; }
#MainMenu, footer { visibility:hidden; }
.stApp { background:#0a0e17; }
.block-container { max-width:1140px; padding:1rem 1.25rem 4rem; }
:root { --vlm: ui-monospace,'SF Mono',Menlo,Consolas,monospace; }
a { text-decoration:none; }

.vl-top { display:flex; align-items:center; justify-content:space-between; gap:1rem;
  padding:.7rem .25rem 1rem; border-bottom:1px solid rgba(255,255,255,0.07); margin-bottom:1.4rem; }
.vl-brand { display:flex; align-items:center; gap:.6rem; min-width:0; }
.vl-wordmark { font-size:20px; font-weight:700; letter-spacing:-0.5px; color:#f0f2f5; }
.vl-wordmark em { font-style:normal; color:#00e676; }
.vl-pill { display:inline-flex; align-items:center; border:1px solid rgba(255,255,255,0.35);
  background:rgba(255,255,255,0.12); border-radius:6px; padding:2px 6px; font-size:9px; font-weight:700;
  text-transform:uppercase; letter-spacing:.12em; color:#fff; }
.vl-desc { color:#8899aa; font-size:12.5px; margin-left:.55rem; }
@media (max-width:880px){ .vl-desc{ display:none; } }
.vl-ctas { display:flex; gap:.5rem; flex-shrink:0; }
.vl-btn { font-family:var(--vlm); font-size:13px; font-weight:600; border-radius:8px; padding:8px 14px;
  border:1px solid rgba(255,255,255,0.30); white-space:nowrap; }
.vl-btn.ghost { background:rgba(255,255,255,0.06); color:#cdd6e0; }
.vl-btn.ghost:hover { background:rgba(255,255,255,0.12); }
.vl-btn.primary { background:rgba(0,230,118,0.15); border-color:rgba(0,230,118,0.5); color:#00e676; }
.vl-btn.primary:hover { background:rgba(0,230,118,0.25); }

.vl-hero { position:relative; overflow:hidden; border-radius:18px; border:1px solid rgba(255,255,255,0.08);
  background:rgba(13,18,30,0.97); box-shadow:0 8px 40px rgba(0,0,0,0.45); padding:1.7rem 1.6rem;
  display:flex; flex-wrap:wrap; gap:1.4rem 2rem; align-items:center; }
.vl-hero::before { content:""; position:absolute; right:-90px; top:-110px; height:300px; width:300px;
  border-radius:50%; background:rgba(255,255,255,0.05); filter:blur(60px); pointer-events:none; }
.vl-id { display:flex; flex-direction:column; gap:.7rem; min-width:240px; flex:1; }
.vl-id-row { display:flex; align-items:center; gap:.9rem; }
.vl-avatar { height:54px; width:54px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-family:var(--vlm); font-size:20px; font-weight:700; color:#00e676;
  border:1px solid rgba(0,230,118,0.35); background:rgba(0,230,118,0.10); flex-shrink:0; }
.vl-name { font-size:22px; font-weight:700; color:#fff; margin:0; line-height:1.1; }
.vl-handle { font-family:var(--vlm); font-size:13px; color:#8899aa; margin:3px 0 0; }
.vl-arch { font-size:15px; font-weight:600; color:#00e676; line-height:1.35; margin:.1rem 0 0; max-width:34rem; }
.vl-arch .t { font-weight:400; color:#8899aa; }

.vl-score { display:flex; flex-direction:column; gap:.7rem; margin-left:auto;
  border-left:1px solid rgba(139,146,184,0.12); padding-left:2rem; }
@media (max-width:760px){ .vl-score{ border-left:0; padding-left:0; margin-left:0; } }
.vl-score-row { display:flex; gap:1.6rem; flex-wrap:wrap; align-items:flex-start; }
.vl-slabel { font-family:var(--vlm); font-size:12px; font-weight:600; text-transform:uppercase;
  letter-spacing:.16em; color:#fff; }
.vl-snum { font-family:var(--vlm); font-size:46px; font-weight:700; line-height:1; color:#00e676; }
.vl-sden { font-family:var(--vlm); font-size:22px; font-weight:600; color:#8899aa; }
.vl-vdiv { width:1px; align-self:stretch; background:rgba(139,146,184,0.18); }
.vl-badges { display:flex; gap:.4rem; flex-wrap:wrap; margin-top:.3rem; }
.vl-badge { display:inline-flex; align-items:center; gap:5px; border-radius:999px; padding:4px 11px;
  font-family:var(--vlm); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.04em; }
.vl-chips { display:grid; grid-template-columns:repeat(auto-fit,minmax(0,1fr)); gap:.5rem; }
.vl-chip { display:flex; justify-content:center; align-items:center; border-radius:7px;
  border:1px solid rgba(139,146,184,0.18); background:rgba(139,146,184,0.06); font-family:var(--vlm);
  font-size:11px; font-weight:500; text-transform:uppercase; letter-spacing:.1em; color:#8899aa; padding:6px 9px; }
.vl-publish { font-family:var(--vlm); font-size:12px; color:#8899aa; }
.vl-publish a { color:#00e676; }

.vl-h2 { font-size:18px; font-weight:600; color:#f0f2f5; margin:1.8rem 0 .9rem; }
.vl-note { font-family:var(--vlm); font-size:11px; color:#8899aa; opacity:.85; margin-top:.9rem; }

.vl-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(232px,1fr)); gap:.8rem; }
.vl-card { border-radius:13px; background:rgba(14,20,33,0.85); padding:15px 15px 16px; position:relative; overflow:hidden; }
.vl-card .ln { position:absolute; top:0; left:0; right:0; height:2px; }
.vl-cat { display:inline-flex; align-items:center; border-radius:6px; padding:3px 8px; font-family:var(--vlm);
  font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:.1em; }
.vl-q { font-family:var(--vlm); font-size:11px; color:#8899aa; margin:.7rem 0 .2rem; }
.vl-hl { font-size:16px; font-weight:700; color:#fff; line-height:1.25; margin:0 0 .35rem; }
.vl-dt { font-size:12.5px; color:#9aa7b6; line-height:1.45; margin:0; }
.vl-mt { margin-top:.7rem; font-family:var(--vlm); font-size:9px; color:#6b7787; text-transform:uppercase; letter-spacing:.1em; }

.vl-dims { display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:.7rem; }
.vl-dim { border-radius:10px; border:1px solid rgba(139,146,184,0.12); background:rgba(139,146,184,0.03); padding:13px 14px; }
.vl-dtop { display:flex; justify-content:space-between; align-items:center; }
.vl-dlabel { font-family:var(--vlm); font-size:11px; font-weight:500; text-transform:uppercase; letter-spacing:.12em; color:#8899aa; }
.vl-dscore { font-family:var(--vlm); font-size:14px; font-weight:700; }
.vl-track { margin-top:11px; height:8px; border-radius:999px; background:rgba(139,146,184,0.15); overflow:hidden; }
.vl-fill { height:100%; border-radius:999px; }
.vl-tele { color:#00e676; font-family:var(--vlm); font-size:10px; letter-spacing:.12em; text-transform:uppercase; }
.vl-ug { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:11px; }
.vl-un { font-family:var(--vlm); font-size:14px; font-weight:700; color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.vl-ul { font-family:var(--vlm); font-size:9px; color:#8899aa; text-transform:uppercase; letter-spacing:.1em; margin-top:3px; }

.vl-srow { display:flex; align-items:center; gap:.85rem; border-radius:12px; border:1px solid rgba(255,255,255,0.07);
  background:rgba(14,20,33,0.85); padding:11px 14px; margin-bottom:.5rem; }
.vl-sicon { height:32px; width:32px; border-radius:9px; display:flex; align-items:center; justify-content:center;
  border:1px solid rgba(139,146,184,0.18); background:rgba(0,230,118,0.08); color:#00e676; font-size:13px;
  font-family:var(--vlm); flex-shrink:0; }
.vl-stitle { font-size:13.5px; font-weight:500; color:#e6ebf1; margin:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.vl-schips { display:flex; gap:6px; flex-wrap:wrap; margin-top:6px; }
.vl-sscore { margin-left:auto; font-family:var(--vlm); font-size:19px; font-weight:700; flex-shrink:0; }

.vl-cta { border-radius:14px; border:1px solid rgba(255,255,255,0.07); background:rgba(14,20,33,0.85);
  padding:1.9rem 1.6rem; text-align:center; margin-top:1.8rem; }
.vl-cta-t { font-size:21px; font-weight:700; color:#fff; margin:0 0 .45rem; }
.vl-cta-s { font-size:13.5px; color:#8899aa; margin:0 auto 1.2rem; max-width:32rem; line-height:1.5; }
.vl-cta-b { display:inline-flex; align-items:center; gap:6px; border-radius:9px; border:1px solid rgba(0,230,118,0.5);
  background:rgba(0,230,118,0.15); color:#00e676; font-family:var(--vlm); font-size:14px; font-weight:600; padding:11px 20px; }
.vl-cta-b:hover { background:rgba(0,230,118,0.25); }
.vl-foot { margin-top:1.6rem; font-family:var(--vlm); font-size:11px; color:#6b7787; text-align:center; }
</style>
"""


# ── helpers ──────────────────────────────────────────────────────────────────
def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def score_color(s: float) -> str:
    if s >= 8: return BLUE
    if s >= 7: return ACCENT
    if s >= 4: return AMBER
    return RED


def level_color(level: str) -> str:
    return LEVEL_COLORS.get(level, ACCENT)


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


def fmt_date(iso: str) -> str:
    return (iso or "")[:10]


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
        cur.execute(
            'SELECT id, title, cards, dimension_scores FROM "AuraSession" '
            "WHERE user_id = %s AND id = %s",
            (USER_ID, session_id),
        )
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        if conn and pool:
            pool.putconn(conn)


# ── html builders ────────────────────────────────────────────────────────────
def header_html() -> str:
    return (
        '<div class="vl-top">'
        '<div class="vl-brand">'
        f'{LOGO_SVG}'
        '<span class="vl-wordmark">Vibe<em>Level</em></span>'
        '<span class="vl-pill">Aura</span>'
        '<span class="vl-desc">Your AI Aura — how you work with AI, from your real sessions</span>'
        '</div>'
        '<div class="vl-ctas">'
        f'<a class="vl-btn ghost" href="{LEADERBOARD_URL}" target="_blank">Leaderboard ↗</a>'
        f'<a class="vl-btn primary" href="{SIGNUP_URL}" target="_blank">Sign up ↗</a>'
        '</div></div>'
    )


def badge(text: str, color: str, icon: str = "") -> str:
    pre = f"{icon} " if icon else ""
    return (
        f'<span class="vl-badge" style="color:{color};background:{color}1a;border:1px solid {color}66;">'
        f'{pre}{esc(text)}</span>'
    )


def hero_html(p: dict) -> str:
    avg = float(p.get("aura_score") or 0)
    best = float(p.get("best_score") or 0)
    show_best = best > 0 and abs(best - avg) > 0.01
    sources = p.get("sources") or {}
    primary = max(sources, key=sources.get) if sources else None
    sessions = p.get("sessions") or []
    mods = {s.get("modality") for s in sessions}
    overall_mod = ("CODING + WRITING" if "coding" in mods and (mods - {"coding"})
                   else "CODING" if "coding" in mods else "WRITING" if mods else None)
    total_tokens = (p.get("stats") or {}).get("total_tokens") or 0

    handle = p.get("handle")
    handle_html = (f'<p class="vl-handle">{SITE.split("//")[-1]}/u/{esc(handle)}</p>' if handle
                   else '<p class="vl-handle">local profile · not yet published</p>')

    arch = esc(p.get("archetype") or "")
    tag = p.get("archetype_tagline")
    arch_html = (f'<p class="vl-arch">{arch}'
                 + (f'<span class="t"> — {esc(tag)}</span>' if tag else "")
                 + '</p>') if arch else ""

    badges = ""
    lvl = p.get("aura_level")
    if lvl:
        badges += badge(lvl, level_color(lvl))
    if p.get("ships_it"):
        badges += badge("Ships it", ACCENT, icon="🚀")

    best_block = ""
    if show_best:
        bl = p.get("best_level")
        best_block = (
            '<div class="vl-vdiv"></div>'
            '<div style="display:flex;flex-direction:column;gap:.5rem;">'
            '<span class="vl-slabel">Best session</span>'
            f'<div><span class="vl-snum">{best:.1f}</span><span class="vl-sden">/10</span></div>'
            + (f'<div class="vl-badges">{badge(bl, level_color(bl))}</div>' if bl else "")
            + '</div>'
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
        '<div style="min-width:0;">'
        f'<p class="vl-name">{esc(p.get("display_name") or "Builder")}</p>'
        f'{handle_html}'
        '</div></div>'
        f'{arch_html}'
        '</div>'
        '<div class="vl-score">'
        '<div class="vl-score-row">'
        '<div style="display:flex;flex-direction:column;gap:.5rem;">'
        '<span class="vl-slabel">Avg of all sessions</span>'
        f'<div><span class="vl-snum">{avg:.1f}</span><span class="vl-sden">/10</span></div>'
        f'<div class="vl-badges">{badges}</div>'
        '</div>'
        f'{best_block}'
        '</div>'
        f'<div class="vl-chips">{chips_html}</div>'
        f'<div class="vl-publish">🔗 <a href="{SIGNUP_URL}" target="_blank">Publish &amp; share on vibelevel.ai →</a></div>'
        '</div></div>'
    )


KLASS = {"credibility": (ACCENT, "Behavioral"), "personality": (BLUE, "Personality")}


def insight_card_html(c: dict) -> str:
    if not (c.get("headline") or c.get("detail")):
        return ""
    accent, label = KLASS.get(c.get("klass"), (ACCENT, "Insight"))
    mod = c.get("modality")
    modtag = "CODING" if mod == "coding" else "WRITING" if mod == "noncoding" else "BOTH"
    q = f'<p class="vl-q">{esc(c["question"])}</p>' if c.get("question") else ""
    dt = f'<p class="vl-dt">{esc(c["detail"])}</p>' if c.get("detail") else ""
    return (
        f'<div class="vl-card" style="border:1px solid {accent}2e;">'
        f'<div class="ln" style="background:linear-gradient(90deg,{accent}00,{accent}99,{accent}00);"></div>'
        f'<span class="vl-cat" style="color:{accent};background:{accent}1f;border:1px solid {accent}59;">{label}</span>'
        f'{q}'
        f'<p class="vl-hl">{esc(c.get("headline") or "")}</p>'
        f'{dt}'
        f'<div class="vl-mt">{modtag}</div>'
        '</div>'
    )


def insights_grid_html(cards: list) -> str:
    items = "".join(insight_card_html(c) for c in cards if c.get("id") != "archetype")
    if not items:
        return '<div class="vl-card" style="text-align:center;color:#8899aa;">No insights yet.</div>'
    return f'<div class="vl-grid">{items}</div>'


def dim_bar_html(label: str, score: float) -> str:
    c = score_color(score)
    pct = max(0, min(100, score * 10))
    return (
        '<div class="vl-dim">'
        '<div class="vl-dtop">'
        f'<span class="vl-dlabel">{esc(label)}</span>'
        f'<span class="vl-dscore" style="color:{c}">{score:.1f}</span>'
        '</div>'
        f'<div class="vl-track"><div class="vl-fill" style="width:{pct}%;background:{c}"></div></div>'
        '</div>'
    )


def usage_tile_html(stats: dict) -> str:
    return (
        '<div class="vl-dim">'
        '<div class="vl-dtop"><span class="vl-dlabel">Usage</span><span class="vl-tele">Telemetry</span></div>'
        '<div class="vl-ug">'
        f'<div><div class="vl-un">{fmt_tokens(stats.get("avg_tokens_per_session"))}</div><div class="vl-ul">tok/session</div></div>'
        f'<div><div class="vl-un">{float(stats.get("avg_prompts_per_session") or 0):.1f}</div><div class="vl-ul">prompts/sn</div></div>'
        f'<div><div class="vl-un">{esc(stats.get("top_model") or "—")}</div><div class="vl-ul">model</div></div>'
        '</div></div>'
    )


def dims_grid_html(dim_scores: dict, stats: dict | None) -> str:
    rows = "".join(
        dim_bar_html(DIM_LABELS.get(k, k.replace("_", " ").title()), float(dim_scores[k].get("score") or 0))
        for k in DIM_ORDER if dim_scores.get(k) is not None
    )
    # any non-standard dims (e.g. writing modality) after the canonical order
    rows += "".join(
        dim_bar_html(DIM_LABELS.get(k, k.replace("_", " ").title()), float((v or {}).get("score") or 0))
        for k, v in dim_scores.items() if k not in DIM_ORDER
    )
    if not rows:
        return '<div class="vl-card" style="text-align:center;color:#8899aa;">No dimension scores yet.</div>'
    if stats:
        rows += usage_tile_html(stats)
    return f'<div class="vl-dims">{rows}</div>'


def session_row_html(s: dict) -> str:
    coding = s.get("modality") == "coding"
    score = float(s.get("aura_score") or 0)
    chips = "".join(
        f'<span class="vl-chip">{esc(x)}</span>'
        for x in (pretty_source(s.get("source")), fmt_date(s.get("created_at")), modality_chip(s.get("modality")))
        if x
    )
    return (
        '<div class="vl-srow">'
        f'<div class="vl-sicon">{"&lt;/&gt;" if coding else "✎"}</div>'
        '<div style="min-width:0;flex:1;">'
        f'<p class="vl-stitle">{esc(s.get("title") or "Untitled session")}</p>'
        f'<div class="vl-schips">{chips}</div>'
        '</div>'
        f'<span class="vl-sscore" style="color:{score_color(score)}">{score:.1f}</span>'
        '</div>'
    )


def cta_html() -> str:
    return (
        '<div class="vl-cta">'
        '<p class="vl-cta-t">Get on the leaderboard</p>'
        '<p class="vl-cta-s">This Aura lives only on your machine. Sign up at VibeLevel to claim a handle, '
        'share your profile, and rank against other builders.</p>'
        f'<a class="vl-cta-b" href="{SIGNUP_URL}" target="_blank">Reveal your Aura on vibelevel.ai →</a>'
        '</div>'
    )


# ── page ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Open Aura", page_icon="✨", layout="wide")
render(CSS)
render(header_html())

try:
    profile = load_profile()
except Exception as e:  # noqa: BLE001
    st.error(f"Couldn't load your profile from local Postgres: {e}")
    st.caption("Is the database up and POSTGRES_URL set? In Docker: `docker compose up`.")
    st.stop()

if int(profile.get("session_count") or 0) == 0:
    render(
        '<div class="vl-hero" style="display:block;text-align:center;">'
        '<div class="vl-avatar" style="margin:0 auto .9rem;">?</div>'
        '<p class="vl-name">No Aura yet</p>'
        '<p class="vl-arch" style="max-width:none;margin-top:.5rem;">'
        '<span class="t">Connect your agent to the Aura MCP server '
        '(<code>http://localhost:8090/mcp</code>) and ask it to “score this session with Aura.”</span></p>'
        '</div>'
    )
    render(cta_html())
    st.stop()

render(hero_html(profile))

render('<div class="vl-h2">Insights</div>')
render(insights_grid_html(profile.get("cards") or []))
render('<p class="vl-note">Behavioral (green) = how you steer, plan &amp; verify · '
       'Personality (ice blue) = style &amp; habits</p>')

render('<div class="vl-h2">Dimensions</div>')
render(dims_grid_html(profile.get("dimension_scores") or {}, profile.get("stats")))

render('<div class="vl-h2">Recent sessions</div>')
sessions = profile.get("sessions") or []
render("".join(session_row_html(s) for s in sessions[:8]))

# Per-session report (cards + dimension breakdown), reusing the same builders.
if sessions:
    labels = {f'{fmt_date(s.get("created_at"))} · {s.get("title") or s.get("id")}': s for s in sessions}
    choice = st.selectbox("Open a session report", ["—"] + list(labels.keys()))
    if choice and choice != "—":
        s = labels[choice]
        detail = load_session_detail(s["id"])
        if detail:
            render(f'<div class="vl-h2">Session report — {esc(s.get("title") or "")}</div>')
            dims = as_obj(detail.get("dimension_scores")) or {}
            if dims:
                render(dims_grid_html(dims, None))
            cards = as_obj(detail.get("cards")) or []
            render(insights_grid_html(cards))

render(cta_html())
render('<div class="vl-foot">Open Aura · local, read-only viewer — nothing is scored or written here.</div>')
