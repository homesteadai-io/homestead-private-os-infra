# Langfuse Model Route Tracing Handoff

Updated: 2026-06-28

## Scope

Task 4C adds optional Langfuse tracing around Homestead `/model/route`.

The serving path remains direct to OpenRouter. Homestead does not route through LiteLLM. No background workers, receipt automation, dashboards, or public Langfuse exposure are added.

## Runtime Contract

Tracing is controlled only by env vars:

```text
LANGFUSE_ENABLED=false
LANGFUSE_HOST=http://100.112.20.36:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_ENVIRONMENT=homestead-private-os
LANGFUSE_RELEASE=v0-openrouter-route
```

Real key values stay only in local/server env files, especially:

```text
/opt/homestead/secrets/runtime.env
```

## Behavior

When `LANGFUSE_ENABLED` is false or any required Langfuse value is missing, `/model/route` behaves exactly as the direct OpenRouter route.

When enabled, Homestead sends a minimal trace to Langfuse using the private `LANGFUSE_HOST` and the Langfuse ingestion endpoint.

Trace metadata includes:

- route: `/model/route`
- requested model
- model used
- latency in milliseconds
- ok/error
- token usage when OpenRouter returns it
- requesting surface when supplied through `x-homestead-surface` or `User-Agent`

Prompt and assistant content are not sent by default.

## Fail-Open Requirement

Langfuse errors must not break `/model/route`.

If Langfuse is down, unreachable, misconfigured, or rejects auth, Homestead should still return the OpenRouter response. Langfuse trace failures are swallowed and are not returned to the caller.

## Exposure Boundaries

Expected hardening from Task 4B remains:

```text
Langfuse web: 100.112.20.36:3000 only
MinIO API: 127.0.0.1:9090 only
LiteLLM: 127.0.0.1:4000 only
Homestead API: 100.112.20.36:8088 through Caddy
```

Public probes that should fail:

```text
http://5.78.206.130:3000
http://5.78.206.130:9090/minio/health/live
```

## Acceptance

Required checks:

- local API tests pass,
- `/health` passes on Homestead,
- `/model/route` passes with tracing disabled,
- `/model/route` passes with tracing enabled and a trace appears in private Langfuse,
- `/model/route` still passes when `LANGFUSE_HOST` is intentionally invalid,
- public Langfuse and public MinIO remain closed,
- LiteLLM remains untouched and loopback-only.

## Next Recommendation

Keep this as instrumentation only. Do not introduce LiteLLM as a gateway until it has its own authenticated provider proof, model map cleanup, and explicit ownership decision.
