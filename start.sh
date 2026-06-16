#!/usr/bin/env sh
# Open Aura container entrypoint: print where to reach things, then run both
# processes (the MCP server + the Streamlit viewer) via honcho (see Procfile).
echo ""
echo "  ┌────────────────────────────────────────────────────────────┐"
echo "  │   ✨  Open Aura — starting up                                │"
echo "  ├────────────────────────────────────────────────────────────┤"
echo "  │   Viewer (UI)     →  http://localhost:3000                   │"
echo "  │   Backend (MCP)   →  http://localhost:8090/mcp   (no auth)   │"
echo "  │   Health          →  http://localhost:8090/health           │"
echo "  └────────────────────────────────────────────────────────────┘"
echo "   Point your agent's MCP config at the backend URL above, then"
echo "   open the viewer in your browser. (~2s for both to be ready.)"
echo ""
exec honcho start
