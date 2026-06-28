# Output Capsule Write Policy

## Approved Lane

`/System Outputs` is the approved top-level Keep write lane for durable Homestead
output capsule bundles.

Approved bundle path shape:

```text
/System Outputs/{project_id}/{YYYY-MM-DD}-{slug}/
```

Example:

```text
/System Outputs/homestead-private-os/2026-06-28-agent-boot-projects/
```

## Purpose

Output capsules preserve useful work and continuation context for future agents.

Receipts remain separate. `/System Receipts` proves system behavior. `/System
Outputs` preserves reusable work products and handoff bundles.

## Required Bundle Contents

Each output capsule bundle must include:

```text
index.md
HANDOFF.md
handoff.json
CAPSULE.md
capsule.json
next-ai-prompt.md
okf/
pam/
```

`index.md` is the Keep collection entrypoint for the bundle. It links to the
handoff, capsule, next-agent prompt, JSON metadata, OKF folder, and PAM folder.

## Allowed Links

Output capsules may link to:

- `project_id`
- `command_id`
- `session_id`

Links are metadata only. They do not grant autonomous authority.

## Forbidden Writes

Do not write output capsules into:

- `/System Receipts`
- `/System Receipts/Homestead Health`
- any other new top-level Keep folder

Do not create any top-level Keep folder besides the approved `/System Outputs`
lane.

## Content Policy

Output capsules must not store by default:

- secrets
- token values
- raw environment values
- raw prompt captures
- raw completion captures
- private model transcript content

If future work needs richer content capture, it requires an explicit Adam
decision and a separate policy update.

## Non-Goals

This policy does not approve:

- Lyhna work
- witness fields
- runner
- scheduler
- dashboard
- local mode
- local model routing
- alerts
- workflow engine
- autonomous command claiming

Adam remains the authority. Agents and Codex are operators.
