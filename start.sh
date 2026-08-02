#!/usr/bin/env sh
# Open Aura backend entrypoint: print where to reach things, then run the
# FastAPI app — the MCP server (/mcp) + the REST API (/api/aura). The viewer
# runs in its own container (aura-ui) on :3000.
echo ""
# ── Startup banner ──────────────────────────────────────────────────────────
# Boxed, sectioned layout. Every row is printf-padded to a fixed inner width so
# the right border always aligns — keep row TEXT ASCII (byte width == column
# width; box-drawing borders below are the only multibyte chars). Keep VERSION in
# sync with aura_mcp_app.__version__ / package.json. BUILD + PFG ON/OFF come from
# env; the Python startup log adds the resolved PFG reachability a moment later.
VERSION="0.2.0"
BUILD="${AURA_BUILD:-dev}"
BAR="────────────────────────────────────────────────────────────"
if [ "${PFG_GROUNDING_ENABLED}" = "true" ] || [ "${PFG_GROUNDING_ENABLED}" = "1" ]; then
  PFG_ROW="  PFG INSIGHTS    ON   (resolving live reachability...)"
else
  PFG_ROW="  PFG INSIGHTS    OFF  (set PFG_GROUNDING_ENABLED=true)"
fi
row() { printf '  │%-60s│\n' "$1"; }

printf '  ┌%s┐\n' "$BAR"
row "  Open Aura  -  backend starting up"
printf '  ├%s┤\n' "$BAR"
row "  VERSION       v${VERSION}    build: ${BUILD}"
printf '  ├%s┤\n' "$BAR"
row "  ENDPOINTS"
row "    Viewer (UI)     http://localhost:3000"
row "    Backend (MCP)   http://localhost:8090/mcp   (no auth)"
row "    REST API        http://localhost:8090/api/aura"
row "    Health          http://localhost:8090/health"
printf '  ├%s┤\n' "$BAR"
row "$PFG_ROW"
printf '  ├%s┤\n' "$BAR"
row "  HOSTED AURA     www.vibelevel.ai"
row "    public profiles - leaderboard - team insights"
printf '  └%s┘\n' "$BAR"
echo ""
echo "  Point your agent's MCP config at the Backend (MCP) URL, then"
echo "  open the viewer at http://localhost:3000"
echo "  Free & open source under Apache-2.0 · © 2026 VibeLevel"
echo ""
exec uvicorn aura_mcp_app:app --host 0.0.0.0 --port 8090 --proxy-headers --forwarded-allow-ips='*'
