# Homestead Private OS Infra v0 Handoff

Updated: 2026-06-27

## Current Decision

Homestead Private OS Infra v0 is deployed on the Hetzner node as a private, deployment-first spine.

The Keep remains Adam's second-brain OKF library/context graph. This runtime reads The Keep by configured path; it does not write concepts back into it.

## Repos

- Runtime repo: `https://github.com/homesteadai-io/homestead-private-os-infra.git`
- Keep repo: `https://github.com/homesteadai-io/The-Keep.git`
- Runtime branch deployed: `codex/hetzner-v0-deploy`
- Runtime commit deployed: `2150ec1`

## Server

- Hetzner IPv4: `5.78.206.130`
- SSH user: `root`
- Host observed over SSH: `keryke`
- Tailscale: installed and authenticated
- Tailscale hostname: `homestead-cpx51`
- Tailscale IPv4: `100.112.20.36`

## Server Layout

`/opt/homestead` is a symlink to the mounted Hetzner volume:

```text
/opt/homestead -> /mnt/HC_Volume_105361821/homestead
```

Required layout is present:

```text
/opt/homestead/
  runtime/    # homestead-private-os-infra checkout
  the-keep/   # The-Keep checkout
  data/       # receipts and runtime data
  backups/    # backup target
  secrets/    # local env files
```

Runtime env file:

```text
/opt/homestead/secrets/runtime.env
```

Do not commit or print this file. It currently uses placeholder model/email/tracing values.

## Running Services

Docker Compose project: `homestead-private-os`

Expected containers:

```text
caddy
homestead-api
homestead-mcp
receipt-worker
repo-sync
```

Current exposure:

```text
100.112.20.36:8088 -> caddy:80
100.112.20.36:8443 -> caddy:443
```

API and MCP are internal-only Docker ports. Public `5.78.206.130:8088` was verified closed.

Existing server Nginx already owns public `80/443`; do not overwrite it unless Adam explicitly chooses a public reverse-proxy migration.

## Disk Notes

Root disk was critical at 98%. It is now below the critical threshold after archiving a large OpenClaw promotion log and vacuuming systemd journals:

```text
/dev/sda1 38G, about 88% used
```

Mounted Hetzner volume has room:

```text
/mnt/HC_Volume_105361821 79G, about 40% used
```

Homestead was intentionally placed on the mounted volume via `/opt/homestead` symlink to avoid filling root.

Docker was already on the mounted volume:

```text
/var/lib/docker -> /mnt/HC_Volume_105361821/docker
DockerRootDir=/mnt/HC_Volume_105361821/docker
```

Docker log rotation is configured in `/etc/docker/daemon.json` with `max-size=10m` and `max-file=3`.

Archived root-pressure file:

```text
/mnt/HC_Volume_105361821/attic/root-disk-relief-20260627T231151Z/promotion-log.jsonl.gz
```

## Live Acceptance Proof

Private Tailscale-bound base URL:

```text
http://100.112.20.36:8088
```

Verified:

- `GET /health` returned OK
- `GET /api/repo/status` returned The Keep branch `main`, dirty `false`
- `POST /api/search` returned `count: 5`
- `POST /api/context-pack` returned `5` files
- `POST /api/receipt/create` wrote Markdown and JSON receipts
- `GET /mcp/tools` returned 5 tools
- `POST /mcp/call` with `homestead.repo_status` returned branch `main`
- Public `5.78.206.130:8088` remained closed

Not yet passed from Adam's laptop:

- Direct laptop curl to `http://100.112.20.36:8088/...`
- Local probe showed the Windows client was not on Tailscale/path; it attempted Wi-Fi source `10.0.0.184`

Receipt proof:

```text
/opt/homestead/data/receipts/2026-06-27/hetzner-live-20260627T224952Z.md
/opt/homestead/data/receipts/2026-06-27/hetzner-live-20260627T224952Z.json
/opt/homestead/data/receipts/2026-06-27/hetzner-tailscale-acceptance-20260627T232456Z.md
/opt/homestead/data/receipts/2026-06-27/hetzner-tailscale-acceptance-20260627T232456Z.json
```

Laptop SSH tunnel proof also passed:

```powershell
ssh -L 18088:127.0.0.1:8088 root@5.78.206.130 -N
```

Then from another terminal:

```powershell
curl http://127.0.0.1:18088/health
curl http://127.0.0.1:18088/mcp/tools
```

## Useful Commands

Check services:

```bash
ssh root@5.78.206.130
cd /opt/homestead/runtime
HOMESTEAD_ENV_FILE=/opt/homestead/secrets/runtime.env \
docker compose --env-file /opt/homestead/secrets/runtime.env -f infra/docker-compose.yml ps
```

Server-local tests:

```bash
BASE=http://100.112.20.36:8088
curl "$BASE/health"
curl "$BASE/api/repo/status"
curl "$BASE/mcp/tools"
```

Deploy current branch:

```bash
cd /opt/homestead/runtime
git fetch origin codex/hetzner-v0-deploy
git checkout codex/hetzner-v0-deploy
git pull --ff-only
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/preflight.sh
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Laptop tunnel:

```powershell
ssh -L 18088:127.0.0.1:8088 root@5.78.206.130 -N
```

Laptop tunnel checks:

```powershell
curl http://127.0.0.1:18088/health
curl http://127.0.0.1:18088/api/repo/status
curl http://127.0.0.1:18088/mcp/tools
```

## Next Best Move

Install or sign into Tailscale on Adam's laptop, then rerun the laptop acceptance checks without SSH tunnel:

```powershell
curl http://100.112.20.36:8088/health
curl http://100.112.20.36:8088/api/repo/status
curl http://100.112.20.36:8088/mcp/tools
```

Restart policy is now active on all five Compose services:

```text
homestead-api: unless-stopped
homestead-mcp: unless-stopped
repo-sync: unless-stopped
receipt-worker: unless-stopped
caddy: unless-stopped
```

Do not merge/tag until laptop Tailscale acceptance passes. Reboot survival proof is also recommended before tagging if Adam is ready for brief downtime.

## Not Yet Added

Do not assume these exist:

- OpenRouter `/model/route`
- LiteLLM
- GPU provider
- Langfuse tracing
- SMTP/email alerts
- vector search
- autonomous runner

Task 3 is OpenRouter routing after this deployment foundation.
