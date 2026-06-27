# Environment

All runtime secrets and deployment-specific paths live in `infra/.env`.

Never commit `infra/.env`.

## Required v0 Variables

| Variable | Purpose |
|---|---|
| `HOMESTEAD_ENV` | environment label, usually `local` or `production` |
| `HOMESTEAD_REPO_PATH` | container path to the repo API inspects |
| `RECEIPTS_DIR` | container path where receipts are written |
| `KEEP_REPO_HOST_PATH` | host path mounted to `HOMESTEAD_REPO_PATH` |
| `HOMESTEAD_DATA_HOST_PATH` | host path mounted to `/data` |
| `HOMESTEAD_API_URL` | internal API URL used by MCP facade |

## OpenRouter Stub

These are placeholders in v0 and become active in Task 3:

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter key |
| `OPENROUTER_BASE_URL` | OpenRouter API base URL |
| `OPENROUTER_DEFAULT_MODEL` | default model route |

## Future Placeholders

Present for planning, not used by v0:

| Variable | Task |
|---|---|
| `LANGFUSE_PUBLIC_KEY` | Task 4 tracing |
| `LANGFUSE_SECRET_KEY` | Task 4 tracing |
| `LANGFUSE_HOST` | Task 4 tracing |
| `SMTP_HOST` | Task 5 email alerts |
| `SMTP_PORT` | Task 5 email alerts |
| `SMTP_USER` | Task 5 email alerts |
| `SMTP_PASSWORD` | Task 5 email alerts |
| `SMTP_FROM` | Task 5 email alerts |

