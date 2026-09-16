# ADR-0001: Separate planning from resumable live mutation

## Status

Accepted

## Date

2026-09-16

## Context

Creating a multi-issue GitHub Epic is not one atomic operation. The system must create a parent, create several children, attach native parent relationships, add dependency edges, update issue bodies with final references, and read the graph back. Network or API failure can interrupt that sequence after GitHub has accepted some mutations.

The same workflow also needs a safe drafting mode. Product scope and dependency order often change during review, and those changes should not create or edit live issues before the repository owner approves the plan.

## Decision

Separate the workflow into local planning, read-only GitHub checks, explicit live mutation, and read-only verification:

- `validate` and `render` operate locally;
- `preflight` reads GitHub prerequisites without mutation;
- `apply` is the only mutating command and requires an exact repository confirmation;
- `apply` persists a plan digest and issue mapping after each successful creation;
- reruns resume recorded work and add only missing dependency edges; and
- `verify` reads the native GitHub graph back before completion is reported.

Do not automatically roll back partial creation by deleting issues. Preserve accepted GitHub state and require reconciliation when an outcome is uncertain.

## Alternatives considered

### Create issues directly from Codex prompts

- **Advantage:** Fewer local artifacts and commands.
- **Rejected because:** The proposed graph is harder to review before mutation, retries have no durable mapping, and partial failures can create duplicates.

### Treat Markdown task lists as the hierarchy

- **Advantage:** One issue edit can describe the complete roadmap.
- **Rejected because:** Markdown does not provide GitHub's native parent/sub-issue navigation or dependency status and cannot be verified as the live relationship graph.

### Roll back every partial run

- **Advantage:** Attempts to restore an all-or-nothing appearance.
- **Rejected because:** GitHub mutations are not transactional, client uncertainty can hide successful writes, and automatic deletion is destructive.

### Use a hosted service and database

- **Advantage:** Central coordination and richer operation tracking.
- **Rejected for the current scope because:** A local tool and small state file provide sufficient resumability without introducing hosting, database, authentication, or operational dependencies.

## Consequences

### Positive

- Plans can be reviewed without touching GitHub.
- Authorization is visible at the mutation boundary.
- Normal interruptions can resume without intentionally duplicating recorded issues.
- Native GitHub relationships remain the live source of truth.
- Verification is distinct from optimistic command success.

### Costs and constraints

- Users must preserve the state file until verification succeeds.
- Live creation remains eventually assembled rather than atomic.
- Uncertain network outcomes may require manual GitHub inspection.
- Plan changes during a partial apply require deliberate reconciliation instead of automatic continuation.

## Follow-up implications

Any new mutating capability must be added only to the explicit mutation boundary and must define authorization, preflight, resumability, failure recovery, and live verification before implementation.
