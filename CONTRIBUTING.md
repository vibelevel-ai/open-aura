# Contributing to Open Aura

Thanks for your interest in improving Open Aura! Contributions of all kinds —
bug reports, fixes, features, and docs — are welcome.

## Reporting issues
Open a GitHub issue with:
- what you expected vs. what happened,
- steps to reproduce,
- your environment (OS, Docker version, the provider/model you're scoring with).

For anything security-sensitive, please report it privately rather than in a
public issue.

## Submitting changes
1. Fork the repo and create a branch off `main`.
2. Keep pull requests focused — one logical change per PR.
3. Describe the change and why; link any related issue.
4. Make sure the stack still runs: `docker compose up` (backend `:8090`,
   viewer `:3000`).

## Running locally
See the [README](README.md) for the quickstart. In short: `cp .env.example .env`,
set one provider key, then `docker compose up`.

## Layout
- `src/` — the MCP server, the referenceless scorer, and the REST API.
- `packages/aura-ui/` — the React viewer components.
- `web/` — the Next.js viewer host.

## License
By contributing, you agree that your contributions are licensed under the
project's [Apache-2.0](LICENSE) license.
