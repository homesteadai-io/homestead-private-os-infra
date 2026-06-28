# LiteLLM Private Network Proof Handoff

Updated: 2026-06-28

## Scope

Task 5C proves the private container path required before Homestead can safely use the optional LiteLLM gateway.

This task does not make LiteLLM the production default. It adds a repeatable private network overlay and requires production to be restored to:

```text
MODEL_GATEWAY=direct
```

## Private Bridge

LiteLLM already runs on the inherited Docker network:

```text
network: arlo-net
container alias: litellm
container port: 4000
host publish: 127.0.0.1:4000 only
```

Homestead's default compose network remains separate. The optional bridge is:

```text
infra/docker-compose.litellm.yml
```

It attaches `homestead-api` to both:

```text
homestead-private-os_default
arlo-net
```

That allows the API container to call:

```text
http://litellm:4000/v1/chat/completions
```

without publishing LiteLLM publicly or over Tailscale.

## Deployment Command

Use the overlay only when proving or intentionally enabling LiteLLM mode:

```bash
cd /opt/homestead/runtime
docker compose \
  --env-file /opt/homestead/secrets/runtime.env \
  -f infra/docker-compose.yml \
  -f infra/docker-compose.litellm.yml \
  up -d --build homestead-api homestead-mcp caddy
```

## Required Runtime Env

Real values stay only in `/opt/homestead/secrets/runtime.env`.

```text
MODEL_GATEWAY=direct
LITELLM_BASE_URL=http://litellm:4000
LITELLM_API_KEY=<set>
LITELLM_DEFAULT_MODEL=haiku
LITELLM_SEND_TEMPERATURE=false
LANGFUSE_HOST=http://langfuse-web:3000
```

For the temporary proof, switch only:

```text
MODEL_GATEWAY=litellm
```

Then restore:

```text
MODEL_GATEWAY=direct
```

## Acceptance

Prove all of the following:

- Homestead health passes.
- Direct mode `/model/route` returns `gateway=direct`.
- API container can reach `http://litellm:4000/health` over `arlo-net`.
- Temporary LiteLLM mode `/model/route` returns `gateway=litellm`.
- Langfuse receives a `homestead.model_route` trace with `gateway=litellm`.
- Model-route receipt metadata includes `gateway=litellm`.
- Receipt index can read the latest LiteLLM receipt.
- Production is restored to `MODEL_GATEWAY=direct`.
- Public `:8088`, `:3000`, `:9090`, and `:4000` remain closed.
- Tailscale `:4000` remains closed.

## Live Proof Result

Task 5C live proof passed on 2026-06-28.

Server checkout during proof:

```text
branch: codex/litellm-optional-gateway
head: 477a4b2
```

Private network proof:

```text
homestead-api networks: homestead-private-os_default, arlo-net
LiteLLM internal URL: http://litellm:4000
authenticated LiteLLM health from homestead-api container: 200
internal Langfuse health from homestead-api container: 200
```

Direct mode after overlay:

```text
/model/route gateway=direct
model=openai/gpt-4.1-mini-2025-04-14
receipt written
Langfuse trace id present
```

Temporary LiteLLM mode:

```text
/model/route gateway=litellm
model=haiku
receipt=model-route-5ec2bce8fed0
receipt metadata gateway=litellm
receipt index read succeeded
Langfuse trace=df59c50479784312822c42f35eeaa874
Langfuse metadata gateway=litellm, route=/model/route, ok=True
prompt/content omitted from receipt/index output by default
```

Production restored:

```text
MODEL_GATEWAY=direct
/model/route gateway=direct
latest direct receipt has Langfuse trace id
```

Exposure after proof:

```text
public :8088 -> closed
public :4000 -> closed
Tailscale :4000 -> closed
public :3000 -> closed
public :9090 -> closed
private :8088 -> healthy
```

## Recommendation

If acceptance passes, PR #9 can be merged and tagged:

```text
v0-optional-litellm-gateway
```

Keep the live default direct. LiteLLM should remain optional until Adam explicitly chooses it as the serving path.
