# Homestead Private OS Infra v0

Boring spine first. This repo holds the first deployable foundation for Adam's Homestead Private OS node:

- Docker Compose
- Caddy
- FastAPI API
- thin MCP HTTP facade
- Git-backed repo status/sync
- Markdown search/context packs over Adam's second-brain OKF library/context graph
- Markdown and JSON receipts
- OpenRouter env stub only

No GPU provider, no LiteLLM, no Langfuse, no email alerts, no agent swarm in v0.

## Hetzner v0 Deployment Verified

Hetzner v0 is live as a private foundation node:

- Server: `5.78.206.130`
- Tailscale host: `homestead-cpx51`
- Private URL: `http://100.112.20.36:8088`
- Existing Nginx still owns public `80/443`
- Homestead Caddy is private on Tailscale `8088/8443`
- Docker data-root lives on the mounted Hetzner volume
- All five Compose services use `restart: unless-stopped`

OpenRouter, LiteLLM, GPU, Langfuse, SMTP, vector search, and runner behavior are intentionally not part of this merge.

## Quick Start

```bash
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/docker-compose.yml up --build
```

Then verify:

```bash
curl http://localhost/health
curl http://localhost/api/repo/status
curl http://localhost/mcp/tools
```

Full deployment notes live in [`docs/RUNBOOK.md`](docs/RUNBOOK.md). Exact verification commands live in [`docs/ACCEPTANCE-TESTS.md`](docs/ACCEPTANCE-TESTS.md).

DNS and private access notes:
- [`docs/DNS.md`](docs/DNS.md)
- [`docs/TAILSCALE.md`](docs/TAILSCALE.md)

## Services

| Service | Purpose |
|---|---|
| `homestead-api` | API for health, repo status/sync, markdown search, context packs, receipts |
| `homestead-mcp` | thin HTTP facade exposing the required Homestead tool names |
| `repo-sync` | safe repo fetch loop placeholder |
| `receipt-worker` | receipt queue worker placeholder |
| `caddy` | reverse proxy for local and Tailscale-only domains |
