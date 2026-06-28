# Environment

Local runtime values can live in `infra/.env`.

Hetzner runtime values live in:

```text
/opt/homestead/secrets/runtime.env
```

Never commit real env files.

## Required v0 Variables

| Variable | Purpose |
|---|---|
| `HOMESTEAD_ENV` | environment label, usually `local` or `production` |
| `HOMESTEAD_REPO_PATH` | container path to the repo API inspects |
| `RECEIPTS_DIR` | container path where receipts are written |
| `KEEP_REPO_HOST_PATH` | host path mounted to `HOMESTEAD_REPO_PATH` |
| `HOMESTEAD_DATA_PATH` | host path mounted to `/data` |
| `HOMESTEAD_ENV_FILE` | env file path used by Docker Compose service `env_file` |
| `HOMESTEAD_API_URL` | internal API URL used by MCP facade |
| `CADDY_HTTP_BIND` | host address for Caddy port 80 |
| `CADDY_HTTPS_BIND` | host address for Caddy port 443 |
| `CADDY_HTTP_PORT` | host port mapped to Caddy container port 80 |
| `CADDY_HTTPS_PORT` | host port mapped to Caddy container port 443 |

## Hetzner v0 Values

```bash
HOMESTEAD_ENV=production
HOMESTEAD_REPO_PATH=/workspace/keep
RECEIPTS_DIR=/data/receipts
KEEP_REPO_HOST_PATH=/opt/homestead/the-keep
HOMESTEAD_DATA_PATH=/opt/homestead/data
HOMESTEAD_ENV_FILE=/opt/homestead/secrets/runtime.env
HOMESTEAD_API_URL=http://homestead-api:8000
HOMESTEAD_MCP_URL=http://homestead-mcp:8010
CADDY_HTTP_BIND=100.112.20.36
CADDY_HTTPS_BIND=100.112.20.36
CADDY_HTTP_PORT=8088
CADDY_HTTPS_PORT=8443
```

The live v0 node keeps existing Nginx on public `80/443`, so Homestead Caddy binds privately to the Tailscale IP on `8088/8443`.

Set `CADDY_HTTP_BIND` and `CADDY_HTTPS_BIND` to the server's Tailscale IP for direct tailnet access, or to `0.0.0.0` only for intentional public exposure.

## OpenRouter

These power `/model/route` through OpenRouter. Keep real values only in local/server env files, never in git.

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter key |
| `OPENROUTER_BASE_URL` | OpenRouter API base URL |
| `OPENROUTER_DEFAULT_MODEL` | default model route |
| `OPENROUTER_HTTP_REFERER` | value sent in the `HTTP-Referer` attribution header |
| `OPENROUTER_APP_TITLE` | value sent in the `X-OpenRouter-Title` attribution header |

## Optional Langfuse Tracing

These optionally trace `/model/route` while keeping the serving path direct to OpenRouter. Tracing is disabled by default and must fail open: if Langfuse is missing, unavailable, or rejects auth, `/model/route` should still return the OpenRouter response.

Keep real keys only in local/server env files. Commit placeholders only.

| Variable | Purpose |
|---|---|
| `LANGFUSE_ENABLED` | set to `true` to emit `/model/route` traces; default `false` |
| `LANGFUSE_HOST` | private Langfuse URL, for example `http://100.112.20.36:3000` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key |
| `LANGFUSE_ENVIRONMENT` | trace environment label, default `homestead-private-os` |
| `LANGFUSE_RELEASE` | trace release label, default `v0-openrouter-route` |

Trace metadata includes route, requested model, model used, latency, ok/error, token usage when returned, and requesting surface when available. Prompt and response content are not sent by default.

## Future Placeholders

Present for planning, not used by v0:

| Variable | Task |
|---|---|
| `SMTP_HOST` | Task 5 email alerts |
| `SMTP_PORT` | Task 5 email alerts |
| `SMTP_USER` | Task 5 email alerts |
| `SMTP_PASSWORD` | Task 5 email alerts |
| `SMTP_FROM` | Task 5 email alerts |
