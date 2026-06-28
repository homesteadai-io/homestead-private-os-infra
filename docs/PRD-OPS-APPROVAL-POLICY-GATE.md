# PRD: Ops Approval Policy Gate

## Release Target

```text
v0-ops-approval-policy-gate
```

## Current Baseline

```text
main: e8c014f
latest tag: v0-manual-ops-probes
live node: Hetzner CPX51
private URL: http://100.112.20.36:8088
```

Homestead currently has:

- private runtime
- direct OpenRouter `/model/route` production default
- optional/private LiteLLM support, not default
- Langfuse tracing
- metadata receipts
- receipt index
- node/OS status
- Keep health memory
- review queue
- capability registry
- manual-only receipt-backed ops/probes

The current manual ops loop is:

```text
manual request -> action/probe -> receipt -> review queue -> capability map
```

This PRD defines the next step before any scheduler, runner, alert system, local mode, or dashboard work.

## Mission

Add a narrow approval/policy gate around manual ops so Homestead can answer:

```text
Is this requesting surface allowed to run this action/probe right now?
Why or why not?
Was the decision receipt-backed?
```

This is not autonomy. This is a permission boundary for explicit private calls.

## Product Principle

Homestead should not merely know what it can do. It should know when a caller is allowed to ask it to do that thing.

Tiny but important difference:

```text
capability = can the system do it?
policy = may this caller do it now?
```

## Non-Goals

Do not add:

- scheduled jobs
- autonomous runner
- background worker
- alerts
- dashboard
- local mode
- public exposure
- default LiteLLM routing
- prompt/content capture
- database dependency
- user accounts/auth system
- secrets in docs, logs, receipts, responses, or commits

Do not change Homestead `/model/route` behavior.

Do not change `MODEL_GATEWAY=direct` as the production default.

## Proposed Surface

Add API endpoints:

```text
GET /ops/policy
POST /ops/policy/check
```

Through private Caddy:

```text
GET /api/ops/policy
POST /api/ops/policy/check
```

Add MCP tools:

```text
homestead.ops_policy
homestead.check_ops_policy
```

Optionally add a decision summary into:

```text
GET /os/capabilities
GET /ops/actions
```

## Policy Model

Start with an in-code static policy. Do not add a database or admin editor yet.

Recommended default:

```json
{
  "mode": "manual_only",
  "default_decision": "deny",
  "rules": [
    {
      "surface": "codex",
      "actions": ["refresh_node_status", "write_status_receipt"],
      "probes": ["node_status", "receipt_write", "exposure_config"],
      "decision": "allow"
    },
    {
      "surface": "codex",
      "actions": ["sync_keep_health"],
      "probes": ["keep_health_sync", "model_route", "litellm_private_health"],
      "decision": "allow_with_receipt"
    },
    {
      "surface": "unknown",
      "actions": [],
      "probes": ["node_status"],
      "decision": "allow_read_probe_only"
    }
  ]
}
```

Implementation can derive the requesting surface from:

```text
x-homestead-surface
requesting_agent
user-agent
```

Trusted surfaces must not be accepted from caller-supplied names alone. For v0,
privileged surface claims such as `codex`, `mcp`, or `manual_cli` require a
configured shared policy token:

```text
OPS_POLICY_SURFACE_TOKEN=<server-side API token>
HOMESTEAD_MCP_POLICY_TOKEN=<same value for MCP facade>
x-homestead-policy-token: <same value on trusted calls>
```

If the token is missing or wrong, treat the caller as `unknown`.

Normalize common callers:

```text
codex
manual_cli
mcp
unknown
```

## Policy Decisions

Policy check response should include:

```text
ok
decision: allow | deny | allow_with_receipt
surface
operation_type: action | probe
operation
reason
receipt_required
manual_only=true
```

Example:

```json
{
  "ok": true,
  "decision": "allow_with_receipt",
  "surface": "codex",
  "operation_type": "probe",
  "operation": "model_route",
  "reason": "codex may run explicit model_route probes with receipt",
  "receipt_required": true,
  "manual_only": true
}
```

## Enforcement

Apply policy checks to:

```text
POST /ops/actions/run
POST /ops/probes/run
```

Policy denial should:

- return safe `403`
- not run the action/probe
- not call model providers
- not sync Keep health
- not write prompt/content
- write a denial receipt if receipt writing is available
- set `review_required=true` on denial receipts

Policy allow should preserve current manual ops behavior.

Policy failures must fail closed:

```text
if policy cannot classify the operation -> deny
if policy code errors -> deny safely
```

Do not fail closed for receipt writer failure after an allow decision. Manual action/probe behavior can still return safe `receipt_error` if the operation itself succeeded and receipt writing failed, matching current fail-open receipt behavior where appropriate.

## Receipts

Add receipt task:

```text
ops_policy_decision
```

Policy decision receipts should include metadata only:

```text
surface
operation_type
operation
decision
allowed
reason
receipt_required
manual_only
policy_version
requesting_agent
timestamp
```

Do not include:

- prompt
- assistant content
- headers
- API keys
- raw env
- stack traces

Policy denials should be visible in:

```text
GET /api/receipts/review
```

Recent ops should include policy decisions if useful:

```text
GET /api/ops/recent?limit=20
```

## Capability Registry Update

Update `GET /os/capabilities`:

```text
ops_policy_gate:
  enabled: true
  status: active
  mode: manual_only
  default_decision: deny
  write_access: policy_decision_receipts
  scheduler_enabled: false
  autonomous_execution: false
```

## Tests

Add API tests:

- `GET /ops/policy` returns static policy with `default_decision=deny`
- `POST /ops/policy/check` allows known safe action for known surface
- trusted surface claims require the policy token; spoofed surfaces are denied
- unknown surface/action is denied safely
- denied action does not run the action/probe
- denied action writes safe `ops_policy_decision` receipt with `review_required=true`
- allowed manual action still runs and writes receipt
- allowed system probe still runs and writes receipt
- direct `/keep/health/sync` cannot bypass the `sync_keep_health` action policy
- policy check does not leak secrets, headers, prompt, content, or raw env
- malformed operation type/action/probe returns safe 400 or deny
- old receipt formats do not break review queue/recent ops

Add MCP tests:

- tool list includes `homestead.ops_policy`
- tool list includes `homestead.check_ops_policy`
- dispatch maps to `/ops/policy`
- dispatch maps to `/ops/policy/check`

Run existing tests:

```powershell
$env:PYTHONPATH = "services/homestead-api"
.\.venv\Scripts\python.exe -m pytest .\services\homestead-api\tests
$env:PYTHONPATH = "services/homestead-mcp"
.\.venv\Scripts\python.exe -m pytest .\services\homestead-mcp\tests
```

Run config checks:

```powershell
docker compose --env-file infra\.env.example -f infra\docker-compose.yml config --quiet
docker compose --env-file infra\.env.example -f infra\docker-compose.yml -f infra\docker-compose.litellm.yml config --quiet
git diff --check
```

Run source secret scan before commit.

## Live Acceptance

Deploy branch to Hetzner before merge.

Check:

```powershell
curl.exe --max-time 10 http://100.112.20.36:8088/health
curl.exe --max-time 10 http://100.112.20.36:8088/api/ops/policy
curl.exe --max-time 10 http://100.112.20.36:8088/api/os/capabilities
```

Allowed policy check:

```powershell
$policyToken = "<set OPS_POLICY_SURFACE_TOKEN value>"
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"operation_type":"probe","operation":"node_status","requesting_agent":"codex-live-acceptance"}'
curl.exe --max-time 10 -X POST http://100.112.20.36:8088/api/ops/policy/check -H "Content-Type: application/json" -H "x-homestead-surface: codex" -H "x-homestead-policy-token: $policyToken" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Denied policy check:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"operation_type":"action","operation":"turn_on_runner","requesting_agent":"unknown"}'
curl.exe --max-time 10 -X POST http://100.112.20.36:8088/api/ops/policy/check -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Allowed operation still works:

```powershell
$policyToken = "<set OPS_POLICY_SURFACE_TOKEN value>"
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"probe":"node_status","requesting_agent":"codex-live-acceptance"}'
curl.exe --max-time 10 -X POST http://100.112.20.36:8088/api/ops/probes/run -H "Content-Type: application/json" -H "x-homestead-surface: codex" -H "x-homestead-policy-token: $policyToken" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Denied operation does not run:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"action":"turn_on_runner","requesting_agent":"unknown"}'
curl.exe --max-time 10 -X POST http://100.112.20.36:8088/api/ops/actions/run -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected:

```text
allowed checks return allow/allow_with_receipt
denied checks return deny
denied operation returns safe 403
denial receipt appears in review queue
no prompt/content/secrets/raw env in responses or receipts
```

Public exposure must remain closed:

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

After merge:

```text
deploy from main
verify live from main
tag v0-ops-approval-policy-gate
```

## Copy-Ready Next Window Prompt

```text
Continue Homestead Private OS Infra.

Repo:
C:\Users\Adam\OneDrive\Desktop\homestead-private-os-infra

Current production baseline:
main at e8c014f
tag: v0-manual-ops-probes
live private URL: http://100.112.20.36:8088

First read:
docs/PRD-OPS-APPROVAL-POLICY-GATE.md
docs/HANDOFF-MANUAL-OPS-PROBES.md

Mission:
Implement v0-ops-approval-policy-gate.

Add a narrow approval/policy gate for manual ops:
- GET /ops/policy
- POST /ops/policy/check
- MCP homestead.ops_policy
- MCP homestead.check_ops_policy
- enforce policy on POST /ops/actions/run and POST /ops/probes/run
- write metadata-only ops_policy_decision receipts
- denied actions/probes must not run and should appear in review queue

Rules:
- Do not add scheduler, runner, alerts, dashboard, local mode, public exposure, database, auth system, or autonomous behavior.
- Do not change /model/route behavior.
- Keep MODEL_GATEWAY=direct as production default.
- Do not route through LiteLLM by default.
- Do not print or commit secrets.
- Do not capture prompt/content.
- Keep public :8088, :4000, :3000, and :9090 closed.

Acceptance:
- local API/MCP tests pass
- compose config passes with and without LiteLLM overlay
- live health passes
- policy allow/deny checks pass
- denied operation returns safe 403 and does not execute
- denial receipt appears in review queue
- manual allowed probe still works
- no secrets/prompt/content in responses or receipts
- deploy from main after merge
- tag v0-ops-approval-policy-gate
```
