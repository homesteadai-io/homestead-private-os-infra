# Langfuse / LiteLLM Inventory Handoff

Updated: 2026-06-28

## Scope

This was a read-only inventory pass on the existing Langfuse and LiteLLM containers on the Hetzner node.

No Homestead routing was changed. Homestead `/model/route` still routes directly to OpenRouter. No LiteLLM gateway wiring, Langfuse tracing, public exposure changes, container restarts, deletes, stops, or secret commits were performed.

## Executive Recommendation

1. **Keep Homestead direct OpenRouter routing for now.** It is live, simpler, already private through the Homestead Tailscale/Caddy path, and does not depend on inherited infrastructure.
2. **Do not add Langfuse tracing until exposure is corrected or explicitly accepted.** Langfuse is running and its app health endpoint reports OK, but `langfuse-web` is bound to the public IPv4 on port `3000`, and MinIO is bound publicly on port `9090`.
3. **Treat LiteLLM as a useful later candidate, not the next dependency.** It is running, loopback-bound, backed by Postgres and Redis, and configured with budgets/cache/fallbacks/Langfuse callbacks. But its model aliases need validation, its API requires auth, and it has no container-level healthcheck.

## Ownership

The Langfuse/LiteLLM stack is not owned by Homestead.

Docker Compose project:

```text
arlo-infra
```

Compose file:

```text
/opt/arlo-infra/docker-compose.yml
```

Related config files observed:

```text
/opt/arlo-infra/.env
/opt/arlo-infra/litellm_config.yaml
/opt/arlo-infra/litellm_config.yaml.bak.2026-04-09
/opt/arlo-infra/litellm_config.yaml.bak.cache.2026-04-09
/opt/arlo-infra/docker-compose.yml.pre-cap-sub-refresh-001
```

Docker Compose also reports a separate Homestead project:

```text
homestead-private-os
```

Homestead API is on Docker network:

```text
homestead-private-os_default
```

The inherited stack is on:

```text
arlo-net
```

No direct Docker-network dependency from Homestead to `arlo-infra` was observed.

## Systemd

No active systemd service was observed as the owner of the Langfuse/LiteLLM containers.

One related static unit exists but is inactive and not a container owner:

```text
arlo-cognitive-retention.service
Loaded: static
Active: inactive (dead)
ExecStart: /root/.brv-cli/bin/node /root/.openclaw/workspace/lib/events/retention-runner.mjs
```

## Containers

| Container | Image | Status | Health | Restart | Host ports |
| --- | --- | --- | --- | --- | --- |
| `langfuse-web` | `langfuse/langfuse:3` | running | none | always | `0.0.0.0:3000->3000`, `[::]:3000->3000` |
| `langfuse-worker` | `langfuse/langfuse-worker:3` | running | none | always | `127.0.0.1:3030->3030` |
| `litellm` | `ghcr.io/berriai/litellm:main-stable` | running | none | unless-stopped | `127.0.0.1:4000->4000` |
| `langfuse-db` | `postgres:17` | running | healthy | always | `127.0.0.1:5432->5432` |
| `litellm-db` | `postgres:16-alpine` | running | healthy | unless-stopped | no host port |
| `langfuse-clickhouse` | `clickhouse/clickhouse-server` | running | healthy | always | `127.0.0.1:8123->8123`, `127.0.0.1:9000->9000` |
| `litellm-redis` | `redis:7-alpine` | running | healthy | unless-stopped | no host port |
| `langfuse-redis` | `redis:7` | running | healthy | always | `127.0.0.1:6379->6379` |
| `langfuse-minio` | `cgr.dev/chainguard/minio` | running | healthy | always | `0.0.0.0:9090->9000`, `[::]:9090->9000`, `127.0.0.1:9091->9001` |

## Bind / Exposure Findings

Confirmed public or public-bind surfaces:

```text
http://5.78.206.130:3000/                 -> 200 text/html
http://5.78.206.130:9090/minio/health/live -> 200
```

Confirmed Tailscale-visible surfaces due to public/all-interface binding:

```text
http://100.112.20.36:3000/ -> 200 text/html
```

Confirmed private/loopback-only surface:

```text
http://127.0.0.1:4000/health    -> 401 auth_error, no API key passed
http://127.0.0.1:4000/v1/models -> 401 auth_error, no API key passed
```

Confirmed not reachable over Tailscale:

```text
http://100.112.20.36:4000/health -> connection failed
```

Interpretation:

- Langfuse web is currently publicly reachable on port `3000`.
- Langfuse MinIO API is currently publicly reachable on port `9090`.
- LiteLLM is not publicly or Tailscale reachable; it is loopback-bound on the host.
- Internal Langfuse data services are mostly loopback-only or Docker-network-only.

## Health / Usability Checks

Langfuse:

```text
GET http://127.0.0.1:3000/api/public/health
200 application/json
{"status":"OK","version":"3.164.0"}
```

LiteLLM:

```text
GET http://127.0.0.1:4000/health
401 application/json
auth required
```

```text
GET http://127.0.0.1:4000/v1/models
401 application/json
auth required
```

MinIO:

```text
GET http://127.0.0.1:9090/minio/health/live
200
```

Interpretation:

- Langfuse appears live at the application layer.
- LiteLLM appears live enough to reject unauthenticated requests, but it was not authenticated-tested in this pass.
- MinIO is live, but its API bind is a concern because it is exposed on all interfaces.

## Volumes / Databases

Named volumes observed:

```text
langfuse_langfuse_clickhouse_data
langfuse_langfuse_clickhouse_logs
langfuse_langfuse_minio_data
langfuse_langfuse_postgres_data
langfuse_langfuse_redis_data
litellm_litellm_pgdata
litellm_redis_data
```

Volume data lives under Docker's mounted-volume root:

```text
/mnt/HC_Volume_105361821/docker/volumes/...
```

Datastores:

- Langfuse Postgres: `postgres:17`, healthy, loopback host port `5432`.
- Langfuse ClickHouse: healthy, loopback host ports `8123` and `9000`.
- Langfuse Redis: healthy, loopback host port `6379`.
- Langfuse MinIO: healthy, public API port `9090`, loopback console port `9091`.
- LiteLLM Postgres: healthy, Docker-network only.
- LiteLLM Redis: healthy, Docker-network only.

## Env Var Names Present

Values were not recorded here. Treat all listed names as value-present unless noted by the owning image defaults.

### LiteLLM

```text
ANTHROPIC_API_KEY
DATABASE_URL
GEMINI_API_KEY
GOOGLE_API_KEY
LANGFUSE_HOST
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
LITELLM_MASTER_KEY
OPENAI_API_KEY
OPENROUTER_API_KEY
POSTGRES_PASSWORD
```

Also present from image/runtime defaults:

```text
HOSTNAME
PATH
SSL_CERT_FILE
UV_COMPILE_BYTECODE
UV_LINK_MODE
```

### Langfuse Web / Worker

Key application and secret-bearing names present:

```text
CLICKHOUSE_CLUSTER_ENABLED
CLICKHOUSE_MIGRATION_URL
CLICKHOUSE_PASSWORD
CLICKHOUSE_URL
CLICKHOUSE_USER
DATABASE_URL
ENCRYPTION_KEY
LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES
LANGFUSE_S3_BATCH_EXPORT_ACCESS_KEY_ID
LANGFUSE_S3_BATCH_EXPORT_BUCKET
LANGFUSE_S3_BATCH_EXPORT_ENABLED
LANGFUSE_S3_BATCH_EXPORT_ENDPOINT
LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT
LANGFUSE_S3_BATCH_EXPORT_FORCE_PATH_STYLE
LANGFUSE_S3_BATCH_EXPORT_PREFIX
LANGFUSE_S3_BATCH_EXPORT_REGION
LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY
LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID
LANGFUSE_S3_EVENT_UPLOAD_BUCKET
LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT
LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE
LANGFUSE_S3_EVENT_UPLOAD_PREFIX
LANGFUSE_S3_EVENT_UPLOAD_REGION
LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY
LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID
LANGFUSE_S3_MEDIA_UPLOAD_BUCKET
LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT
LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE
LANGFUSE_S3_MEDIA_UPLOAD_PREFIX
LANGFUSE_S3_MEDIA_UPLOAD_REGION
LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY
LANGFUSE_USE_AZURE_BLOB
NEXTAUTH_SECRET
NEXTAUTH_URL
REDIS_AUTH
REDIS_HOST
REDIS_PORT
REDIS_TLS_CA
REDIS_TLS_CERT
REDIS_TLS_ENABLED
REDIS_TLS_KEY
SALT
TELEMETRY_ENABLED
```

Also present from image/runtime defaults:

```text
BUILD_ID
DOCKER_BUILD
NEXT_MANUAL_SIG_HANDLE
NEXT_PUBLIC_LANGFUSE_CLOUD_REGION
NEXT_TELEMETRY_DISABLED
NODE_ENV
NODE_VERSION
PATH
PORT
YARN_VERSION
```

### Datastores

Postgres containers:

```text
POSTGRES_DB
POSTGRES_PASSWORD
POSTGRES_USER
```

ClickHouse:

```text
CLICKHOUSE_DB
CLICKHOUSE_PASSWORD
CLICKHOUSE_USER
```

MinIO:

```text
MINIO_ROOT_PASSWORD
MINIO_ROOT_USER
```

Redis containers do not need host-published secrets listed here beyond command/config ownership in Compose.

## LiteLLM Config Notes

Config file:

```text
/opt/arlo-infra/litellm_config.yaml
```

Observed behavior/config shape:

- `general_settings` includes master key and database URL.
- `litellm_settings` includes daily budget, Redis cache, prompt caching, JSON logs, and Langfuse success/failure callbacks.
- `router_settings` includes Redis routing state, retries, fallbacks, and latency-based routing.
- Model aliases include `haiku`, `elevated`, `critical`, `aux`, and fallback aliases.

Risk:

- Several model IDs appear old, future-looking, or otherwise not yet proven against providers in this environment.
- The `critical` alias description and model ID appear mismatched.
- No authenticated LiteLLM completion was run in this inventory pass.

## Homestead Dependency Check

Homestead does not currently depend on Langfuse or LiteLLM.

Homestead API env names observed:

```text
HOMESTEAD_REPO_PATH
OPENROUTER_API_KEY
OPENROUTER_APP_TITLE
OPENROUTER_BASE_URL
OPENROUTER_DEFAULT_MODEL
OPENROUTER_HTTP_REFERER
```

No Homestead `LANGFUSE_*` or `LITELLM_*` env names were observed on the API container.

Homestead network:

```text
homestead-private-os_default
```

Inherited stack network:

```text
arlo-net
```

## Reboot Behavior

The inherited containers were running after the deliberate Homestead reboot proof. Restart policies indicate:

- Langfuse app/data plane: `always`
- LiteLLM app/data plane: `unless-stopped`

This suggests reboot survival is already likely and was observed at a high level. Container-level app health remains mixed because `langfuse-web`, `langfuse-worker`, and `litellm` do not declare Docker healthchecks.

## Safety Assessment

### Langfuse

Useful:

- App endpoint reports OK.
- Required backing stores are running and healthy.
- Restart policy is durable.
- Already connected in the inherited LiteLLM config.

Not safe enough yet:

- Web UI is public on `5.78.206.130:3000`.
- MinIO API is public on `5.78.206.130:9090`.
- Credential/auth posture was not reviewed.
- Secret values and inherited defaults should be reviewed/rotated out-of-band before Homestead depends on this stack.

Recommendation:

Do not add Homestead tracing yet. First make Langfuse private or explicitly choose the exposure model, then verify login/project/API key posture without printing secrets.

### LiteLLM

Useful:

- Loopback-bound, so not directly exposed.
- Has Postgres and Redis backing services.
- Config already includes budget, cache, routing, fallbacks, and Langfuse callbacks.
- Can become a gateway later if the model map is cleaned up and authenticated calls pass.

Not proven yet:

- Health endpoints require auth and were not tested with a key.
- Model aliases are not trustworthy until tested.
- No container-level healthcheck.
- It is owned by `arlo-infra`, not Homestead.

Recommendation:

Do not route Homestead through LiteLLM yet. When ready, run an isolated authenticated LiteLLM proof from the server, then decide whether to keep the old `arlo-infra` gateway, fork its config into Homestead-owned infra, or retire it.

## Next Safe Moves

Recommended order:

1. Keep direct OpenRouter `/model/route` as the production path.
2. Privately harden Langfuse exposure before tracing:
   - bind `langfuse-web` to loopback or Tailscale only,
   - bind MinIO API to loopback/Docker network only unless there is a deliberate reason for public access,
   - verify auth/project/API key posture without printing secrets.
3. Run a no-routing LiteLLM proof:
   - authenticate locally against `127.0.0.1:4000`,
   - list models,
   - send one low-token prompt through one known-valid provider/model,
   - confirm whether Langfuse receives the trace.
4. Only after those pass, decide whether Homestead should integrate:
   - direct OpenRouter plus Langfuse tracing,
   - LiteLLM as optional gateway,
   - or a Homestead-owned clean-room Compose stack replacing inherited `arlo-infra`.

## Bottom Line

This stack is not junk, but it is also not ready to become Homestead's spine.

Langfuse is alive but currently too public. LiteLLM is private and potentially useful, but not yet provider-proven. Homestead should keep the direct OpenRouter route until these old machines are intentionally claimed, hardened, and tested.
