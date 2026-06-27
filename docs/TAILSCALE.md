# Tailscale

v0 assumes private access first. The Homestead node runs on Hetzner; Adam's laptop and phone are clients. SSH tunnels are temporary fallback access, not a runtime dependency.

## Private Access Assumption

The API and MCP facade are not hardened as public SaaS endpoints in v0. They should be treated as private node surfaces:

- `homestead-api` exposes repo status, markdown search, context packs, and receipt creation.
- `homestead-mcp` exposes the five Homestead tool names.
- Neither service has auth yet.

That is acceptable for a private node. It is not acceptable as a public API product.

## Install Tailscale On Hetzner

Run on the server:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --ssh --hostname homestead-cpx51
tailscale status
```

Record the server's Tailscale IP:

```bash
tailscale ip -4
```

## Test Through Tailscale IP

Set Caddy to bind to the server's Tailscale IP in `/opt/homestead/secrets/runtime.env`:

```bash
TAILSCALE_IP="$(tailscale ip -4)"
sed -i "s/^CADDY_HTTP_BIND=.*/CADDY_HTTP_BIND=$TAILSCALE_IP/" /opt/homestead/secrets/runtime.env
sed -i "s/^CADDY_HTTPS_BIND=.*/CADDY_HTTPS_BIND=$TAILSCALE_IP/" /opt/homestead/secrets/runtime.env
sed -i "s/^CADDY_HTTP_PORT=.*/CADDY_HTTP_PORT=8088/" /opt/homestead/secrets/runtime.env
sed -i "s/^CADDY_HTTPS_PORT=.*/CADDY_HTTPS_PORT=8443/" /opt/homestead/secrets/runtime.env
cd /opt/homestead/runtime
ENV_FILE=/opt/homestead/secrets/runtime.env bash infra/scripts/deploy.sh
```

From Adam's laptop while connected to the same tailnet:

```bash
curl http://<tailscale-ip>:8088/health
curl http://<tailscale-ip>:8088/api/repo/status
curl http://<tailscale-ip>:8088/mcp/tools
```

If these time out from the laptop, check the laptop Tailscale client first. Do not open public ports to compensate for a missing Tailnet client.

## Optional SSH Tunnel

If DNS is not ready and direct Tailscale HTTP is blocked:

```bash
ssh -L 8080:localhost:80 root@<server-ip>
```

Then from Adam's laptop:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/repo/status
curl http://localhost:8080/mcp/tools
```

If Homestead is bound to alternate loopback port `8088`, tunnel that port:

```bash
ssh -L 8088:localhost:8088 root@<server-ip>
curl http://localhost:8088/health
curl http://localhost:8088/api/repo/status
curl http://localhost:8088/mcp/tools
```

## Firewall Posture

For v0:
- keep SSH restricted to keys
- use Tailscale SSH if practical
- expose 80/443 publicly only if Adam intentionally wants public DNS tests
- do not expose Docker daemon ports

Tailscale-only firewall example:

```bash
ufw allow OpenSSH
ufw allow in on tailscale0 to any port 8088 proto tcp
ufw allow in on tailscale0 to any port 8443 proto tcp
ufw enable
ufw status
```

Public DNS firewall example, only after accepting unauthenticated v0 exposure:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

If the node is Tailscale-only and public Caddy is not needed yet, do not open 80/443 publicly.
