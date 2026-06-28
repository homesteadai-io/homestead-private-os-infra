# Acceptance Tests

These tests prove v0 exists as deployed infrastructure, not just localhost code.

Replace:
- `<server-ip>` with the Hetzner server IP or Tailscale IP
- `<tailscale-ip>` with the node's Tailscale IP
- `<api-host>` with `api.homesteadai.io` when public DNS is intentionally enabled
- `<mcp-host>` with `mcp.homesteadai.io` when public DNS is intentionally enabled
- `<node-host>` with `node.homesteadai.io` when public DNS is intentionally enabled

Default v0 is private. The live Hetzner v0 shape keeps existing Nginx on public `80/443` and binds Homestead Caddy to the Tailscale IP on `8088/8443`.

Public DNS tests require `CADDY_HTTP_BIND=0.0.0.0` and `CADDY_HTTPS_BIND=0.0.0.0`, which exposes unauthenticated v0 surfaces. Do not use public DNS mode for the private OS spine without a separate access-control decision.

## 1. Local Unit Tests

Use Python 3.12 or 3.13 for local tests. Docker already uses Python 3.12. Python 3.14 may fail to build pinned native dependencies.

PowerShell:

```powershell
cd C:\Users\Adam\OneDrive\Desktop\homestead-private-os-infra
.\.venv\Scripts\python.exe -m pip install -r .\services\homestead-api\requirements.txt -r .\services\homestead-mcp\requirements.txt
$env:PYTHONPATH = "services/homestead-api"
.\.venv\Scripts\python.exe -m pytest .\services\homestead-api\tests
$env:PYTHONPATH = "services/homestead-mcp"
.\.venv\Scripts\python.exe -m pytest .\services\homestead-mcp\tests
```

Linux:

```bash
cd /opt/homestead/runtime
python3 -m venv .venv
. .venv/bin/activate
pip install -r services/homestead-api/requirements.txt -r services/homestead-mcp/requirements.txt
PYTHONPATH=services/homestead-api pytest services/homestead-api/tests
PYTHONPATH=services/homestead-mcp pytest services/homestead-mcp/tests
```

## 2. Server Preflight

Run on Hetzner:

```bash
cd /opt/homestead/runtime
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/preflight.sh
```

Expected:

```text
preflight ok
```

## 3. Compose Stack Is Running

Run on Hetzner:

```bash
cd /opt/homestead/runtime
HOMESTEAD_ENV_FILE=/opt/homestead/secrets/runtime.env \
docker compose --env-file /opt/homestead/secrets/runtime.env -f infra/docker-compose.yml ps
```

Expected services are running:

```text
caddy
homestead-api
homestead-mcp
receipt-worker
repo-sync
```

All Compose services should use:

```yaml
restart: unless-stopped
```

This keeps the runtime on Hetzner. Adam's laptop is only a client; the SSH tunnel is a temporary fallback, not a runtime dependency.

## 4. Health Through Caddy

From the Hetzner server:

```bash
curl http://localhost/health
```

From Adam's laptop after DNS/Tailscale is ready:

```bash
curl http://<tailscale-ip>:8088/health
```

Public DNS mode:

```bash
curl https://<node-host>/health
curl https://status.homesteadai.io/health
```

Expected:

```json
{"ok":true}
```

## 5. Repo Status Against The Keep

From the Hetzner server:

```bash
curl http://localhost/api/repo/status
```

From Adam's laptop:

```bash
curl http://<tailscale-ip>:8088/api/repo/status
```

Public DNS mode:

```bash
curl https://<api-host>/repo/status
```

Expected keys:

```text
branch
latest_commit
dirty
dirty_files
```

## 6. Markdown Search Works

From the Hetzner server:

```bash
curl -X POST http://localhost/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Homestead","max_results":5}'
```

From Adam's laptop:

```bash
curl -X POST http://<tailscale-ip>:8088/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Homestead","max_results":5}'
```

Public DNS mode:

```bash
curl -X POST https://<api-host>/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Homestead","max_results":5}'
```

Expected:

```text
count >= 1
results[0].path
results[0].snippet
```

## 7. Context Pack Works

From the Hetzner server:

```bash
curl -X POST http://localhost/api/context-pack \
  -H "Content-Type: application/json" \
  -d '{"task":"Homestead second-brain OKF library","max_files":5}'
```

From Adam's laptop:

```bash
curl -X POST http://<tailscale-ip>:8088/api/context-pack \
  -H "Content-Type: application/json" \
  -d '{"task":"Homestead second-brain OKF library","max_files":5}'
```

Public DNS mode:

```bash
curl -X POST https://<api-host>/context-pack \
  -H "Content-Type: application/json" \
  -d '{"task":"Homestead second-brain OKF library","max_files":5}'
```

Expected:

```text
generated_at
files
files[0].path
files[0].snippet
```

## 8. Receipt Writes Markdown and JSON

From the Hetzner server:

```bash
RUN_ID="hetzner-acceptance-$(date -u +%Y%m%dT%H%M%SZ)"
curl -X POST http://localhost/api/receipt/create \
  -H "Content-Type: application/json" \
  -d "{
    \"run_id\":\"$RUN_ID\",
    \"requesting_agent\":\"hetzner-acceptance\",
    \"task\":\"verify v0 receipt creation on Hetzner\",
    \"files_read\":[\"/README.md\"],
    \"model_used\":\"not_applicable_v0\",
    \"actions_taken\":[\"called deployed receipt endpoint\"],
    \"files_changed\":[],
    \"review_required\":false,
    \"verdict\":\"ok\"
  }"
find /opt/homestead/data/receipts -name "$RUN_ID.md" -o -name "$RUN_ID.json"
```

Expected:

```text
/opt/homestead/data/receipts/YYYY-MM-DD/<run-id>.md
/opt/homestead/data/receipts/YYYY-MM-DD/<run-id>.json
```

## 9. MCP Tool Surface Exists

From the Hetzner server:

```bash
curl http://localhost/mcp/tools
```

From Adam's laptop:

```bash
curl http://<tailscale-ip>:8088/mcp/tools
```

Public DNS mode:

```bash
curl https://<mcp-host>/tools
```

Expected tools:

```text
homestead.search_keep
homestead.read_concept
homestead.build_context_pack
homestead.repo_status
homestead.create_receipt
```

## 10. MCP Tool Call Works

From the Hetzner server:

```bash
curl -X POST http://localhost/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"homestead.repo_status","arguments":{}}'
```

From Adam's laptop:

```bash
curl -X POST http://<tailscale-ip>:8088/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"homestead.repo_status","arguments":{}}'
```

Public DNS mode:

```bash
curl -X POST https://<mcp-host>/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"homestead.repo_status","arguments":{}}'
```

Expected:

```text
result.branch
result.latest_commit
result.dirty
```

## 11. OpenRouter Model Route Works

Run on Hetzner without printing secret values:

```bash
grep -E '^(OPENROUTER_API_KEY|OPENROUTER_BASE_URL|OPENROUTER_DEFAULT_MODEL|OPENROUTER_HTTP_REFERER|OPENROUTER_APP_TITLE)=' /opt/homestead/secrets/runtime.env | sed 's/=.*/=<set>/'
```

Expected:

```text
OPENROUTER_API_KEY=<set>
OPENROUTER_BASE_URL=<set>
OPENROUTER_DEFAULT_MODEL=<set>
OPENROUTER_HTTP_REFERER=<set>
OPENROUTER_APP_TITLE=<set>
```

From Adam's laptop while signed into the same tailnet:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"prompt":"Say hello from Homestead in one sentence.","max_tokens":80}'
curl.exe --max-time 60 -X POST http://<tailscale-ip>:8088/model/route -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected:

```text
content
model
finish_reason
```

## 12. Optional Langfuse Tracing

Tracing is optional and must not change `/model/route` behavior. Keep `/model/route` direct to OpenRouter and do not route through LiteLLM.

Verify variable names without printing secret values:

```bash
grep -E '^(LANGFUSE_ENABLED|LANGFUSE_HOST|LANGFUSE_PUBLIC_KEY|LANGFUSE_SECRET_KEY|LANGFUSE_ENVIRONMENT|LANGFUSE_RELEASE)=' /opt/homestead/secrets/runtime.env | sed 's/=.*/=<set>/'
```

With tracing disabled:

```bash
LANGFUSE_ENABLED=false ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Then from Adam's laptop:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"prompt":"Say hello from Homestead with tracing disabled.","max_tokens":80}'
curl.exe --max-time 60 -X POST http://<tailscale-ip>:8088/model/route -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected:

```text
200 response
model/content/finish_reason present
```

With tracing enabled and real Langfuse keys present only in `/opt/homestead/secrets/runtime.env`:

```bash
cd /opt/homestead/runtime
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Then from Adam's laptop:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"prompt":"Say hello from Homestead with Langfuse tracing enabled.","max_tokens":80}'
curl.exe --max-time 60 -X POST http://<tailscale-ip>:8088/model/route -H "Content-Type: application/json" -H "x-homestead-surface: laptop-acceptance" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected:

```text
200 response
Langfuse trace appears in the private UI at http://<tailscale-ip>:3000
trace metadata includes route=/model/route, requested_model, model_used, latency_ms, ok=true, token usage when returned
prompt/content are not captured by default
```

Fail-open check:

```bash
cd /opt/homestead/runtime
LANGFUSE_HOST=http://127.0.0.1:1 ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Then call `/model/route` again. Expected:

```text
200 response from /model/route
no secret values in response body
```

Restore the real private Langfuse host afterward and redeploy if tracing should remain enabled.

## 13. Optional Model Route Receipts

Model route receipts are optional, append-only, metadata-only by default, and fail-open.

Verify variable names without printing values:

```bash
grep -E '^(MODEL_ROUTE_RECEIPTS_ENABLED|MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT)=' /opt/homestead/secrets/runtime.env | sed 's/=.*/=<set>/'
```

With receipts disabled:

```bash
cd /opt/homestead/runtime
MODEL_ROUTE_RECEIPTS_ENABLED=false ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Then from Adam's laptop:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"prompt":"Say hello from Homestead with model-route receipts disabled.","max_tokens":80}'
curl.exe --max-time 60 -X POST http://<tailscale-ip>:8088/model/route -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected:

```text
200 response
no receipt_id in response
```

With receipts enabled:

```bash
cd /opt/homestead/runtime
MODEL_ROUTE_RECEIPTS_ENABLED=true MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT=false ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Then from Adam's laptop:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"prompt":"Say hello from Homestead with model-route receipt metadata enabled.","max_tokens":80}'
curl.exe --max-time 60 -X POST http://<tailscale-ip>:8088/model/route -H "Content-Type: application/json" -H "x-homestead-surface: laptop-receipt-acceptance" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected:

```text
200 response
receipt_id and receipt_path present
receipt Markdown and JSON exist under /opt/homestead/data/receipts/YYYY-MM-DD/
receipt metadata includes route=/model/route, requested_model, model_used, latency_ms, ok=true, token usage when returned, and langfuse_trace_id when tracing succeeds
receipt does not include full prompt or assistant content by default
```

Fail-open check:

```bash
cd /opt/homestead/runtime
MODEL_ROUTE_RECEIPTS_ENABLED=true RECEIPTS_DIR=/not/a/writable/path ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Then call `/model/route` again. Expected:

```text
200 response from /model/route
safe receipt_error may be present
no secret values or stack traces in response body
```

Restore the real `RECEIPTS_DIR` and desired receipt setting afterward, then redeploy.

## 14. Private Exposure Check

From Adam's laptop, public `:8088` should fail:

```powershell
curl.exe --max-time 10 http://<server-ip>:8088/health
```

Expected:

```text
connection timed out or failed
```

From Adam's laptop while signed into the same tailnet, Tailscale `:8088` should succeed:

```powershell
curl.exe --max-time 10 http://<tailscale-ip>:8088/health
curl.exe --max-time 10 http://<tailscale-ip>:8088/api/repo/status
curl.exe --max-time 10 http://<tailscale-ip>:8088/mcp/tools
```

For POST requests from Windows PowerShell, prefer a temp JSON file so native argument parsing cannot strip quotes:

```powershell
$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"query":"Homestead","max_results":5}'
curl.exe --max-time 10 -X POST http://<tailscale-ip>:8088/api/search -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp

$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"task":"Homestead second-brain OKF library","max_files":5}'
curl.exe --max-time 10 -X POST http://<tailscale-ip>:8088/api/context-pack -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp

$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"tool":"homestead.repo_status","arguments":{}}'
curl.exe --max-time 10 -X POST http://<tailscale-ip>:8088/mcp/call -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp

$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"prompt":"Say hello from Homestead in one sentence.","max_tokens":80}'
curl.exe --max-time 60 -X POST http://<tailscale-ip>:8088/model/route -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

If the Tailscale commands time out and `Test-NetConnection <tailscale-ip> -Port 8088` shows the Wi-Fi interface instead of a Tailscale interface, the laptop is not connected to the Tailnet yet. Fix the client before changing server exposure.

Langfuse and MinIO public hardening should remain intact:

```powershell
curl.exe --max-time 10 http://<server-ip>:3000/
curl.exe --max-time 10 http://<server-ip>:9090/minio/health/live
curl.exe --max-time 10 http://<tailscale-ip>:3000/api/public/health
curl.exe --max-time 10 http://<tailscale-ip>:4000/health
```

Expected:

```text
public :3000 fails
public :9090 fails
private Langfuse health succeeds
LiteLLM over Tailscale fails
```

## 15. Receipt Read/Index Surface

The receipt index is read-only. It should return metadata summaries for list endpoints and full receipt files only when a specific receipt is requested by date and id.

From Adam's laptop:

```powershell
curl.exe --max-time 10 http://<tailscale-ip>:8088/api/receipts/recent?limit=5
curl.exe --max-time 10 http://<tailscale-ip>:8088/api/receipts/stats
```

Expected recent receipt summary fields:

```text
receipt_id
timestamp
task
requesting_agent
verdict
review_required
route
requested_model
model_used
latency_ms
usage
langfuse_trace_id
markdown_path
json_path
```

Read a specific receipt from the recent list:

```powershell
curl.exe --max-time 10 http://<tailscale-ip>:8088/api/receipts/by-date/<YYYY-MM-DD>
curl.exe --max-time 10 http://<tailscale-ip>:8088/api/receipts/<YYYY-MM-DD>/<receipt-id>
```

Expected:

```text
by-date returns metadata summaries only
exact read returns summary, parsed JSON, and Markdown for that explicit receipt
missing receipt returns safe 404
malformed date returns safe 400
```

MCP receipt tools:

```powershell
curl.exe --max-time 10 http://<tailscale-ip>:8088/mcp/tools

$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"tool":"homestead.list_recent_receipts","arguments":{"limit":5}}'
curl.exe --max-time 10 -X POST http://<tailscale-ip>:8088/mcp/call -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp

$tmp = New-TemporaryFile
Set-Content -LiteralPath $tmp -NoNewline -Encoding utf8 -Value '{"tool":"homestead.receipt_stats","arguments":{}}'
curl.exe --max-time 10 -X POST http://<tailscale-ip>:8088/mcp/call -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item -LiteralPath $tmp
```

Expected MCP tools:

```text
homestead.list_recent_receipts
homestead.read_receipt
homestead.receipt_stats
```

## 16. Reboot Survival

Run only when brief server downtime is acceptable:

```bash
ssh root@<server-ip>
reboot
```

After the server returns:

```bash
ssh root@<server-ip>
docker ps
cd /opt/homestead/runtime
HOMESTEAD_ENV_FILE=/opt/homestead/secrets/runtime.env \
docker compose --env-file /opt/homestead/secrets/runtime.env -f infra/docker-compose.yml ps
curl http://<tailscale-ip>:8088/health
```

Expected:

```text
Docker is running
all five Homestead services are up
/health returns ok
```
