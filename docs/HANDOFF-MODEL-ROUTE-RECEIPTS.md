# Model Route Receipts Handoff

Updated: 2026-06-28

## Scope

Task 4D adds optional append-only receipt metadata for Homestead `/model/route` calls.

The serving path remains direct to OpenRouter. Langfuse tracing remains optional and fail-open. Homestead does not route through LiteLLM. No background workers, dashboard work, SMTP, public exposure changes, or prompt/content capture are added by default.

## Runtime Contract

Receipts are controlled by env vars:

```text
MODEL_ROUTE_RECEIPTS_ENABLED=false
MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT=false
```

Real live values belong only in:

```text
/opt/homestead/secrets/runtime.env
```

Placeholders live in:

```text
infra/.env.example
```

## Behavior

When `MODEL_ROUTE_RECEIPTS_ENABLED=false`, `/model/route` behaves as before and writes no model-route receipt.

When `MODEL_ROUTE_RECEIPTS_ENABLED=true`, each `/model/route` call attempts to write a receipt through the existing append-only receipt path:

```text
/opt/homestead/data/receipts/YYYY-MM-DD/
```

Successful receipt writes add these response fields:

```text
receipt_id
receipt_path
```

If receipt writing fails, `/model/route` still returns the model response and may include:

```text
receipt_error: receipt write failed
```

No stack traces, secret values, API keys, headers, raw env, or private context are returned.

## Receipt Metadata

Default receipt metadata includes:

- `run_id`
- `timestamp`
- `requesting_agent` from `x-homestead-surface` or `User-Agent` when available
- `task=model_route`
- `route=/model/route`
- requested model
- model used
- latency in milliseconds
- ok/error state
- safe error summary on failure
- token usage when returned
- Langfuse trace id when tracing succeeds
- `review_required`
- `verdict`

Defaults:

```text
files_read=[]
files_changed=[]
review_required=false on success
verdict=ok on success
verdict=error on failure
```

`actions_taken` summarizes the model route call without including prompt or assistant content.

## Content Boundary

Prompt and assistant content are not captured by default.

`MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT=true` is reserved for a later explicit content-capture decision. Keep it false unless Adam explicitly chooses otherwise.

## Acceptance

Required checks:

- local API tests pass,
- local MCP tests pass,
- `/health` passes on Homestead,
- `/model/route` passes with receipts disabled and returns no receipt id,
- `/model/route` passes with receipts enabled and writes Markdown plus JSON,
- receipt does not contain full prompt or assistant content by default,
- receipt write failure does not fail `/model/route`,
- OpenRouter failure can still write a safe failure receipt,
- Langfuse tracing still receives `homestead.model_route` metadata,
- public Langfuse and public MinIO remain closed,
- LiteLLM remains loopback-only and untouched.

## Next Recommendation

Pause before LiteLLM gateway work. If continuing the observability/proof spine, the next useful step is a careful review of receipt retention/search ergonomics, not provider routing complexity.
