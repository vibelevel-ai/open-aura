# Open Aura profile evolution

## Product direction

The local profile implements the hierarchy and information architecture of
`VibeLevel Aura Profile.html` in Open Aura's dark viewer. `AuraProfile` remains
the primary renderer; no parallel profile page was introduced.

## Concept mapping

| Reference capability | Open Aura treatment | Data source | Hosted treatment |
| --- | --- | --- | --- |
| Identity, headline, experience, location, availability | Evidence-weighted local inference with confidence and empty states | Redacted scored-session evidence | User-controlled public profile fields |
| Aura score, level, archetype | Full local implementation | Existing scoring output | Public and cross-device profile |
| AI activity | Exactly 365 UTC dates, source filtering, streaks and inspection | Local session timestamps | Public/aggregated history |
| Agents and models | Full local measured summary | Session source and model metadata | Multi-agent/cross-device aggregation |
| MCP servers | Sanitized observed names only | Optional workspace context | Managed integrations |
| Tools and skills | Measured counts when the source reports them | `local_stats` | Expanded integrations and analytics |
| Projects/repositories | Sanitized repository-grouped local evidence | Optional workspace context and session scores | Published portfolio and verification |
| Dimensions and human edge | Existing scores in the reference hierarchy | Existing dimension contract | Public credibility signals |
| Behavioral/personality insights | Existing insight cards and session scope | Existing cards | Shareable public profile |
| Publishing and recruiter workflows | One explicit external CTA; no local workflow | Viewer configuration | Hosted-only |

## Implemented scope

- Reference-style dark identity hero and score ring.
- Evidence-weighted profile signals for headline, availability, experience, and
  location.
- Fixed 365-day UTC activity heatmap with source filters, totals, active days,
  current/longest streaks, and keyboard/touch day inspection.
- Agents, models, MCP servers, tools, and skills from verified session metadata.
- Project cards grouped by sanitized repository basename with session count and
  average project Aura.
- Existing dimensions, human-edge presentation, insights, session selection,
  and deep links retained.
- Centralized hosted sign-in and publication URLs derived from
  `AURA_PUBLIC_WEB_URL`.

## Scoring and aggregation

`EvidencePacket.workspace_context` accepts optional automatically collected,
sanitized metadata:

- Repository basename.
- Short redacted project summary.
- Language labels.
- MCP display names/categories.

The existing scoring response now includes optional `profile_facts`. Each scalar
fact contains a value, confidence, source, and short redacted evidence summary.
The session's facts are persisted under `AuraSession.telemetry.profile_facts`,
so existing databases require no migration.

Profile aggregation combines confidence, source quality, repetition, and
recency. Measured signals have more weight than model-inferred signals. Stable,
repeated evidence can therefore outweigh one unusual recent session.

Existing sessions without the new fields remain valid. Unsupported or
low-confidence values are omitted and the UI shows an insufficient-evidence
state rather than fabricated content.

## Privacy and network implications

- Raw prompts, full transcripts, source-code contents, credentials, environment
  values, tokens, private keys, and MCP configuration values are not added to
  profile facts.
- Repository values are reduced to sanitized basenames.
- MCP values are reduced to safe display names and categories; URLs and
  secret-like values are rejected.
- Project summaries are bounded and reject secret-like values.
- All new persistence and aggregation remains in the local PostgreSQL database.
- The profile sections add no fetch, XHR, beacon, analytics SDK, or upload.
- Inference reuses the existing scoring-model call; it does not add a separate
  outbound request.
- Automatically inferred profile, toolkit, and project facts are removed from
  the compatibility public-profile REST route. Explicit hosted publication is
  required before recruiter-facing use.

## Hosted publication boundary

The local viewer states that the current Aura stays local. Its primary
publication destination is:

`https://www.vibelevel.ai/aura?source=open-aura&intent=publish-profile`

The base is configurable through `AURA_PUBLIC_WEB_URL`. The URL contains only
static source and intent parameters. Clicking it opens the hosted product but
does not upload a profile, score, session identifier, timestamp, repository, or
other local value.

Public URLs, recruiter discovery, interview requests, hiring workflows, public
verification, portfolio publishing, cloud synchronization, and cross-device
aggregation remain hosted responsibilities.

## Activity semantics

- The window contains exactly 365 UTC dates and includes today as the final
  date.
- A session later than the exact current instant is rejected before UTC day
  bucketing.
- Invalid and out-of-range timestamps are excluded.
- Missing, empty, and whitespace sources normalize to `unknown`.
- Source ties use locale-independent lexical ordering.
- Today or yesterday can continue the current streak; stale activity produces a
  current streak of zero.

## Local startup

The viewer is built into a Docker image. Source changes require a rebuild:

```bash
docker compose up --build
```

Running `docker compose up` without `--build` may reuse an older viewer image.
