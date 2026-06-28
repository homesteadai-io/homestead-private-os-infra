# DNS

v0 target domains:

| Host | Purpose | Points to |
|---|---|---|
| `status.homesteadai.io` | lightweight status checks | Hetzner CPX51 public IP or Tailscale-routed endpoint |
| `api.homesteadai.io` | Homestead API | Hetzner CPX51 public IP or Tailscale-routed endpoint |
| `mcp.homesteadai.io` | Homestead MCP facade | Hetzner CPX51 public IP or Tailscale-routed endpoint |
| `node.homesteadai.io` | path-routed node entrypoint | Hetzner CPX51 public IP or Tailscale-routed endpoint |

## Recommended v0 Records

If exposing through normal public DNS:

```text
A  status.homesteadai.io  <hetzner-ip>
A  api.homesteadai.io     <hetzner-ip>
A  mcp.homesteadai.io     <hetzner-ip>
A  node.homesteadai.io    <hetzner-ip>
```

If using IPv6:

```text
AAAA  status.homesteadai.io  <hetzner-ipv6>
AAAA  api.homesteadai.io     <hetzner-ipv6>
AAAA  mcp.homesteadai.io     <hetzner-ipv6>
AAAA  node.homesteadai.io    <hetzner-ipv6>
```

## Caddy Routing

`infra/caddy/Caddyfile` routes:

| Request | Upstream |
|---|---|
| `https://status.homesteadai.io/` | static OK text |
| `https://status.homesteadai.io/health` | `homestead-api:8000/health` |
| `https://api.homesteadai.io/*` | `homestead-api:8000` |
| `https://mcp.homesteadai.io/*` | `homestead-mcp:8010` |
| `https://node.homesteadai.io/health` | `homestead-api:8000/health` |
| `https://node.homesteadai.io/api/*` | `homestead-api:8000/*` |
| `https://node.homesteadai.io/mcp/*` | `homestead-mcp:8010/*` |

## Public Exposure Warning

v0 assumes private access through Tailscale. If these records point at the public Hetzner IP, the API and MCP facade are reachable from the public internet unless the firewall, Tailscale, or another access layer blocks them.

The Docker Compose default binds Caddy to `127.0.0.1` only:

```bash
CADDY_HTTP_BIND=127.0.0.1
CADDY_HTTPS_BIND=127.0.0.1
```

For direct Tailscale access, bind Caddy to the server's Tailscale IP:

```bash
CADDY_HTTP_BIND=<tailscale-ip>
CADDY_HTTPS_BIND=<tailscale-ip>
```

For public DNS, bind Caddy publicly only after accepting unauthenticated v0 exposure:

```bash
CADDY_HTTP_BIND=0.0.0.0
CADDY_HTTPS_BIND=0.0.0.0
```

For v0, the safer default is:
- test first with Tailscale IP or SSH tunnel
- add DNS only when Adam is ready to expose the node name
- keep ports 80/443 reachable only as intentionally needed for Caddy/TLS

## DNS Propagation Checks

From Adam's laptop:

```bash
nslookup status.homesteadai.io
nslookup api.homesteadai.io
nslookup mcp.homesteadai.io
nslookup node.homesteadai.io
```

Expected: each name resolves to the intended Hetzner or private endpoint.
