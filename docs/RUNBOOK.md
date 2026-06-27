# Runbook

This runbook deploys Homestead Private OS Infra v0 to the Hetzner CPX51 node.

v0 is deployment-only:
- no OpenRouter routing yet
- no LiteLLM
- no GPU provider
- no Langfuse
- no SMTP/email
- no autonomous runner

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
KEEP_REPO_HOST_PATH=/opt/homestead/the-keep
HOMESTEAD_DATA_PATH=/opt/homestead/data
HOMESTEAD_ENV_FILE=/opt/homestead/secrets/runtime.env
HOMESTEAD_API_URL=http://homestead-api:8000
HOMESTEAD_MCP_URL=http://homestead-mcp:8010
CADDY_HTTP_BIND=127.0.0.1
CADDY_HTTPS_BIND=127.0.0.1
```

For direct Tailscale access, replace both Caddy bind values with the server's Tailscale IP from `tailscale ip -4`.

For public DNS testing, use `0.0.0.0` only after accepting that v0 API/MCP surfaces are unauthenticated:

```bash
CADDY_HTTP_BIND=0.0.0.0
CADDY_HTTPS_BIND=0.0.0.0
```

Leave model, Langfuse, and SMTP values as placeholders in v0.

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

If `CADDY_HTTP_BIND` is set to a Tailscale IP, use that IP instead of `localhost` from Adam's laptop.

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
