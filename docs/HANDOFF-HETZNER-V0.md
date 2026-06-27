# Homestead Private OS Infra v0 Handoff

Updated: 2026-06-27

## Current Decision

Homestead Private OS Infra v0 is deployed on the Hetzner node as a private, deployment-first spine.

The Keep remains Adam's second-brain OKF library/context graph. This runtime reads The Keep by configured path; it does not write concepts back into it.

## Repos

- Runtime repo: `https://github.com/homesteadai-io/homestead-private-os-infra.git`
- Keep repo: `https://github.com/homesteadai-io/The-Keep.git`
- Runtime branch deployed: `codex/hetzner-v0-deploy`
- Runtime commit deployed: `4913e35`

## Server

- Hetzner IPv4: `5.78.206.130`
- SSH user: `root`
- Host observed over SSH: `Laptop`
- Tailscale: not installed as of this handoff

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
127.0.0.1:8088 -> caddy:80
127.0.0.1:8443 -> caddy:443
```

API and MCP are internal-only Docker ports. Public `5.78.206.130:8088` was verified closed from Adam's laptop.

Existing server Nginx already owns public `80/443`; do not overwrite it unless Adam explicitly chooses a public reverse-proxy migration.

## Disk Notes

Root disk is tight:

```text
/dev/sda1 38G, about 98% used
```

Mounted Hetzner volume has room:

```text
/mnt/HC_Volume_105361821 79G, about 40% used
```

Homestead was intentionally placed on the mounted volume via `/opt/homestead` symlink to avoid filling root.

## Live Acceptance Proof

Server-local base URL:

```text
http://127.0.0.1:8088
```

Verified:

- `GET /health` returned OK
- `GET /api/repo/status` returned The Keep branch `main`, dirty `false`
- `POST /api/search` returned `count: 3`
- `POST /api/context-pack` returned `3` files
- `POST /api/receipt/create` wrote Markdown and JSON receipts
- `GET /mcp/tools` returned 5 tools
- `POST /mcp/call` with `homestead.repo_status` returned branch `main`

Receipt proof:

```text
/opt/homestead/data/receipts/2026-06-27/hetzner-live-20260627T224952Z.md
/opt/homestead/data/receipts/2026-06-27/hetzner-live-20260627T224952Z.json
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
BASE=http://127.0.0.1:8088
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

Install/auth Tailscale and bind Homestead Caddy to the Tailscale IP.

Planned mode:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --ssh --hostname homestead-cpx51
TAILSCALE_IP="$(tailscale ip -4)"
sed -i "s/^CADDY_HTTP_BIND=.*/CADDY_HTTP_BIND=$TAILSCALE_IP/" /opt/homestead/secrets/runtime.env
sed -i "s/^CADDY_HTTPS_BIND=.*/CADDY_HTTPS_BIND=$TAILSCALE_IP/" /opt/homestead/secrets/runtime.env
sed -i "s/^CADDY_HTTP_PORT=.*/CADDY_HTTP_PORT=80/" /opt/homestead/secrets/runtime.env
sed -i "s/^CADDY_HTTPS_PORT=.*/CADDY_HTTPS_PORT=443/" /opt/homestead/secrets/runtime.env
cd /opt/homestead/runtime
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

Then Adam can use:

```text
http://<tailscale-ip>/health
http://<tailscale-ip>/api/repo/status
http://<tailscale-ip>/mcp/tools
```

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

