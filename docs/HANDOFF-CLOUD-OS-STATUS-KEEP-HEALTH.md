# Cloud OS Status And Keep Health Handoff

Updated: 2026-06-28

## Scope

This release implements the next three Homestead cloud-first phases as one narrow spine:

1. `v0-node-status` - the node can describe its current state.
2. `v0-keep-health-receipts` - the node can write metadata-only health summaries into The Keep.
3. `v0-cloud-control-plane` - the cloud node exposes OS status/context while local mode remains visible and disabled.

No runner, dashboard, alerts, prompt capture, local daemon, or autonomous workflow engine was added.

## API Surface

Private API endpoints:

```text
GET /node/status
GET /os/status
GET /os/context
POST /keep/health/sync
```

Through live Caddy:

```text
GET http://100.112.20.36:8088/api/node/status
GET http://100.112.20.36:8088/api/os/context
POST http://100.112.20.36:8088/api/keep/health/sync
```

## MCP Surface

Tools added:

```text
homestead.node_status
homestead.os_status
homestead.os_context
homestead.sync_keep_health
```

## Keep Health Folder

Default repo-relative path:

```text
System Receipts/Homestead Health
```

Configured by:

```text
KEEP_HEALTH_DIR=System Receipts/Homestead Health
```

Files written by explicit sync:

```text
index.md
homestead-latest.md
homestead-health-log.md
daily/YYYY-MM-DD.md
gateway/gateway-health.md
snapshots/<timestamp>.md
homestead-review-required.md only when review_required count is nonzero
```

Summaries are metadata-only. They include gateway, commit/tag, receipt counts, latest receipt id/timestamp/gateway, tracing status, exposure assumptions, and local-mode status. They omit prompts, completions, headers, secret values, raw env, and full private context.

## Cloud Control Plane Boundary

`/os/context` is cloud-first. It reports:

```text
cloud_first=true
local_mode.enabled=false
local_mode.status=available_later
local_mode.activation=manual_switch_only
runner.enabled=false
alerts.enabled=false
dashboard.enabled=false
```

Local is represented as a future manual switch, not a current execution mode.

## Recommendation

Use `homestead.node_status` at the start of future agent work. Use `homestead.sync_keep_health` after meaningful deploy/proof milestones so The Keep becomes the readable health meter for agents when Adam asks for system state.
