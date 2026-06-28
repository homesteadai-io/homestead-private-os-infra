# LiteLLM Optional Gateway Handoff

Updated: 2026-06-28

## Scope

Task 5B adds env-gated LiteLLM gateway support to Homestead `/model/route`.

This does not make LiteLLM the production default. Homestead still defaults to direct OpenRouter routing:

```text
MODEL_GATEWAY=direct
```

No public exposure changes were made. No Langfuse hardening changes were made. No receipt write/index behavior was removed. LiteLLM remains an optional gateway candidate, not a required dependency.

## Runtime Behavior

`/model/route` now selects one gateway:

```text
MODEL_GATEWAY=direct   -> OpenRouter chat completions
MODEL_GATEWAY=litellm  -> LiteLLM OpenAI-compatible chat completions
```

Direct mode uses:

```text
OPENROUTER_API_KEY
OPENROUTER_BASE_URL
OPENROUTER_DEFAULT_MODEL
OPENROUTER_HTTP_REFERER
OPENROUTER_APP_TITLE
```

LiteLLM mode uses:

```text
LITELLM_BASE_URL
LITELLM_API_KEY
LITELLM_DEFAULT_MODEL
LITELLM_SEND_TEMPERATURE
```

If `MODEL_GATEWAY=litellm` and LiteLLM fails, Homestead does not silently fall back to OpenRouter. The route returns a safe upstream error so the operator knows the selected gateway path is broken.

## Temperature Shaping

Task 5A proved that some inherited LiteLLM aliases reject temperature overrides. LiteLLM mode therefore omits `temperature` by default.

To send a temperature override in LiteLLM mode, set:

```text
LITELLM_SEND_TEMPERATURE=true
```

Direct OpenRouter mode keeps the previous default temperature behavior: if the request omits `temperature`, Homestead sends `0.2`.

## Tracing And Receipts

Langfuse tracing remains fail-open.

Trace metadata now includes:

```text
gateway=direct|litellm
route=/model/route
requested_model
model_used
latency_ms
ok/error
```

Model-route receipt metadata also includes `gateway` for new receipts. Old receipts continue to read normally; the receipt index returns `gateway=null` when an older receipt lacks that field.

Prompt and response content are still omitted by default.

## Production Networking Note

The inherited LiteLLM service is currently host-loopback only:

```text
127.0.0.1:4000 -> 4000/tcp
```

That is good for exposure, but it means the live Homestead API container cannot assume `http://127.0.0.1:4000` reaches the host's LiteLLM process. Inside the API container, `127.0.0.1` is the API container itself.

Keep production on:

```text
MODEL_GATEWAY=direct
```

until a deliberate private server-side path is chosen.

Task 5C adds the repeatable private bridge as an optional Docker Compose overlay:

```text
infra/docker-compose.litellm.yml
```

The overlay attaches only `homestead-api` to the existing external `arlo-net` network. With that overlay, LiteLLM is reachable privately from the API container at:

```text
http://litellm:4000
```

With the same overlay, Homestead should use the internal Langfuse URL for tracing:

```text
LANGFUSE_HOST=http://langfuse-web:3000
```

Do not expose LiteLLM publicly or over Tailscale to solve this.

## Tests

Local API tests cover:

- direct mode remains default,
- direct mode keeps OpenRouter headers and temperature behavior,
- unknown gateway is rejected safely,
- LiteLLM mode uses bearer auth and `/v1/chat/completions`,
- LiteLLM mode omits temperature by default,
- LiteLLM mode can send temperature when explicitly enabled,
- LiteLLM failure does not fall back to OpenRouter,
- no prompt content or secret values leak in LiteLLM error responses.

## Recommendation

Keep Homestead live on direct OpenRouter for now.

The code now has the optional gateway hook and the private network overlay, but production should still be restored to `MODEL_GATEWAY=direct` after proof. Merge only after live acceptance proves:

- `MODEL_GATEWAY=direct` works after the overlay deploy,
- temporary `MODEL_GATEWAY=litellm` works through `http://litellm:4000`,
- Langfuse and receipts record `gateway=litellm`,
- public `:4000`, `:3000`, `:9090`, and `:8088` remain closed,
- LiteLLM remains closed over Tailscale,
- production is restored to `MODEL_GATEWAY=direct`.
