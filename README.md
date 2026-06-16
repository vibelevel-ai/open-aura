# Open Aura

**Open-source, local-first: turn your real AI coding sessions into a scored builder profile, entirely on your own machine.**

Open Aura is an [MCP](https://modelcontextprotocol.io) server your agent (Claude Code, Cursor, Claude Desktop, …) connects to. After a session, the agent sends a **redacted evidence packet** — truncated snippets + file metadata, never raw code or prompts — and Open Aura scores how you worked *with* the AI and stores it in your **local Postgres**. No login, no account, nothing leaves your machine.

> Want a public profile, the shared leaderboard, and team insights? Those live in the hosted edition at [vibelevel.ai](https://www.vibelevel.ai).

---

## Quickstart (Docker)

```bash
cp .env.example .env          # then set ONE provider key (e.g. GROQ_API_KEY)
docker compose up             # Postgres + the app (MCP server :8090 + viewer :3000)
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

A lightweight, **read-only** Streamlit dashboard is built into the stack — the app container runs it alongside the MCP server. After `docker compose up`, open **http://localhost:3000**. Styled after the VibeLevel Aura profile, with a sidebar (Profile · Getting started · Leaderboard · your recent sessions), the hero score block, flip-able insight cards, dimension bars, a light/dark toggle, and a read-only pull of the public leaderboard. It reads your local Postgres and reuses the exact aggregation the MCP server uses — it never scores or writes anything.

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
| `POSTGRES_URL` | compose-provided | local Postgres (apply `schema.sql` for bare-metal) |
| `AURA_MCP_PORT` | `8090` | MCP server port |

## How it's built

- `src/aura_mcp/` — the MCP server (`server.py`) + auth (`pat_auth.py`, with a local-mode bypass).
- `src/services/aura/` — the referenceless scorer, signal extraction, archetypes, profile aggregation, and the scoring **rubric** (`aura_model_coding.py` / `aura_model_writing.py`) — open for contributions.
- `src/core/` — slim config, Postgres pool, and LLM provider routing.
- `aura_mcp_app.py` — the entrypoint that mounts the MCP app + `/health`.
- `streamlit_app.py` + `Procfile` — the local read-only viewer; the app container runs it next to the MCP server via honcho.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

See [`LICENSE`](LICENSE).
