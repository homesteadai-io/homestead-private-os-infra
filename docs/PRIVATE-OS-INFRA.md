# Homestead Private OS Infra v0

## Decision

Build Homestead Private OS Infra as its own repo, separate from The Keep.

The Keep is Adam's second-brain OKF library and context graph. This repo runs private OS infrastructure. Receipts are the bridge between work and memory, not a hidden dependency.

## v0 Scope

Included:
- Docker Compose runtime
- Caddy reverse proxy
- FastAPI Homestead API
- thin MCP HTTP facade
- Git CLI repo status and safe fetch sync
- Markdown file search
- context pack builder
- Markdown and JSON receipts
- OpenRouter environment placeholders

Excluded:
- GPU provider support
- LiteLLM
- Langfuse tracing
- email alerts
- complex agent swarm
- vector search
- destructive repo writes

## Runtime Shape

```text
client / agent
  -> Caddy
    -> homestead-api
       -> configured git repo
       -> receipts directory
    -> homestead-mcp
       -> homestead-api
```

## Hetzner Layout

```text
/opt/homestead/
  runtime/    # this repo
  the-keep/   # Adam's second-brain OKF library/context graph
  data/       # receipts, logs, runtime state
  backups/    # tarball backups
  secrets/    # local-only env files
```

Runtime env lives at:

```text
/opt/homestead/secrets/runtime.env
```

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | service health |
| `GET` | `/repo/status` | branch, latest commit, dirty state |
| `POST` | `/repo/sync` | safe `git fetch --all --prune` |
| `POST` | `/search` | search markdown files |
| `POST` | `/context-pack` | relevant markdown paths and snippets |
| `POST` | `/read-concept` | read one markdown file for MCP |
| `POST` | `/receipt/create` | write Markdown and JSON receipts |

## MCP Tools

| Tool | Backing API |
|---|---|
| `homestead.search_keep` | `POST /search` |
| `homestead.read_concept` | `POST /read-concept` |
| `homestead.build_context_pack` | `POST /context-pack` |
| `homestead.repo_status` | `GET /repo/status` |
| `homestead.create_receipt` | `POST /receipt/create` |

## Receipt Contract

Receipts write to:

```text
receipts/YYYY-MM-DD/<run-id>.md
receipts/YYYY-MM-DD/<run-id>.json
```

Fields:
- `run_id`
- `timestamp`
- `requesting_agent`
- `task`
- `files_read`
- `model_used`
- `actions_taken`
- `files_changed`
- `review_required`
- `verdict`

Existing receipt IDs return `409 Conflict`; v0 does not overwrite receipts.

## Repo Boundary

`HOMESTEAD_REPO_PATH` points at whichever repo the node should inspect. On the Hetzner node this will usually be The Keep checkout: Adam's second-brain OKF library/context graph. This repo does not import The Keep as code and does not write concepts into it.

`/repo/sync` runs `git fetch --all --prune`. It updates Git remote metadata but does not merge, rebase, edit files, delete files, or commit.
