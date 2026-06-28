# Receipt Index Surface Handoff

Updated: 2026-06-28

## Scope

Task 4E adds a narrow read-only API and MCP surface for existing Homestead receipts.

No receipt write format changes were required beyond reading the existing JSON/Markdown files. No dashboard, SMTP, alerting, public exposure, LiteLLM routing, or receipt mutation behavior was added.

## API Surface

Private API endpoints:

```text
GET /receipts/recent?limit=20
GET /receipts/by-date/{YYYY-MM-DD}
GET /receipts/{YYYY-MM-DD}/{receipt_id}
GET /receipts/stats
```

Through Caddy on the live node, use:

```text
http://100.112.20.36:8088/api/receipts/...
```

Recent and by-date responses return metadata summaries only:

- `receipt_id`
- `timestamp`
- `task`
- `requesting_agent`
- `verdict`
- `review_required`
- `route`
- `requested_model`
- `model_used`
- `latency_ms`
- `usage`
- `langfuse_trace_id`
- `markdown_path`
- `json_path`

Exact receipt reads return:

- summary
- parsed JSON
- Markdown content for the explicitly requested receipt
- Markdown/JSON paths

This means prompt/content is not included in list responses. Exact read can return whatever already exists in that specific receipt because the caller named the receipt.

## MCP Surface

Tools added:

```text
homestead.list_recent_receipts
homestead.read_receipt
homestead.receipt_stats
```

## Safety

The surface is read-only.

Date values must be `YYYY-MM-DD`. Receipt ids are restricted to the existing receipt id character set. Missing receipts return a safe 404. Malformed dates or ids return safe 400 responses.

## Live Acceptance

Required checks:

- `/health` passes,
- recent receipt list returns model-route receipt metadata,
- by-date list returns metadata summaries,
- exact receipt read works for the latest model-route receipt,
- MCP tools list and return receipt metadata,
- `/model/route` still works,
- Langfuse tracing still works,
- public Langfuse and public MinIO remain closed,
- LiteLLM remains loopback-only and untouched.

## Next Recommendation

Pause before building dashboards. This surface is enough for agents and operators to retrieve proof trails programmatically. If the next step is UI, keep it private and reader-first.
