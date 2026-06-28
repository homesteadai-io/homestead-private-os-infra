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

Then ask these six questions:

```text
1. What is Homestead, and what should an agent read first before working?
2. What is the current operating mode, and which capabilities are disabled?
3. What does Homestead use output capsules for, and where are they stored?
4. What is the Creative Coatings powder scheduler, and what problem does it solve?
5. What is the difference between Core Dump Inbox and Schedule Intake Inbox?
6. Is Creative Coatings part of the Homestead runtime, or is it a separate project context?
```

## Question Checks

### 1. What is Homestead, and what should an agent read first before working?

PASS reply:

```text
Homestead is Adam's private operating spine / owned memory system. A fresh agent should boot from Homestead, read the Deed and active project context, then use Keep concepts before answering. It cites concept-deed-571b2b47 and/or concept-homestead-cdd07bcc.
```

FAIL reply:

```text
It asks Adam what Homestead is, treats Homestead as a public SaaS, or answers without a concept_id.
```

Expected concept IDs:

```text
concept-deed-571b2b47
concept-homestead-cdd07bcc
```

### 2. What is the current operating mode, and which capabilities are disabled?

PASS reply:

```text
Homestead is manual-only. Adam is the authority; agents are operators. Runner, scheduler, dashboard, alerts, local mode, and autonomous claiming are disabled. It cites a Homestead concept such as concept-deed-571b2b47 plus live status context such as concept-system-receipts-homestead-health-homestead-latest-7d8b5c17 when available.
```

FAIL reply:

```text
It claims Homestead can autonomously claim work, run a scheduler, expose a dashboard, or enable local mode.
```

Expected concept IDs:

```text
concept-deed-571b2b47
concept-system-receipts-homestead-health-homestead-latest-7d8b5c17
```

### 3. What does Homestead use output capsules for, and where are they stored?

PASS reply:

```text
Output capsules preserve useful work and continuation context as durable bundles under /System Outputs/{project_id}/{YYYY-MM-DD}-{slug}/. Receipts remain separate proof of system behavior. It cites concept-system-outputs-homestead-private-os-2026-06-28-output-capsule-acceptance-20260628-222457-index-c40f3eb1.
```

FAIL reply:

```text
It says capsules live in /System Receipts, treats receipts as capsules, or cannot name the /System Outputs path.
```

Expected concept ID:

```text
concept-system-outputs-homestead-private-os-2026-06-28-output-capsule-acceptance-20260628-222457-index-c40f3eb1
```

### 4. What is the Creative Coatings powder scheduler, and what problem does it solve?

PASS reply:

```text
Creative Coatings is a separate powder-schedule business workflow. Its app manages a weekly powder board, schedule inbox, core/open-order candidate pool, traveler/photo intake, Add to Schedule, Hot List, and shop handoff. It is not Homestead infrastructure. It cites concept-system-outputs-creative-coatings-2026-06-28-door-ingest-creative-coatings-capsule-59a7f1b6.
```

FAIL reply:

```text
It describes Creative Coatings as an OS runtime, runner, dashboard for Homestead, or answers without a Creative Coatings concept_id.
```

Expected concept ID:

```text
concept-system-outputs-creative-coatings-2026-06-28-door-ingest-creative-coatings-capsule-59a7f1b6
```

### 5. What is the difference between Core Dump Inbox and Schedule Intake Inbox?

PASS reply:

```text
Core Dump Inbox is for clean plant/open-order data that refreshes the In Process candidate pool. Schedule Intake Inbox is for messy human scheduling inputs such as Monday sheets, traveler photos, hot-list emails, customer notes, screenshots, PDFs, Docs, sheets, and partial files. Core refresh must not wipe schedule-inbox, weekly-board, manual, traveler, or Sent to Shop rows. It cites concept-system-outputs-creative-coatings-2026-06-28-door-ingest-creative-coatings-capsule-59a7f1b6.
```

FAIL reply:

```text
It merges the two inboxes, says core dumps replace all schedule state, or imports Homestead output-capsule rules into Creative Coatings scheduling.
```

Expected concept ID:

```text
concept-system-outputs-creative-coatings-2026-06-28-door-ingest-creative-coatings-capsule-59a7f1b6
```

### 6. Is Creative Coatings part of the Homestead runtime, or is it a separate project context?

PASS reply:

```text
Creative Coatings is a separate project context indexed by Homestead. Homestead is the private OS/control spine; Creative Coatings is a powder scheduler/workflow project. The agent should keep those contexts separate and cite both a Homestead concept and a Creative Coatings concept, such as concept-deed-571b2b47 and concept-system-outputs-creative-coatings-2026-06-28-door-ingest-creative-coatings-capsule-59a7f1b6.
```

FAIL reply:

```text
It blurs Creative Coatings into the Homestead runtime, says Homestead's disabled scheduler is the Creative Coatings scheduler, or answers with only one project's concept IDs.
```

Expected concept IDs:

```text
concept-deed-571b2b47
concept-system-outputs-creative-coatings-2026-06-28-door-ingest-creative-coatings-capsule-59a7f1b6
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

Homestead Private OS and Creative Coatings content are the required Phase 1 project pair.

The Creative Coatings ingest lives under:

```text
/System Outputs/creative-coatings/2026-06-28-door-ingest-creative-coatings/
```

Phase 1 is not complete until the live cold-boot proof passes and is tagged.
