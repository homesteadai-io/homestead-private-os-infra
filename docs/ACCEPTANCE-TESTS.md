# Acceptance Tests

These tests prove v0 exists as deployed infrastructure, not just localhost code.

Replace:
- `<server-ip>` with the Hetzner server IP or Tailscale IP
- `<tailscale-ip>` with the node's Tailscale IP
- `<api-host>` with `api.homesteadai.io` when public DNS is intentionally enabled
- `<mcp-host>` with `mcp.homesteadai.io` when public DNS is intentionally enabled
- `<node-host>` with `node.homesteadai.io` when public DNS is intentionally enabled

Default v0 is private. Public DNS tests require `CADDY_HTTP_BIND=0.0.0.0` and `CADDY_HTTPS_BIND=0.0.0.0`, which exposes unauthenticated v0 surfaces.

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

## 4. Health Through Caddy

From the Hetzner server:

```bash
curl http://localhost/health
```

From Adam's laptop after DNS/Tailscale is ready:

```bash
curl http://<tailscale-ip>/health
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
curl http://<tailscale-ip>/api/repo/status
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
curl -X POST http://<tailscale-ip>/api/search \
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
curl -X POST http://<tailscale-ip>/api/context-pack \
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
curl http://<tailscale-ip>/mcp/tools
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
curl -X POST http://<tailscale-ip>/mcp/call \
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
