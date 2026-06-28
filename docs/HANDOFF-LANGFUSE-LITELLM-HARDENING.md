# Langfuse / LiteLLM Private Hardening Handoff

Updated: 2026-06-28

## Scope

Task 4B hardened the Homesteadal inherited Langfuse/MinIO public exposure before any Homestead integration.

This task did not add Langfuse tracing, did not route Homestead through LiteLLM, and did not change Homestead `/model/route`.

## Server / Owner

Hetzner node:

```text
root@5.78.206.130
```

Tailscale IP:

```text
100.112.20.36
```

Homesteadal inherited stack Compose file:

```text
/opt/arlo-infra/docker-compose.yml
```

Current Docker Compose project name on the server:

```text
arlo-infra
```

Note: the server still uses the historical project/path name `arlo-infra`. Renaming the live Compose project or directory should be treated as a separate migration because it can recreate containers, networks, and labels.

## Backup

Before editing, the Compose file was backed up on the server:

```text
/opt/arlo-infra/docker-compose.yml.pre-private-hardening-20260628T013348Z
```

## Changes Made

Only published bind addresses were changed.

Langfuse web:

```text
before: "3000:3000"
after:  "100.112.20.36:3000:3000"
```

MinIO API:

```text
before: "9090:9000"
after:  "127.0.0.1:9090:9000"
```

Unchanged:

```text
LiteLLM:       "127.0.0.1:4000:4000"
MinIO console: "127.0.0.1:9091:9001"
```

## Reload

Compose config was validated with:

```bash
cd /opt/arlo-infra
docker compose config --quiet
```

Only affected services were recreated:

```bash
cd /opt/arlo-infra
docker compose up -d langfuse-minio langfuse-web
```

Observed reload behavior:

```text
langfuse-minio Recreate -> Started -> Healthy
langfuse-web   Recreate -> Started
```

Databases, Redis, ClickHouse, LiteLLM, and Homestead services were not intentionally recreated.

## Final Exposure Map

| Service | Intended access | Observed bind / result |
| --- | --- | --- |
| Langfuse web | Tailscale only | `100.112.20.36:3000->3000/tcp` |
| MinIO API | Host loopback only | `127.0.0.1:9090->9000/tcp` |
| MinIO console | Host loopback only | `127.0.0.1:9091->9001/tcp` |
| LiteLLM | Host loopback only | `127.0.0.1:4000->4000/tcp` |
| Homestead API | Tailscale through Caddy | `100.112.20.36:8088` |

## Acceptance Evidence

### Public Langfuse Closed

From laptop:

```text
GET http://5.78.206.130:3000/
curl timed out
HTTP code: 000
```

### Public MinIO API Closed

From laptop:

```text
GET http://5.78.206.130:9090/minio/health/live
curl timed out
HTTP code: 000
```

### Private Langfuse Works

From laptop over Tailscale:

```text
GET http://100.112.20.36:3000/api/public/health
200 application/json
{"status":"OK","version":"3.164.0"}
```

### MinIO Private Health Works

From server loopback:

```text
GET http://127.0.0.1:9090/minio/health/live
200
```

### LiteLLM Remains Loopback-Only

Docker bind:

```text
127.0.0.1:4000->4000/tcp
```

Tailscale probe:

```text
GET http://100.112.20.36:4000/health
connection failed
HTTP code: 000
```

### Homestead Health Still Passes

From laptop over Tailscale:

```text
GET http://100.112.20.36:8088/health
200
{"ok":true,"service":"homestead-api","version":"0.1.0","repo_path":"/workspace/keep"}
```

### Homestead Model Route Still Works

From laptop over Tailscale:

```text
POST http://100.112.20.36:8088/model/route
200
model: openai/gpt-4.1-mini-2025-04-14
finish_reason: stop
```

This confirms Homestead remains on the direct OpenRouter route. No LiteLLM routing was introduced.

## Current Recommendation

Task 4C can add optional Langfuse tracing around Homestead `/model/route`, but it should be done as a narrow, opt-in integration:

- keep direct OpenRouter routing as the serving path,
- add tracing behind explicit `LANGFUSE_*` env vars and an enable flag,
- fail open if tracing is unavailable,
- do not route through LiteLLM,
- do not expose Langfuse or MinIO publicly,
- verify traces land in Langfuse through the Tailscale-only UI.

LiteLLM should remain a later gateway candidate, not part of Task 4C.

## Bottom Line

The inherited Langfuse surface is now private enough to consider optional tracing next. The old public edges on Langfuse web and MinIO API are closed, LiteLLM remains loopback-only, and Homestead stayed healthy with direct OpenRouter model routing.
