#!/usr/bin/env sh
# Open Aura backend entrypoint: print where to reach things, then run the
# FastAPI app — the MCP server (/mcp) + the REST API (/api/aura). The viewer
# runs in its own container (aura-ui) on :3000.
echo ""
echo "  ┌────────────────────────────────────────────────────────────┐"
echo "  │   ✨  Open Aura — backend starting up                        │"
echo "  ├────────────────────────────────────────────────────────────┤"
echo "  │   Viewer (UI)     →  http://localhost:3000                   │"
echo "  │   Backend (MCP)   →  http://localhost:8090/mcp   (no auth)   │"
echo "  │   REST API        →  http://localhost:8090/api/aura          │"
echo "  │   Health          →  http://localhost:8090/health           │"
echo "  └────────────────────────────────────────────────────────────┘"
# Version line (keep v in sync with aura_mcp_app.__version__ / package.json).
# Build label + PFG ON/OFF come from env; the Python startup log adds the live
# PFG reachability check a moment later.
echo "   Open Aura v0.1.0  ·  build ${AURA_BUILD:-dev}"
if [ "${PFG_GROUNDING_ENABLED}" = "true" ] || [ "${PFG_GROUNDING_ENABLED}" = "1" ]; then
  echo "   PFG insights: ON (resolving live reachability…)"
else
  echo "   PFG insights: OFF  (set PFG_GROUNDING_ENABLED=true)"
fi
echo "   Point your agent's MCP config at the backend URL above, then"
echo "   open the viewer in your browser."
echo ""
echo "   Hosted Aura · leaderboard · teams  →  https://www.vibelevel.ai"
echo "   Open Aura — free & open source under Apache-2.0 · © 2026 VibeLevel"
echo ""
exec uvicorn aura_mcp_app:app --host 0.0.0.0 --port 8090 --proxy-headers --forwarded-allow-ips='*'
