# Handoff: Review Queue And Capability Map

## Release Target

```text
v0-review-and-capability-map
```

## Scope

This release adds the next attention/control layer above the existing observability spine:

- receipt review queue
- capability registry
- Keep health folder policy

It does not add runners, alerts, dashboard work, local mode, public exposure, or LiteLLM routing changes.

## New API Surface

```text
GET /receipts/review?limit=20
GET /os/capabilities
```

Through Caddy's private API path:

```text
GET /api/receipts/review?limit=20
GET /api/os/capabilities
```

## New MCP Tools

```text
homestead.receipts_review
homestead.os_capabilities
```

## Review Queue Behavior

The review queue is read-only and metadata-only.

Receipts enter the queue when any of these are true:

- `review_required=true`
- `verdict` is not `ok` or `recorded`
- `metadata.ok=false`
- `metadata.error_summary` exists

The queue returns summaries only. It does not return Markdown bodies, prompt content, response content, headers, API keys, raw env values, or stack traces.

## Capability Registry Behavior

The capability registry is the agent-readable boundary map for Homestead:

```text
cloud_node_status: active
os_context: active
capability_registry: active
model_route: active
direct_openrouter_gateway: production_default
litellm_gateway: available_private_optional
langfuse_tracing: optional_fail_open
model_route_receipts: optional_fail_open
receipt_index: active
review_queue: active
keep_health_sync: explicit_only
local_mode: disabled
runner: disabled
alerts: disabled
dashboard: disabled
```

Agents should use only enabled `agent_safe=true` capabilities. Disabled or future-only entries are unavailable until Adam explicitly chooses those release paths.

## Keep Health Folder Policy

```text
/System Receipts/Homestead Health is agent-readable operational memory.
It may remain dirty/untracked until a separate Keep sync policy exists.
Agents may read it for current node context.
Agents must not auto-commit it.
Agents must not treat it as infra source.
Agents must not write prompt/content/secrets/raw env into it.
```

## Acceptance

Local:

```powershell
$env:PYTHONPATH = "services/homestead-api"
.\.venv\Scripts\python.exe -m pytest .\services\homestead-api\tests
$env:PYTHONPATH = "services/homestead-mcp"
.\.venv\Scripts\python.exe -m pytest .\services\homestead-mcp\tests
docker compose --env-file infra\.env.example -f infra\docker-compose.yml config --quiet
docker compose --env-file infra\.env.example -f infra\docker-compose.yml -f infra\docker-compose.litellm.yml config --quiet
```

Live:

```powershell
curl.exe --max-time 10 http://100.112.20.36:8088/health
curl.exe --max-time 10 http://100.112.20.36:8088/api/receipts/review?limit=20
curl.exe --max-time 10 http://100.112.20.36:8088/api/os/capabilities
curl.exe --max-time 10 http://100.112.20.36:8088/api/node/status
```

MCP:

```powershell
curl.exe --max-time 10 http://100.112.20.36:8088/mcp/tools
```

Public exposure must remain closed:

```powershell
curl.exe --max-time 10 http://5.78.206.130:8088/health
curl.exe --max-time 10 http://5.78.206.130:4000/health
curl.exe --max-time 10 http://5.78.206.130:3000/
curl.exe --max-time 10 http://5.78.206.130:9090/minio/health/live
```

## Recommendation

After this release, the observability/control spine is complete enough for v0:

```text
health -> trace -> receipt -> index -> status -> Keep memory -> review queue -> capability map
```

The next major frontier is controlled execution. Do not add runners, alerts, local mode, or dashboards until the enabled/disabled capability boundaries are routinely used by agents.
