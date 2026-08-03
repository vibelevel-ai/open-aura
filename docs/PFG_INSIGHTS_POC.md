# PFG Operational Insights — Open Aura POC

**Status:** experimental · opt-in · off by default.

Open Aura can ground a scored session against a **Product Feature Graph (PFG)** and
return advisory **check-tips** — *current-vs-legacy*, *hand-rolled-vs-established-SDK*,
*a standard or skill to adopt*, or *a graph gap you should add*. Tips are **advisory
only**: they never change your Aura score.

In plain terms: the graph already maps the tools builders use — **Claude skills,
LangChain, the OpenAI SDK, MCP servers**, and more — so your session gets specific
"use this instead" nudges grounded in real tooling, rather than just a number.

## Why this lives in Open Aura, not the hosted edition

The hosted scorer only ever receives a **redacted** evidence packet (truncated
snippets, file metadata — never raw code or prompts). An earlier hosted attempt
asked the *agent* to self-report graph tags from that redacted summary, and the
tags were too weak to ground well — so it was paused.

Open Aura runs **on your machine**, so it can see the **real artifacts**: the actual
`git diff`, the full transcript, and the dependency manifests. That makes it the
right place to derive accurate tags and produce real insights. This is a deliberate
**local-first divergence** — something the redacted hosted path structurally cannot do.

## How it works

1. **You pass `local_context`** to `score_this_session` (separate from the redacted
   `evidence`): the real `git diff`, full transcript, manifests, and commands. This
   stays on your machine and is **never persisted, fingerprinted, or scored**.
2. **Local extraction** (`pfg_local_extractor.py`) turns it into high-quality tags:
   - *Deterministic* — dependency manifests (`package.json`, `requirements.txt`,
     `pyproject.toml`, `go.mod`, `Cargo.toml`), added imports in the diff, touched
     file-path work-areas, and commands.
   - *Local LLM* (your BYO key, same `AURA_SCORING_MODEL`) — reads the FULL
     transcript + diff to name capabilities, patterns, work-areas, and the crucial
     **approach**: was something built by hand (`direct-api`/`manual`/`custom`) that
     an established SDK/framework usually handles?
3. **Resolution** (`pfg_client.py`) grounds the tags against the graph READ-ONLY:
   token/synonym expansion (to beat PFG's literal substring search), category-aware
   ranking, a 3-factor confidence (match / evidence / authority), and precision-first
   check-tips. High-evidence "not found" surfaces as a **graph gap** for you to add.
4. **Result** — surfaced tips come back on the `ScoreResult` as `pfg_check_tips`
   (capped, ordered by usefulness).

## Configuration

All env-gated; see `.env.example`:

| Var | Default | Purpose |
|---|---|---|
| `PFG_GROUNDING_ENABLED` | `false` | master switch for grounding |
| `PFG_MCP_URL` | — | PFG MCP endpoint (include the `/mcp` path) |
| `PFG_MCP_TOKEN` | — | bearer token for the PFG MCP |
| `PFG_WORKSPACE` | `vibelevel` | graph workspace to read (passed per query) |
| `PFG_EXTRACT_LLM` | `true` | set `false` for deterministic-only extraction |

With grounding disabled (the default) or `local_context` omitted, scoring behaves
exactly as before — this feature is purely additive.

## Getting access (endpoint + token)

Grounding talks to VibeLevel's hosted **VibeGraph** MCP over streamable-HTTP. Access is
**read-only** and needs a Personal Access Token (PAT):

1. Sign in at **[graph.vibelevel.ai](https://graph.vibelevel.ai)**.
2. Create or open a workspace. For operational insights, the public catalog
   **`public-graphs-by-vibelevel`** (SDKs / frameworks + Claude skills) is the best
   target — it's what powers the *improve*, *currency*, and *adopt* tips. (Point
   `PFG_WORKSPACE` at your **own** product graph instead only if you also want *graph
   gap* tips; those are suppressed for catalogs you don't curate.)
3. Go to **Account → Tokens** and generate a token — it looks like `pfg_…`. PATs are
   user-scoped: one token works across every workspace you can read.

Then set these in your `.env` and rebuild the backend (`docker compose up -d --build`):

```dotenv
PFG_GROUNDING_ENABLED=true
PFG_MCP_URL=https://graphapi.vibelevel.ai/mcp
PFG_MCP_TOKEN=pfg_your_token_here
PFG_WORKSPACE=public-graphs-by-vibelevel
```

You do **not** need to add the `Bearer ` prefix — Open Aura adds it. On startup the
backend logs a status line so you can confirm it's wired:

```
[Open Aura] PFG insights: ON · graphapi.vibelevel.ai · ws=public-graphs-by-vibelevel · reachable ✓ · extract-LLM=on
```

`reachable ✗` means the URL, token, or workspace is wrong — grounding then silently
no-ops (it never breaks scoring).

## Boundaries / design rules

- **Read-only.** Open Aura never writes to or proposes changes to the graph. A
  genuine gap is surfaced for *you* to take to PFG.
- **Never scored.** `local_context` and the derived tags never feed the scoring LLM
  and are not part of the dedup fingerprint.
- **Best-effort.** Every step is guarded; a failure (no graph configured, LLM
  unavailable, a bad query) degrades to fewer or no tips — it never breaks scoring.

## Files

- `src/services/aura/contracts.py` — `PfgTag`, `LocalContext`, `pfg_check_tips`.
- `src/services/aura/pfg_local_extractor.py` — local tag extraction (deterministic + LLM).
- `src/services/aura/pfg_client.py` — graph resolution + live PFG-MCP transport.
- `src/services/aura/aura_scoring_service.py` — `score_evidence` grounding hook.
- `src/aura_mcp/server.py` — `score_this_session(evidence, local_context=…)`.
