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

## 11. Confirm No v0 Scope Creep

These should not exist yet:

```bash
curl -i https://api.homesteadai.io/model/route
```

Expected:

```text
404 Not Found
```

## 12. Private Exposure Check

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
```

If the Tailscale commands time out and `Test-NetConnection <tailscale-ip> -Port 8088` shows the Wi-Fi interface instead of a Tailscale interface, the laptop is not connected to the Tailnet yet. Fix the client before changing server exposure.

## 13. Reboot Survival

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
