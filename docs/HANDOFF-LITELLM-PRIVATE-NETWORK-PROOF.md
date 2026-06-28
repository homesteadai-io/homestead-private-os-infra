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

## Recommendation

If acceptance passes, PR #9 can be merged and tagged:

```text
v0-optional-litellm-gateway
```

Keep the live default direct. LiteLLM should remain optional until Adam explicitly chooses it as the serving path.
