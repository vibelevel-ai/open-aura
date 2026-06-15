# Open Aura

**The open-source, local-first edition of VibeLevel Aura — turn your real AI coding sessions into a scored builder profile, entirely on your own machine.**

Open Aura is an [MCP](https://modelcontextprotocol.io) server your agent (Claude Code, Cursor, Claude Desktop, …) connects to. After a session, the agent sends a **redacted evidence packet** — truncated snippets + file metadata, never raw code or prompts — and Open Aura scores how you worked *with* the AI and stores it in your **local Postgres**. No login, no account, nothing leaves your machine.

> Same scoring engine as hosted [Aura](https://github.com/vibelevel-ai/aura). The hosted edition adds the shared leaderboard, public profiles, and team insights; this repo is the local core, and the methodology is open for the community to shape.

---

## Quickstart (Docker)

```bash
cp .env.example .env          # then set ONE provider key (e.g. GROQ_API_KEY)
docker compose up             # starts Postgres + the Aura MCP server
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

### Local viewer (optional)

Prefer a dashboard over raw tool output? A lightweight, **read-only** Streamlit viewer ships in this repo — opt in with a compose profile so the default stack stays just Postgres + the MCP server:

```bash
docker compose --profile ui up      # db + MCP + the viewer
```

Open **http://localhost:8501** for your Aura score, per-dimension scores, insight cards, and a session-by-session breakdown. It reads your local Postgres and reuses the exact aggregation the MCP server uses — it never scores or writes anything.

## What it measures

A referenceless read of your **process** — no rubric, no test cases — across dimensions like prompting effectiveness, AI collaboration/steering, problem decomposition, and human contribution vs. AI reliance, plus a session archetype, insight cards, and measured telemetry (tokens, tools, "ships-it" lifecycle). Tools exposed: `score_this_session`, `import_history`, `get_my_profile`, `whoami`.

## Privacy

The redaction contract is the whole point: **raw transcripts and file contents never leave your machine.** The agent sends only truncated text excerpts and file *paths/metadata*. In the default local mode everything stays in your local Postgres — there is no network call out of Open Aura at all.

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
- `streamlit_app.py` — the optional local read-only viewer (`ui` compose profile).

## Contributing

The scoring methodology is meant to be community-shaped — PRs to the rubric and signal extraction are welcome. Join the discussion via the Discord linked from [vibelevel-ai/aura](https://github.com/vibelevel-ai/aura).

## License

See [`LICENSE`](LICENSE).
