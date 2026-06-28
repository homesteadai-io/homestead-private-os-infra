# Handoff: Command Sessions

## Release Target

```text
v0-command-sessions
```

## Mission

Add Adam-commanded work tracking without adding autonomy.

The loop is:

```text
Adam creates command -> agent starts manual session -> agent updates command/session -> Adam remains authority
```

## Boundaries

This release does not add:

- runner
- scheduler
- background automation
- local mode
- dashboard
- alerts
- autonomous command claiming
- workflow engine
- multi-agent planner
- public exposure
- prompt/completion capture
- Lyhna work
- witness fields

`claimed` is a manual command state only. No endpoint auto-claims work.

## New API Surface

```text
POST /commands
GET /commands
GET /commands/{command_id}
PATCH /commands/{command_id}

POST /agent/sessions/start
POST /agent/sessions/end
GET /agent/sessions
GET /agent/sessions/{session_id}
```

Through the private Caddy API path:

```text
POST /api/commands
GET /api/commands
GET /api/commands/{command_id}
PATCH /api/commands/{command_id}

POST /api/agent/sessions/start
POST /api/agent/sessions/end
GET /api/agent/sessions
GET /api/agent/sessions/{session_id}
```

## New MCP Tools

```text
homestead.commands_create
homestead.commands_list
homestead.commands_read
homestead.commands_update
homestead.session_start
homestead.session_end
homestead.sessions
homestead.session_read
```

## State

Command and session state is an append-only JSONL event log.

Default path:

```text
/data/state/command-sessions/
```

Config:

```text
HOMESTEAD_STATE_DIR=/data/state
```

This is runtime state, not Keep doctrine. It does not create a new top-level Keep
folder.

## Policy

Write endpoints are policy-gated:

```text
operation_type=command operation=create|update
operation_type=session operation=start|end
```

Read endpoints are read-only.

Denied writes do not mutate command/session state. They write metadata-only
policy denial receipts with `review_required=true`.

Allowed writes include safe policy metadata in the command/session event. They do
not include headers, tokens, raw env, prompts, completions, or secrets.

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

Live:

```powershell
curl.exe --max-time 10 http://100.112.20.36:8088/health
curl.exe --max-time 10 http://100.112.20.36:8088/api/commands
curl.exe --max-time 10 http://100.112.20.36:8088/api/agent/sessions
curl.exe --max-time 10 http://100.112.20.36:8088/api/os/capabilities
curl.exe --max-time 10 http://100.112.20.36:8088/api/agent/boot
curl.exe --max-time 10 http://100.112.20.36:8088/mcp/tools
```

Write acceptance requires the configured policy token. Do not print token values.

Expected:

```text
commands can be created, listed, read, and updated
invalid command status returns 400
sessions can be started, ended, listed, and read
session start does not auto-claim or auto-update the command
commands can be linked to a session by explicit manual update
MCP tools dispatch to equivalent API routes
capability registry reports command_sessions manual_only
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
v0-output-capsules
```
