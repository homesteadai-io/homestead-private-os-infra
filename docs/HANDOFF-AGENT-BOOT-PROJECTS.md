# Handoff: Agent Boot And Project Registry

## Release Target

```text
v0-agent-boot-projects
```

## Mission

Give agents one standard entrance into Homestead without giving them autonomy.

The boot loop is:

```text
agent asks for boot context -> reads OS status/capabilities/projects/manual ops -> Adam still decides work
```

## Boundaries

This release does not add:

- command creation
- sessions
- output capsules
- scheduler
- runner
- background automation
- dashboard
- alerts
- local mode
- public exposure
- prompt/completion capture
- Lyhna work
- witness fields

Adam is the authority. Agents and Codex are operators.

## New API Surface

```text
GET /agent/boot
GET /os/projects
GET /os/projects/{project_id}
```

Through the private Caddy API path:

```text
GET /api/agent/boot
GET /api/os/projects
GET /api/os/projects/{project_id}
```

## New MCP Tools

```text
homestead.agent_boot
homestead.projects
homestead.project_context
```

## Project Registry

The registry is config-backed in code for v0. It is read-only and does not add
new persistence.

Initial project ids:

```text
homestead-private-os
the-keep
lyhna-witness
loop-forge
frostbite
creative-coatings
```

`lyhna-witness` is listed for orientation only. This release does no Lyhna work
and adds no witness fields.

## Agent Boot Contents

`/agent/boot` returns:

- orientation
- Adam authority model
- loop protocol
- read-first pointers
- project registry summaries
- default project context
- node health summary
- capability registry
- manual ops catalog
- recent ops
- review queue summary
- disabled capability status
- content policy

It reuses existing status, capabilities, receipts, ops, and policy surfaces.

## Acceptance

Local:

```powershell
$env:PYTHONPATH = "services/homestead-api"
.\.venv\Scripts\python.exe -m pytest .\services\homestead-api\tests
$env:PYTHONPATH = "services/homestead-mcp"
.\.venv\Scripts\python.exe -m pytest .\services\homestead-mcp\tests
docker compose --env-file infra\.env.example -f infra\docker-compose.yml config --quiet
docker compose --env-file infra\.env.example -f infra\docker-compose.yml -f infra\docker-compose.litellm.yml config --quiet
git diff --check
```

Live:

```powershell
curl.exe --max-time 10 http://100.112.20.36:8088/health
curl.exe --max-time 10 http://100.112.20.36:8088/api/agent/boot
curl.exe --max-time 10 http://100.112.20.36:8088/api/os/projects
curl.exe --max-time 10 http://100.112.20.36:8088/api/os/projects/homestead-private-os
curl.exe --max-time 10 http://100.112.20.36:8088/api/os/capabilities
```

MCP:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"tool":"homestead.agent_boot","arguments":{}}'
curl.exe --max-time 10 -X POST http://100.112.20.36:8088/mcp/call -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected:

```text
agent_boot includes orientation, Adam authority, loop protocol, capabilities, health, manual ops, and project pointers
projects list includes the configured project ids
project_context returns one project by id
runner/local_mode/dashboard/alerts remain disabled
MODEL_GATEWAY remains direct
no secrets, prompt content, completion content, raw env, or token values appear
```

Public closure must still hold:

```powershell
curl.exe --max-time 10 http://5.78.206.130:8088/health
curl.exe --max-time 10 http://5.78.206.130:4000/health
curl.exe --max-time 10 http://5.78.206.130:3000/
curl.exe --max-time 10 http://5.78.206.130:9090/minio/health/live
```

Expected:

```text
all public probes fail
```

## Next Release

After this is live and tagged, continue to:

```text
v0-command-sessions
```
