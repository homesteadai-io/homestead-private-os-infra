# LiteLLM Auth Proof Handoff

Updated: 2026-06-28

## Scope

Task 5A was a read/proof-only pass against the inherited LiteLLM stack.

No Homestead routing, environment behavior, public exposure, Langfuse hardening, receipt writing, or receipt index behavior was changed. Homestead `/model/route` still routes direct to OpenRouter.

## Active LiteLLM Stack

Compose owner:

```text
/opt/arlo-infra/docker-compose.yml
```

Active config path:

```text
/opt/arlo-infra/litellm_config.yaml
```

Container mount:

```text
/opt/arlo-infra/litellm_config.yaml:/app/config.yaml:rw
```

Container:

```text
name: litellm
image: ghcr.io/berriai/litellm:main-stable
command: --config /app/config.yaml --port 4000 --num_workers 2
status: Up
restart: unless-stopped
compose project: arlo-infra
compose service: litellm
```

Related containers:

```text
litellm-db      postgres:16-alpine  Up, healthy
litellm-redis   redis:7-alpine      Up, healthy
```

Related volumes:

```text
litellm_litellm_pgdata
litellm_redis_data
```

## Exposure Proof

LiteLLM remains loopback-only:

```text
127.0.0.1:4000 -> 4000/tcp
```

Server listener proof:

```text
127.0.0.1:4000 LISTEN docker-proxy
```

Public and Tailscale probes:

```text
http://5.78.206.130:4000/health      HTTP 000, timed out
http://100.112.20.36:4000/health     HTTP 000, connection refused
```

This means LiteLLM is reachable locally on the server, but not publicly and not over Tailscale.

## Auth Proof

Auth method:

```text
Authorization: Bearer <LITELLM_MASTER_KEY>
```

The key was read only inside the server proof script from the running container environment and was not printed.

Relevant env/config names confirmed with values redacted:

```text
LITELLM_MASTER_KEY=<set>
DATABASE_URL=<set>
OPENAI_API_KEY=<set>
OPENROUTER_API_KEY=<set>
ANTHROPIC_API_KEY=<set>
GEMINI_API_KEY=<set>
GOOGLE_API_KEY=<set>
LANGFUSE_HOST=<set>
LANGFUSE_PUBLIC_KEY=<set>
LANGFUSE_SECRET_KEY=<set>
POSTGRES_PASSWORD=<set>
```

Unauthenticated check:

```text
GET /v1/models without bearer auth -> 401
```

Authenticated checks:

```text
GET /health     -> 200
GET /v1/models  -> 200
```

## Model List Summary

`/v1/models` returned 8 configured aliases:

```text
haiku
haiku-fallback
elevated
elevated-fallback
critical
critical-fallback
aux
aux-fallback
```

Config alias map:

```text
haiku              -> anthropic/claude-haiku-4-5-20251001
haiku-fallback     -> openrouter/google/gemini-3.1-flash-lite
elevated           -> openai/gpt-5.4-2026-03-05
elevated-fallback  -> anthropic/claude-sonnet-4-6
critical           -> anthropic/claude-opus-4-8
critical-fallback  -> openai/gpt-5.5-2026-04-23
aux                -> openrouter/google/gemini-3.1-flash-lite
aux-fallback       -> openai/gpt-5.4-mini-2026-03-17
```

Alias quality:

| Alias | Proof Result | Assessment |
| --- | --- | --- |
| `haiku` | Chat completion succeeded | Usable now |
| `haiku-fallback` | Chat completion succeeded | Usable now |
| `elevated` | Chat completion succeeded | Usable now |
| `elevated-fallback` | Chat completion succeeded | Usable now |
| `critical` | Failed with `temperature: 0`; succeeded without `temperature` | Usable with parameter discipline |
| `critical-fallback` | Failed with `temperature: 0`; succeeded without `temperature` | Usable with parameter discipline |
| `aux` | Chat completion succeeded | Usable now |
| `aux-fallback` | Chat completion succeeded | Usable now |

The first proof request used `temperature: 0`. Two aliases rejected that parameter because their upstream model/provider requires the default temperature behavior. A no-temperature retest succeeded for both. Treat LiteLLM gateway support as requiring model-aware request shaping.

## Completion Proof

Authenticated low-token chat completions were run locally on the server through:

```text
POST http://127.0.0.1:4000/v1/chat/completions
```

Successful examples:

```text
haiku              -> 200, model=haiku
haiku-fallback     -> 200, model=haiku-fallback
aux                -> 200, model=aux
aux-fallback       -> 200, model=aux-fallback
elevated           -> 200, model=elevated
elevated-fallback  -> 200, model=elevated-fallback
critical           -> 200, model=critical, without temperature override
critical-fallback  -> 200, model=critical-fallback, without temperature override
```

Usage fields were returned on successful completions.

## Langfuse Callback Proof

LiteLLM config includes Langfuse callbacks:

```text
litellm_settings.success_callback
litellm_settings.failure_callback
```

Recent Langfuse traces were created from the LiteLLM proof calls:

```text
trace name: litellm-acompletion
observation type: GENERATION
models observed:
  - anthropic/claude-haiku-4-5-20251001
  - openrouter/google/gemini-3.1-flash-lite
  - openai/gpt-5.4-2026-03-05
  - anthropic/claude-sonnet-4-6
  - anthropic/claude-opus-4-8
  - openai/gpt-5.5-2026-04-23
  - openai/gpt-5.4-mini-2026-03-17
```

Conclusion: LiteLLM -> Langfuse callback is working.

## Homestead Acceptance During Proof

Homestead remained healthy and independent:

```text
GET /health              -> ok=true
POST /model/route        -> direct OpenRouter model=openai/gpt-4.1-mini-2025-04-14
receipt written          -> model-route receipt id returned
receipt index read       -> latest receipt readable
Langfuse trace resolved  -> homestead.model_route, route=/model/route, ok=True
```

Exposure remained hardened:

```text
public LiteLLM :4000    -> closed
public Langfuse :3000   -> closed
public MinIO :9090      -> closed
private Langfuse :3000  -> healthy
LiteLLM Tailscale :4000 -> closed
```

## Recommendation

1. Is LiteLLM healthy enough to use later?

Yes, as an optional gateway candidate. It is running, authenticated, loopback-only, backed by Postgres/Redis, returns `/health` and `/v1/models`, completes calls across all configured aliases with compatible parameters, and emits Langfuse traces.

2. Which aliases/models are valid?

All 8 configured aliases are usable based on this proof. `critical` and `critical-fallback` require request shaping that avoids unsupported temperature overrides.

3. Should Homestead keep direct OpenRouter for now?

Yes. Direct OpenRouter routing is already healthy, traced, receipt-backed, and simple. LiteLLM adds useful gateway capabilities, but also adds parameter compatibility, key management, and operational dependency surface. It should earn its way in as optional, not replace the stable path yet.

4. What would Task 5B need for optional LiteLLM gateway support?

Task 5B should add an env-gated optional gateway path, not a default migration:

```text
MODEL_GATEWAY=direct|litellm
LITELLM_BASE_URL=http://127.0.0.1:4000
LITELLM_API_KEY=<server secret only>
LITELLM_DEFAULT_MODEL=haiku
```

Implementation requirements:

- keep `direct` as the default,
- do not expose LiteLLM beyond loopback,
- add model-aware request shaping, especially around `temperature`,
- fail closed or fall back intentionally by config, not accidentally,
- preserve Homestead Langfuse tracing and receipt metadata,
- include tests for direct mode, LiteLLM success, LiteLLM auth failure, LiteLLM upstream failure, and no secret leakage.
