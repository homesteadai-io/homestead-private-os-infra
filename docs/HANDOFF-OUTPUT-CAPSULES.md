# Handoff: Output Capsules

## Release Target

```text
v0-output-capsules
```

## Mission

Create durable Homestead output bundles so useful work can survive beyond a
single command/session.

The loop is:

```text
command/session work -> output capsule -> next agent reads capsule -> Adam remains authority
```

## Approved Write Lane

Adam approved `/System Outputs` as the top-level Keep write lane for output
capsules.

Policy doc:

```text
/docs/OUTPUT-CAPSULE-WRITE-POLICY.md
```

Bundle path shape:

```text
/System Outputs/{project_id}/{YYYY-MM-DD}-{slug}/
```

Example:

```text
/System Outputs/homestead-private-os/2026-06-28-agent-boot-projects/
```

## Boundaries

This release does not add:

- Lyhna work
- witness fields
- runner
- scheduler
- dashboard
- local mode
- local model routing
- alerts
- workflow engine
- autonomous command claiming
- public exposure
- prompt/completion capture by default

Output capsules do not replace receipts. Receipts remain the system behavior
proof lane.

## New API Surface

```text
POST /outputs
GET /outputs
GET /outputs/{output_id}
```

Through the private Caddy API path:

```text
POST /api/outputs
GET /api/outputs
GET /api/outputs/{output_id}
```

## New MCP Tools

```text
homestead.outputs_write
homestead.outputs_list
homestead.outputs_read
```

## Required Bundle Contents

Every output capsule includes:

```text
index.md
HANDOFF.md
handoff.json
CAPSULE.md
capsule.json
next-ai-prompt.md
okf/
pam/
```

`index.md` is the Keep collection entrypoint. It gives the folder a stable
markdown front door and links to the bundle files.

## Policy

Writes are policy-gated:

```text
operation_type=output operation=write
```

Denied writes do not create a bundle. They write metadata-only policy denial
receipts with `review_required=true`.

Allowed writes include safe policy metadata in bundle JSON. They do not include
headers, tokens, raw env, prompt captures, completion captures, or private model
transcript content by default.

## Acceptance

Local:

```powershell
$env:PYTHONPATH = "services/homestead-api"
pytest .\services\homestead-api\tests
$env:PYTHONPATH = "services/homestead-mcp"
pytest .\services\homestead-mcp\tests
docker compose --env-file infra\.env.example -f infra\docker-compose.yml config --quiet
docker compose --env-file infra\.env.example -f infra\docker-compose.yml -f infra\docker-compose.litellm.yml config --quiet
git diff --check
```

PR:

```text
Open PR for v0-output-capsules.
Request external review before merge.
```

Live after merge:

```powershell
curl.exe --max-time 10 http://100.112.20.36:8088/health
curl.exe --max-time 10 http://100.112.20.36:8088/api/outputs
curl.exe --max-time 10 http://100.112.20.36:8088/api/os/capabilities
curl.exe --max-time 10 http://100.112.20.36:8088/api/agent/boot
curl.exe --max-time 10 http://100.112.20.36:8088/mcp/tools
```

Expected:

```text
POST /api/outputs writes a complete bundle under /System Outputs/{project_id}/{YYYY-MM-DD}-{slug}/
GET /api/outputs lists output summaries
GET /api/outputs/{output_id} reads one output
MCP tools dispatch to equivalent API routes
output can link to project_id, command_id, and session_id
bundle includes all required files/folders
capability registry reports output_capsules manual_only
runner/local_mode/dashboard/alerts remain disabled
MODEL_GATEWAY remains direct
no secrets, raw prompt captures, completion captures, raw env, or token values appear
```

Public closure must still hold:

```powershell
curl.exe --max-time 10 http://5.78.206.130:8088/health
curl.exe --max-time 10 http://5.78.206.130:4000/health
curl.exe --max-time 10 http://5.78.206.130:3000/
curl.exe --max-time 10 http://5.78.206.130:9090/minio/health/live
```
