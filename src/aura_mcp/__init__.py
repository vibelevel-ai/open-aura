"""VibeLevel Aura — standalone MCP connector package.

This package is the sidecar that lets a user's local AI agent (Claude Code /
Cursor / Claude Desktop) score its own real work sessions against VibeLevel
Aura. It runs as its OWN process (entrypoint: ``aura_mcp_app.py`` at the repo
root).

Contents:
  - ``pat_auth``  — Personal Access Token mint/hash/verify + Starlette
    ``PATAuthMiddleware`` (agents have no browser cookie, so PAT is net-new).
  - ``server``    — the ``FastMCP`` server + the agent-facing tools.

It reuses only PLATFORM infra (the DB pool, config/env, the ``"User"`` table,
and the Aura scoring/profile services).
"""
