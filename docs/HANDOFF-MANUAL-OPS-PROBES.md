# Handoff: Manual Ops And System Probes

## Release Target

```text
v0-manual-ops-probes
```

## Mission

Move Homestead from passive inspectability into controlled execution without adding autonomy.

The loop is:

```text
manual request -> action/probe -> receipt -> review queue -> capability map -> Keep memory when explicitly synced
```

## Boundaries

This release does not add:

- scheduled jobs
- autonomous runners
- alerts
- dashboard work
- local mode
- public exposure
- default LiteLLM routing
- prompt/content capture

Direct OpenRouter remains the production default for `/model/route`.

## New API Surface

```text
GET /ops/actions
POST /ops/actions/run
POST /ops/probes/run
GET /ops/recent?limit=20
```

Through the private Caddy API path:

```text
GET /api/ops/actions
POST /api/ops/actions/run
POST /api/ops/probes/run
GET /api/ops/recent?limit=20
```

## New MCP Tools

```text
homestead.list_manual_ops
homestead.run_manual_action
homestead.run_system_probe
homestead.list_recent_ops
```

## Manual Actions

Allowed actions:

```text
refresh_node_status
sync_keep_health
write_status_receipt
```

Each action is explicit and receipt-backed. `sync_keep_health` writes operational memory into The Keep; the others write only receipts.

## System Probes

Allowed probes:

```text
node_status
receipt_write
keep_health_sync
model_route
litellm_private_health
exposure_config
all
```

Probe behavior:

- `node_status` confirms the API can self-report.
- `receipt_write` proves the append-only receipt writer.
- `keep_health_sync` explicitly syncs health memory into The Keep.
- `model_route` performs a low-token `/model/route` call through the configured gateway and omits assistant content from the probe response.
- `litellm_private_health` checks private LiteLLM `/health` only when LiteLLM env is configured.
- `exposure_config` checks configured exposure assumptions.
- `all` runs every probe once, sequentially.

Failed probes write `review_required=true` receipts when the receipt writer is available and should appear in `/receipts/review`.

## Capability Registry

`/os/capabilities` now includes:

```text
manual_ops: enabled, manual_only
scheduler_enabled: false
autonomous_execution: false
```

Agents should treat this as permission for explicit private API/MCP calls only. It is not permission to schedule, loop, daemonize, or take unsupervised action.

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
curl.exe --max-time 10 http://100.112.20.36:8088/api/ops/actions
curl.exe --max-time 10 http://100.112.20.36:8088/api/os/capabilities
```

Manual action:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"action":"refresh_node_status","requesting_agent":"acceptance-manual-op"}'
curl.exe --max-time 10 -X POST http://100.112.20.36:8088/api/ops/actions/run -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

System probe:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"probe":"model_route","requesting_agent":"acceptance-model-probe","max_tokens":50}'
curl.exe --max-time 60 -X POST http://100.112.20.36:8088/api/ops/probes/run -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Public closure must still hold:

```powershell
curl.exe --max-time 10 http://5.78.206.130:8088/health
curl.exe --max-time 10 http://5.78.206.130:4000/health
curl.exe --max-time 10 http://5.78.206.130:3000/
curl.exe --max-time 10 http://5.78.206.130:9090/minio/health/live
```

## Recommendation

This release is the bridge into controlled execution. After it is stable, the next safe phase is not a runner yet. The next phase should be a very small approval/policy gate around which manual actions are allowed for which requesting surfaces.
