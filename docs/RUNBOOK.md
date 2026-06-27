# Runbook

## Local Run

```bash
cd homestead-private-os-infra
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/docker-compose.yml up --build
```

In `infra/.env`, set:

```bash
KEEP_REPO_HOST_PATH=/absolute/path/to/the/repo/to/search
HOMESTEAD_DATA_HOST_PATH=/absolute/path/to/local/data
```

For local Windows testing, Docker accepts paths like:

```bash
KEEP_REPO_HOST_PATH=C:/Users/Adam/OneDrive/Desktop/Homestead AI.io
HOMESTEAD_DATA_HOST_PATH=C:/Users/Adam/OneDrive/Desktop/homestead-private-os-infra/data
```

## Hetzner First Boot

SSH into the CPX51 node:

```bash
ssh root@<server-ip>
```

Install base dependencies:

```bash
curl -fsSL https://raw.githubusercontent.com/<your-org>/<this-repo>/main/infra/scripts/bootstrap-server.sh | bash
```

Or clone first and run locally:

```bash
git clone git@github.com:<your-org>/<this-repo>.git /opt/homestead/private-os-infra
cd /opt/homestead/private-os-infra
sudo bash infra/scripts/bootstrap-server.sh
```

Clone The Keep/source repo:

```bash
git clone git@github.com:<your-org>/<the-keep-repo>.git /opt/homestead/the-keep
```

Create env:

```bash
cd /opt/homestead/private-os-infra
cp infra/.env.example infra/.env
nano infra/.env
```

Use:

```bash
KEEP_REPO_HOST_PATH=/opt/homestead/the-keep
HOMESTEAD_DATA_HOST_PATH=/opt/homestead/data
HOMESTEAD_REPO_PATH=/workspace/keep
RECEIPTS_DIR=/data/receipts
```

Deploy:

```bash
bash infra/scripts/deploy.sh
```

## Tailscale / DNS v0

v0 assumes private access through Tailscale. Public exposure should stay minimal.

Recommended v0 DNS:
- `status.homesteadai.io` -> server public IP or Tailscale-accessible route
- `api.homesteadai.io` -> server public IP or Tailscale-accessible route
- `mcp.homesteadai.io` -> server public IP or Tailscale-accessible route

If these names are public DNS records, restrict access at the network layer before putting sensitive data behind them. Caddy is configured in `infra/caddy/Caddyfile`; hard auth/Tailscale ACLs are a follow-up if public exposure becomes real.

## Backups

Back up runtime data:

```bash
bash infra/scripts/backup.sh
```

Default output:

```text
/opt/homestead/backups/homestead-data-<timestamp>.tgz
```

## Deploy Update

```bash
ssh root@<server-ip>
cd /opt/homestead/private-os-infra
git pull --ff-only
bash infra/scripts/deploy.sh
```

