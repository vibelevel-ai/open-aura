# Open Aura

**Open-source, local-first: turn your real AI coding sessions into a scored builder profile, entirely on your own machine.**

Open Aura is an [MCP](https://modelcontextprotocol.io) server your agent (Claude Code, Cursor, Claude Desktop, …) connects to. After a session, the agent sends a **redacted evidence packet** — truncated snippets + file metadata, never raw code or prompts — and Open Aura scores how you worked *with* the AI and stores it in your **local Postgres**. No login, no account, nothing leaves your machine.

> Want a public profile, the shared leaderboard, and team insights? Those live in the hosted edition at [vibelevel.ai](https://www.vibelevel.ai).

---

## Quickstart (Docker)

```bash
cp .env.example .env          # then set OPENAI_API_KEY to your OpenCode key
docker compose up             # Postgres + backend (MCP :8090) + viewer (:3000)
```

Point your agent's MCP config at the local server (no auth in local mode):

```jsonc
// Claude Code / Cursor MCP config
{
  "mcpServers": {
    "aura": { "url": "http://localhost:8090/mcp" }
  }
}
```

Then, after a piece of work, ask your agent to **"score this session with Aura."**

### Local viewer

A **read-only** web viewer ships with the stack (its own `aura-ui` container). After `docker compose up`, open **http://localhost:3000**. A left sidebar — **Profile · Getting Started · Leaderboard · Sessions**, a recent-sessions list, and a greyed *Coming soon* group (importing your sessions / submitting to the leaderboard — those live in the hosted edition) — sits beside the content: the hero score block, flip-able insight cards, dimension bars, and a read-only pull of the public leaderboard. It reads your local data through the backend's REST API and never scores or writes anything.

## What it measures

A referenceless read of your **process** — no rubric, no test cases — across dimensions like prompting effectiveness, AI collaboration/steering, problem decomposition, and human contribution vs. AI reliance, plus a session archetype, insight cards, and measured telemetry (tokens, tools, "ships-it" lifecycle). Tools exposed: `score_this_session`, `import_history`, `get_my_profile`, `whoami`.

## Privacy

The redaction contract is the whole point: **raw transcripts and file contents never leave your machine.** The agent sends only truncated text excerpts and file *paths/metadata*. In local mode the scoring and profile paths make **no outbound calls** — everything stays in your local Postgres. (The only exception is the viewer's optional **Leaderboard** tab, which does a plain read-only `GET` of the public leaderboard from vibelevel.ai — it sends none of your data.)

## Configuration

| Var | Default | Purpose |
|---|---|---|
| `AURA_LOCAL_MODE` | `true` (in `.env.example`) | single local user, no PAT/login |
| `AURA_SCORING_MODEL` | `openai/gpt-oss-120b` | scoring model (provider routing in `model_config.json`) |
| `OPENAI_API_KEY` / `GROQ_API_KEY` / `ANTHROPIC_API_KEY` | — | bring your own; set the one your model uses |
| `OPENAI_BASE_URL` | OpenAI default | optional OpenAI-compatible endpoint (for OpenCode, use `https://opencode.ai/zen/v1`) |
| `POSTGRES_URL` | compose-provided | local Postgres (apply `schema.sql` for bare-metal) |
| `AURA_MCP_PORT` | `8090` | MCP server port |

## Experimental: PFG operational insights

This branch (`pfg-insights-poc`) adds an **opt-in, off-by-default** capability: ground
a session against a **Product Feature Graph** and get advisory *check-tips* (e.g.
"you hand-rolled X — the graph maps an established SDK", or "this is marked legacy").
It works precisely *because* Open Aura is local — it reads your **real** `git diff`
and full transcript (passed as `local_context`, never persisted or scored) instead of
a redacted summary. It never affects your Aura score. See
[`docs/PFG_INSIGHTS_POC.md`](docs/PFG_INSIGHTS_POC.md) and the `PFG_*` vars in
`.env.example`.

## How it's built

- `src/aura_mcp/` — the MCP server (`server.py`) + the single-local-user binding (`local_auth.py`).
- `src/services/aura/` — the referenceless scorer, signal extraction, archetypes, profile aggregation, and the scoring **rubric** (`aura_model_coding.py` / `aura_model_writing.py`) — open for contributions.
- `src/core/` — slim config, Postgres pool, and LLM provider routing.
- `aura_mcp_app.py` — the entrypoint that mounts the MCP app + the REST API + `/health`.
- `packages/aura-ui/` + `web/` — the React viewer components and the Next.js host that renders them (the `aura-ui` container).

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0 — see [`LICENSE`](LICENSE).

VibeLevel and Aura are names and brands of VibeLevel. This repository is the
local-first, open edition. The hosted service at [vibelevel.ai](https://www.vibelevel.ai) —
the public leaderboard, shareable profiles, and the aggregated network — is
separate and not included here. The license grants no rights to the VibeLevel
or Aura names or logos, or to operate a hosted service using them.
