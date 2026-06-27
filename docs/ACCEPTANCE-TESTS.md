# Acceptance Tests

Run from repo root unless noted.

## 1. Python API Tests

Use Python 3.12 or 3.13 for local tests. Docker already uses Python 3.12. Python 3.14 may fail to build pinned native dependencies.

```bash
cd homestead-private-os-infra
python -m venv .venv
. .venv/bin/activate
pip install -r services/homestead-api/requirements.txt
PYTHONPATH=services/homestead-api pytest services/homestead-api/tests
```

PowerShell:

```powershell
cd C:\Users\Adam\OneDrive\Desktop\homestead-private-os-infra
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\services\homestead-api\requirements.txt
$env:PYTHONPATH = "services/homestead-api"
pytest .\services\homestead-api\tests
```

## 2. Docker Compose Starts

```bash
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/docker-compose.yml up --build
```

With a real Keep/source checkout:

```bash
KEEP_REPO_HOST_PATH=/opt/homestead/the-keep
HOMESTEAD_DATA_HOST_PATH=/opt/homestead/data
docker compose --env-file infra/.env -f infra/docker-compose.yml up --build
```

## 3. Health Returns OK

```bash
curl http://localhost:8080/health
```

Expected:

```json
{"ok":true}
```

## 4. Repo Status Shows Branch, Commit, Dirty State

```bash
curl http://localhost:8080/repo/status
```

Expected keys:

```text
branch
latest_commit
dirty
dirty_files
```

## 5. Markdown Search Works

```bash
curl -X POST http://localhost:8080/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Homestead","max_results":5}'
```

Expected:

```text
count >= 1
results[0].path
results[0].snippet
```

## 6. Context Pack Works

```bash
curl -X POST http://localhost:8080/context-pack \
  -H "Content-Type: application/json" \
  -d '{"task":"Homestead Private OS","max_files":5}'
```

Expected:

```text
generated_at
files
```

## 7. Receipt Writes Markdown and JSON

```bash
curl -X POST http://localhost:8080/receipt/create \
  -H "Content-Type: application/json" \
  -d '{
    "requesting_agent":"acceptance-test",
    "task":"verify v0 receipt creation",
    "files_read":["/README.md"],
    "model_used":"not_applicable_v0",
    "actions_taken":["called receipt endpoint"],
    "files_changed":[],
    "review_required":false,
    "verdict":"ok"
  }'
```

Expected:

```text
markdown_path
json_path
```

Both files should exist under:

```text
<HOMESTEAD_DATA_HOST_PATH>/receipts/YYYY-MM-DD/
```

## 8. MCP Tool Surface Exists

```bash
curl http://localhost:8010/tools
```

Expected tools:

```text
homestead.search_keep
homestead.read_concept
homestead.build_context_pack
homestead.repo_status
homestead.create_receipt
```

## 9. MCP Tool Call Works

```bash
curl -X POST http://localhost:8010/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"homestead.repo_status","arguments":{}}'
```

Expected:

```text
result.branch
result.latest_commit
result.dirty
```
