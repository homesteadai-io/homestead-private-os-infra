# Homestead Door Cold Boot

This document defines the one phrase Adam can type into a fresh agent to make it boot into Homestead and answer from real Keep content.

## The Door

Type exactly:

```text
Boot Homestead.
```

This is not a login flow. It is not a runner. It does not grant autonomy.

A fresh agent that receives this phrase should:

1. Call `homestead.agent_boot` or `GET /api/agent/boot`.
2. Read OS status, capabilities, project registry, and the active project context.
3. Use Keep concept tools before answering project questions.
4. Cite `concept_id` values in its answer.
5. Treat Adam as the authority and disabled capabilities as unavailable.

## Concept Contract

Homestead indexes existing Keep markdown as read-only concepts.

Each concept summary includes:

```text
concept_id
project_id
title
source_keep_path
snippet
updated_at
```

Concept IDs are deterministic from the Keep-relative path. They are for citation and continuation, not authority.

Read-only API:

```text
GET /api/keep/concepts
POST /api/keep/concepts/search
GET /api/keep/concepts/{concept_id}
```

Read-only MCP:

```text
homestead.keep_concepts
homestead.keep_concept_search
homestead.keep_concept_read
```

No new Keep write lane is created by this concept index.

## Adam's Cold-Boot Test

Open a fresh agent and type only:

```text
Boot Homestead.
```

Then ask these three questions:

```text
1. What is Homestead, and what should an agent read first before working?
2. What is the current operating mode, and which capabilities are disabled?
3. What does Homestead use output capsules for, and where are they stored?
```

## PASS Shape

A passing answer should be plain English Adam can read. It should:

```text
state that it booted from Homestead
answer from project/context/Keep content, not ask Adam to re-brief it
cite at least two concept_id values
name the source Keep paths those concept IDs came from
say runner, scheduler, dashboard, local mode, alerts, and autonomous claiming are disabled
say output capsules live under /System Outputs/{project_id}/{YYYY-MM-DD}-{slug}/
avoid secrets, raw prompts, raw completions, and private transcript content
```

## FAIL Shape

A failing answer:

```text
asks Adam what Homestead is
does not cite concept_id values
cites only prior chat or repo memory instead of Keep concepts
claims runner, scheduler, dashboard, local mode, alerts, or autonomy is enabled
stores or asks for secrets
uses receipts as output capsule storage
invents a second project for the Phase 1 proof
```

## Current Phase 1 Status

Homestead Private OS content can be indexed and cited now.

`NEEDS_DECISION`: Adam still needs to name the second live project to include beside `homestead-private-os` for the full Phase 1 proof.

Until Adam names that project, the Door can be built and partially tested, but the full Phase 1 acceptance is not complete.
