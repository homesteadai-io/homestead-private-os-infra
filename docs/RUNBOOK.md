# Runbook

This runbook deploys Homestead Private OS Infra v0 to the Hetzner CPX51 node.

v0 is deployment-only:
- no default LiteLLM dependency; `/model/route` defaults to direct OpenRouter
- no GPU provider
- no required Langfuse dependency; optional `/model/route` tracing is env-gated and fail-open
- no SMTP/email
- no autonomous runner

## Live v0 Topology

As of the Hetzner v0 deployment:

- Hetzner is the always-on node. Adam's laptop is only a client.
- The SSH tunnel is a fallback doorway, not the production access path.
- Existing Nginx owns public `80/443`; do not replace or reconfigure it for v0.
- Homestead Caddy is private on the Tailscale IP with host ports `8088/8443`.
- Public `:8088` should remain unavailable from the internet.
- Tailscale is the normal private access path for laptop access, and later phone access.
- Future automation runner work must run on Hetzner through Docker Compose or systemd, not on Adam's laptop.

Current live values:

```text
Server public IP: 5.78.206.130
Tailscale host: homestead-cpx51
Tailscale IP: 100.112.20.36
Homestead HTTP: http://100.112.20.36:8088
Homestead HTTPS bind: 100.112.20.36:8443
Private Langfuse UI: http://100.112.20.36:3000
```

## Server Layout

```text
/opt/homestead/
  runtime/    # clone of homesteadai-io/homestead-private-os-infra
  the-keep/   # Adam's second-brain OKF library/context graph checkout
  data/       # receipts, logs, persistent runtime data
  backups/    # backup output
  secrets/    # local-only env files, not committed
```

Runtime env file:

```text
/opt/homestead/secrets/runtime.env
```

Docker data is on the mounted Hetzner volume:

```text
/var/lib/docker -> /mnt/HC_Volume_105361821/docker
```

The live Docker daemon config also pins the data root and rotates JSON logs:

```json
{
  "data-root": "/mnt/HC_Volume_105361821/docker",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## One-Time Hetzner Bootstrap

SSH into the CPX51 node:

```bash
ssh root@<server-ip>
```

Create the Homestead folders and install Docker:

```bash
apt-get update
apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
mkdir -p /opt/homestead/runtime /opt/homestead/the-keep /opt/homestead/data /opt/homestead/backups
install -d -m 0700 /opt/homestead/secrets
```

Clone the runtime repo:

```bash
git clone https://github.com/homesteadai-io/homestead-private-os-infra.git /opt/homestead/runtime
cd /opt/homestead/runtime
git checkout main
```

If deploying this branch before merge, use:

```bash
cd /opt/homestead/runtime
git fetch origin codex/hetzner-v0-deploy
git checkout codex/hetzner-v0-deploy
```

Alternative bootstrap script after cloning:

```bash
cd /opt/homestead/runtime
bash infra/scripts/bootstrap-server.sh
```

## Clone The Keep

Clone Adam's Keep/OKF context graph into `/opt/homestead/the-keep`.

```bash
git clone <the-keep-repo-url> /opt/homestead/the-keep
```

Verify it is a git work tree:

```bash
git -C /opt/homestead/the-keep status --short --branch
```

## Create Runtime Env

```bash
cp /opt/homestead/runtime/infra/.env.example /opt/homestead/secrets/runtime.env
chmod 600 /opt/homestead/secrets/runtime.env
nano /opt/homestead/secrets/runtime.env
```

Use these v0 values:

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
CADDY_HTTP_BIND=127.0.0.1
CADDY_HTTPS_BIND=127.0.0.1
CADDY_HTTP_PORT=80
CADDY_HTTPS_PORT=443
```

If another service already owns ports 80/443, keep Homestead private on alternate loopback ports:

```bash
CADDY_HTTP_BIND=127.0.0.1
CADDY_HTTPS_BIND=127.0.0.1
CADDY_HTTP_PORT=8088
CADDY_HTTPS_PORT=8443
```

For direct Tailscale access when public Nginx already owns `80/443`, replace both Caddy bind values with the server's Tailscale IP from `tailscale ip -4` and keep the private host ports:

```bash
CADDY_HTTP_BIND=<tailscale-ip>
CADDY_HTTPS_BIND=<tailscale-ip>
CADDY_HTTP_PORT=8088
CADDY_HTTPS_PORT=8443
```

For public DNS testing, use `0.0.0.0` only after accepting that v0 API/MCP surfaces are unauthenticated:

```bash
CADDY_HTTP_BIND=0.0.0.0
CADDY_HTTPS_BIND=0.0.0.0
```

Set OpenRouter values only in local/server env files.

Verify OpenRouter variable names without printing secret values:

```bash
grep -E '^(OPENROUTER_API_KEY|OPENROUTER_BASE_URL|OPENROUTER_DEFAULT_MODEL|OPENROUTER_HTTP_REFERER|OPENROUTER_APP_TITLE)=' /opt/homestead/secrets/runtime.env | sed 's/=.*/=<set>/'
```

Optional LiteLLM gateway support exists, but direct OpenRouter is the production default.

```bash
MODEL_GATEWAY=direct
LITELLM_BASE_URL=http://litellm:4000
LITELLM_API_KEY=
LITELLM_DEFAULT_MODEL=haiku
LITELLM_SEND_TEMPERATURE=false
```

Do not set `MODEL_GATEWAY=litellm` unless the deployment includes the optional private network overlay:

```bash
docker compose \
  --env-file /opt/homestead/secrets/runtime.env \
  -f infra/docker-compose.yml \
  -f infra/docker-compose.litellm.yml \
  up -d --build homestead-api homestead-mcp caddy
```

The overlay attaches `homestead-api` to the existing external Docker network `arlo-net`, where the inherited LiteLLM container is reachable as `http://litellm:4000`. Do not expose LiteLLM publicly or over Tailscale to make this work.

When using the overlay, use the internal Langfuse host for Homestead tracing:

```bash
LANGFUSE_HOST=http://langfuse-web:3000
```

The Tailscale URL remains the operator UI path from Adam's laptop, but the API container should use Docker DNS.

Verify LiteLLM variable names without printing values:

```bash
grep -E '^(MODEL_GATEWAY|LITELLM_BASE_URL|LITELLM_API_KEY|LITELLM_DEFAULT_MODEL|LITELLM_SEND_TEMPERATURE)=' /opt/homestead/secrets/runtime.env | sed 's/=.*/=<set>/'
```

Optional Langfuse tracing for `/model/route` is disabled by default. When enabled, it must not change model behavior and must fail open if Langfuse is unavailable.

```bash
LANGFUSE_ENABLED=false
LANGFUSE_HOST=http://100.112.20.36:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_ENVIRONMENT=homestead-private-os
LANGFUSE_RELEASE=v0-openrouter-route
```

Real Langfuse keys belong only in `/opt/homestead/secrets/runtime.env`.

Verify Langfuse variable names without printing secret values:

```bash
grep -E '^(LANGFUSE_ENABLED|LANGFUSE_HOST|LANGFUSE_PUBLIC_KEY|LANGFUSE_SECRET_KEY|LANGFUSE_ENVIRONMENT|LANGFUSE_RELEASE)=' /opt/homestead/secrets/runtime.env | sed 's/=.*/=<set>/'
```

Optional model-route receipts write append-only metadata for `/model/route` calls. They are disabled by default and must fail open if the receipt path is unavailable.

```bash
MODEL_ROUTE_RECEIPTS_ENABLED=false
MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT=false
```

Keep content capture disabled unless Adam explicitly chooses it. Default receipts record route, requested/model used, latency, ok/error, token usage, and Langfuse trace id when available, without storing full prompt or assistant content.

Verify receipt variable names without printing values:

```bash
grep -E '^(MODEL_ROUTE_RECEIPTS_ENABLED|MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT)=' /opt/homestead/secrets/runtime.env | sed 's/=.*/=<set>/'
```

Cloud OS status and Keep health summaries:

```bash
KEEP_HEALTH_DIR=System Receipts/Homestead Health
```

`KEEP_HEALTH_DIR` is repo-relative under `/workspace/keep`. Health sync is explicit only; no background writer is added.

Verify without printing unrelated env:

```bash
grep -E '^(KEEP_HEALTH_DIR)=' /opt/homestead/secrets/runtime.env | sed 's/=.*/=<set>/'
```

## Preflight

```bash
cd /opt/homestead/runtime
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/preflight.sh
```

Expected:

```text
preflight ok
```

Preflight checks:
- Docker exists
- Docker Compose plugin exists
- runtime env file exists
- expected folders exist
- `/opt/homestead/the-keep` exists
- `/opt/homestead/the-keep` is a git work tree
- `/opt/homestead/data` is writable
- Docker Compose config resolves

## Deploy

```bash
cd /opt/homestead/runtime
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Check services:

```bash
HOMESTEAD_ENV_FILE=/opt/homestead/secrets/runtime.env \
docker compose --env-file /opt/homestead/secrets/runtime.env -f infra/docker-compose.yml ps
```

Expected services:
- `homestead-api`
- `homestead-mcp`
- `repo-sync`
- `receipt-worker`
- `caddy`

## Server-Local Smoke Tests

```bash
curl http://localhost/health
curl http://localhost/api/repo/status
curl http://localhost/mcp/tools
```

If using alternate loopback ports:

```bash
curl http://localhost:8088/health
curl http://localhost:8088/api/repo/status
curl http://localhost:8088/mcp/tools
```

If `CADDY_HTTP_BIND` is set to a Tailscale IP and `CADDY_HTTP_PORT=8088`, use the private Tailscale URL from Adam's laptop while it is signed into the same tailnet:

```powershell
curl http://<tailscale-ip>:8088/health
curl http://<tailscale-ip>:8088/api/repo/status
curl http://<tailscale-ip>:8088/mcp/tools
```

If the laptop is not signed into Tailscale, these requests should time out. That is expected and is better than accidentally exposing the private OS spine.

## Receipt Read Surface

Receipts are stored under:

```text
/opt/homestead/data/receipts/YYYY-MM-DD/
```

Read-only receipt index endpoints are available through the private API path:

```powershell
curl http://<tailscale-ip>:8088/api/receipts/recent?limit=20
curl http://<tailscale-ip>:8088/api/receipts/by-date/<YYYY-MM-DD>
curl http://<tailscale-ip>:8088/api/receipts/<YYYY-MM-DD>/<receipt-id>
curl http://<tailscale-ip>:8088/api/receipts/stats
```

List endpoints return metadata summaries only. Exact receipt reads return the parsed JSON and Markdown for the explicitly requested receipt.

MCP tools:

```text
homestead.list_recent_receipts
homestead.read_receipt
homestead.receipt_stats
```

## Cloud OS Status And Keep Health

Private status endpoints:

```powershell
curl http://<tailscale-ip>:8088/api/node/status
curl http://<tailscale-ip>:8088/api/os/status
curl http://<tailscale-ip>:8088/api/os/context
curl http://<tailscale-ip>:8088/api/os/capabilities
```

MCP tools:

```text
homestead.node_status
homestead.os_status
homestead.os_context
homestead.os_capabilities
homestead.sync_keep_health
```

Write a metadata-only health summary into The Keep:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"requesting_agent":"runbook-health-sync","note":"manual health sync"}'
curl.exe --max-time 10 -X POST http://<tailscale-ip>:8088/api/keep/health/sync -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected Keep files under `KEEP_HEALTH_DIR`:

```text
index.md
homestead-latest.md
homestead-health-log.md
daily/YYYY-MM-DD.md
gateway/gateway-health.md
snapshots/<timestamp>.md
```

These summaries omit prompt/content and secret values. Local mode should remain visible but disabled.

## Review Queue And Capability Registry

The receipt review queue is read-only and metadata-only. It is the operator attention surface for receipts that need Adam's review because they are explicitly marked for review, failed, or include safe error metadata.

```powershell
curl http://<tailscale-ip>:8088/api/receipts/review?limit=20
```

Expected fields:

```text
generated_at
queue_empty
total_attention_items
receipts[].receipt_id
receipts[].timestamp
receipts[].task
receipts[].requesting_agent
receipts[].verdict
receipts[].review_required
receipts[].review_reasons
receipts[].route
receipts[].gateway
receipts[].requested_model
receipts[].model_used
receipts[].latency_ms
receipts[].error_summary
receipts[].langfuse_trace_id
```

The list surface must not return receipt Markdown bodies, full prompt/content, headers, API keys, raw env values, or stack traces. Exact receipt reads remain available only through `/api/receipts/<YYYY-MM-DD>/<receipt-id>`.

The capability registry is the canonical agent-readable map of what Homestead can safely use now:

```powershell
curl http://<tailscale-ip>:8088/api/os/capabilities
```

Expected status:

```text
cloud_node_status: active
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

MCP calls:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"tool":"homestead.receipts_review","arguments":{"limit":10}}'
curl.exe --max-time 10 -X POST http://<tailscale-ip>:8088/mcp/call -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp

$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"tool":"homestead.os_capabilities","arguments":{}}'
curl.exe --max-time 10 -X POST http://<tailscale-ip>:8088/mcp/call -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Keep health folder policy:

```text
/System Receipts/Homestead Health is agent-readable operational memory.
It may remain dirty/untracked until a separate Keep sync policy exists.
Do not auto-commit it.
Do not treat it as infra source.
Do not write prompt/content/secrets/raw env into it.
```

## Always-On Runtime Check

The stack should not depend on Adam's laptop. Docker services use `restart: unless-stopped`, and Docker itself is enabled through systemd.

Use this after deployment changes:

```bash
docker ps
cd /opt/homestead/runtime
HOMESTEAD_ENV_FILE=/opt/homestead/secrets/runtime.env \
docker compose --env-file /opt/homestead/secrets/runtime.env -f infra/docker-compose.yml ps
curl http://<tailscale-ip>:8088/health
```

Full reboot proof, when Adam is ready for the brief downtime:

```bash
reboot
```

After the server returns:

```bash
ssh root@5.78.206.130
docker ps
curl http://100.112.20.36:8088/health
```

## Deploy Updates

```bash
ssh root@<server-ip>
cd /opt/homestead/runtime
git fetch origin
git checkout main
git pull --ff-only
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

For a pre-merge deployment branch:

```bash
ssh root@<server-ip>
cd /opt/homestead/runtime
git fetch origin codex/hetzner-v0-deploy
git checkout codex/hetzner-v0-deploy
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

## Backups

```bash
DATA_ROOT=/opt/homestead/data BACKUP_ROOT=/opt/homestead/backups bash /opt/homestead/runtime/infra/scripts/backup.sh
```

Default output:

```text
/opt/homestead/backups/homestead-data-<timestamp>.tgz
```

## Stop Stack

This stops containers but does not delete data:

```bash
cd /opt/homestead/runtime
HOMESTEAD_ENV_FILE=/opt/homestead/secrets/runtime.env \
docker compose --env-file /opt/homestead/secrets/runtime.env -f infra/docker-compose.yml stop
```
