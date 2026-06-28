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
| `KEEP_HEALTH_DIR` | repo-relative Keep folder for Homestead health summaries |
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
KEEP_HEALTH_DIR=System Receipts/Homestead Health
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

## Optional Model Gateway

`/model/route` defaults to direct OpenRouter routing. LiteLLM support is optional and env-gated; do not enable it in production until Homestead has a private container-to-LiteLLM network path.

The inherited LiteLLM service currently binds on the Hetzner host at `127.0.0.1:4000`. From inside the Homestead API container, `127.0.0.1` means the API container itself, not the host. Keep `MODEL_GATEWAY=direct` unless a private server-side path is deliberately added without public or Tailscale exposure.

| Variable | Purpose |
|---|---|
| `MODEL_GATEWAY` | `direct` or `litellm`; default `direct` |
| `LITELLM_BASE_URL` | OpenAI-compatible LiteLLM base URL. Use `http://litellm:4000` only with the private `infra/docker-compose.litellm.yml` network overlay. |
| `LITELLM_API_KEY` | LiteLLM bearer token; real value belongs only in local/server env files |
| `LITELLM_DEFAULT_MODEL` | default LiteLLM alias, for example `haiku` |
| `LITELLM_SEND_TEMPERATURE` | set `true` only when the selected aliases support temperature overrides; default `false` |

When `MODEL_GATEWAY=litellm`, Homestead does not silently fall back to OpenRouter. A LiteLLM failure returns a safe model-route error so operators know the selected gateway is broken.

The optional private network overlay is:

```text
infra/docker-compose.litellm.yml
```

It attaches `homestead-api` to the existing external Docker network `arlo-net` so the API container can reach the inherited LiteLLM container at `http://litellm:4000` without publishing LiteLLM publicly or over Tailscale.

When this overlay is active, Homestead can also reach the inherited Langfuse web container privately at:

```text
LANGFUSE_HOST=http://langfuse-web:3000
```

This is preferable inside the API container to the Tailscale UI address.

## Optional Langfuse Tracing

These optionally trace `/model/route` while keeping the serving path on the selected model gateway. Tracing is disabled by default and must fail open: if Langfuse is missing, unavailable, or rejects auth, `/model/route` should still return the model response.

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

## Optional Model Route Receipts

These optionally write append-only receipt metadata for `/model/route` calls using the existing receipt path. Receipts are disabled by default and must fail open: if receipt writing fails, `/model/route` should still return the OpenRouter response.

| Variable | Purpose |
|---|---|
| `MODEL_ROUTE_RECEIPTS_ENABLED` | set to `true` to write model-route metadata receipts; default `false` |
| `MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT` | set to `true` only after an explicit content-capture decision; default `false` |

Default receipts include run id, timestamp, requesting surface, route, requested model, model used, latency, ok/error, token usage when returned, Langfuse trace id when available, review flag, and verdict. Prompt and response content are not written by default.

## Cloud OS Status And Keep Health

Homestead exposes a cloud-first status surface:

| Endpoint | Purpose |
|---|---|
| `GET /node/status` | current node health, git, gateway, Langfuse, receipts, exposure assumptions, and capabilities |
| `GET /os/status` | cloud OS status alias for node status |
| `GET /os/context` | cloud-first OS context, MCP tools, Keep health folder, and local-mode readiness |
| `GET /os/capabilities` | canonical capability registry for enabled, disabled, optional, and future-only surfaces |
| `POST /keep/health/sync` | explicit metadata-only health summary sync into The Keep |

`KEEP_HEALTH_DIR` is repo-relative under `HOMESTEAD_REPO_PATH`.

Default:

```text
KEEP_HEALTH_DIR=System Receipts/Homestead Health
```

The sync writes operational summaries only. It omits prompts, completions, headers, API keys, and raw env values. Local mode is represented as disabled until Adam explicitly chooses that release path.

## Review Queue And Capability Map

Homestead exposes a narrow attention surface for receipts that need review:

| Endpoint | Purpose |
|---|---|
| `GET /receipts/review?limit=20` | receipt metadata summaries where `review_required=true`, `verdict` is not `ok`/`recorded`, `metadata.ok=false`, or `error_summary` is present |

MCP tools:

```text
homestead.receipts_review
homestead.os_capabilities
```

The review queue is read-only and metadata-only. It does not read or return receipt Markdown bodies, prompt content, response content, headers, API keys, raw env, or stack traces.

The capability registry is read-only. It is the agent-facing answer to what Homestead can safely use now:

```text
cloud_node_status: active
model_route: active, direct gateway remains production default
litellm_gateway: available_private_optional, not default
langfuse_tracing: optional_fail_open
model_route_receipts: optional_fail_open
receipt_index: active, read-only
review_queue: active, read-only
keep_health_sync: explicit_only
local_mode: disabled
runner: disabled
alerts: disabled
dashboard: disabled
```

Keep health folder policy:

```text
/System Receipts/Homestead Health is agent-readable operational memory.
It may remain dirty/untracked until a separate Keep sync policy is chosen.
Agents may read it for current node context.
Agents must not auto-commit it, treat it as infra source, or write prompt/content/secrets into it.
```

## Future Placeholders

Present for planning, not used by v0:

| Variable | Task |
|---|---|
| `SMTP_HOST` | Task 5 email alerts |
| `SMTP_PORT` | Task 5 email alerts |
| `SMTP_USER` | Task 5 email alerts |
| `SMTP_PASSWORD` | Task 5 email alerts |
| `SMTP_FROM` | Task 5 email alerts |
