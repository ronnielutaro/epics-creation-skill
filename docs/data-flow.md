# Data flow

## Overview

The system moves one desired-state plan through five increasingly authoritative stages: validation, preview, repository preflight, live creation, and live verification. Only the fourth stage mutates GitHub.

## End-to-end flow

```mermaid
flowchart TD
    Intent[Product intent and repository evidence]
    Draft[Codex drafts Epic plan JSON]
    Validate{Plan valid?}
    Preview[Render parent and child Markdown]
    Review{Human review complete?}
    Preflight{GitHub preflight passes?}
    Authorize{Explicit live-creation approval<br/>and exact repository confirmation?}
    Apply[Create or resume live graph]
    Verify{Live hierarchy and blockers match?}
    Done[Verified Epic URL, child URLs,<br/>and dependency summary]
    Revise[Revise plan without mutation]
    Recover[Preserve state and inspect<br/>partial or uncertain outcome]

    Intent --> Draft
    Draft --> Validate
    Validate -->|no| Revise
    Revise --> Draft
    Validate -->|yes| Preview
    Preview --> Review
    Review -->|changes required| Revise
    Review -->|approved draft| Preflight
    Preflight -->|no| Revise
    Preflight -->|yes| Authorize
    Authorize -->|no| Preview
    Authorize -->|yes| Apply
    Apply --> Verify
    Apply -->|interrupted or uncertain| Recover
    Recover -->|reconciled| Apply
    Verify -->|no| Recover
    Verify -->|yes| Done
```

## Command data paths

| Command | Inputs | Reads | Writes | External mutation |
|---|---|---|---|---|
| `validate` | Plan JSON | Local plan | JSON summary to standard output | None |
| `render` | Plan JSON, optional state | Local plan and optional state | Markdown preview and manifest | None |
| `preflight` | Plan JSON | GitHub authentication, repository, CLI capabilities, labels, assignees, milestones, issue types | JSON readiness summary to standard output | None |
| `apply` | Plan JSON, exact repository confirmation, optional state | Local plan/state and GitHub metadata/relationships | GitHub issues and relationships; local state file | Creates/edits issues and dependencies |
| `verify` | Plan JSON and state | GitHub parent, sub-issues, titles, and blockers | JSON verification summary to standard output | None |

## Apply sequence

```mermaid
sequenceDiagram
    actor User
    participant Codex
    participant Tool as epic_tool.py
    participant State as Resume state
    participant CLI as GitHub CLI
    participant Repo as GitHub repository

    User->>Codex: Approve live creation for OWNER/REPO
    Codex->>Tool: apply plan --confirm-repository OWNER/REPO
    Tool->>Tool: Validate schema and dependency graph
    Tool->>State: Load state if present
    Tool->>Tool: Verify plan key, repository, and digest
    Tool->>CLI: Check auth, repository, flags, and metadata
    CLI->>Repo: Read repository configuration
    Repo-->>CLI: Current labels, users, milestones, and types
    CLI-->>Tool: Preflight result

    alt Parent not recorded
        Tool->>CLI: Create parent Epic
        CLI->>Repo: Create issue
        Repo-->>CLI: Parent number and URL
        CLI-->>Tool: Parent number and URL
        Tool->>State: Persist parent mapping
    end

    loop Each unrecorded child
        Tool->>CLI: Create child with native parent
        CLI->>Repo: Create sub-issue
        Repo-->>CLI: Child number and URL
        CLI-->>Tool: Child number and URL
        Tool->>State: Persist child mapping
    end

    loop Each child with blockers
        Tool->>CLI: Read current blocked-by relationships
        CLI->>Repo: Query child
        Repo-->>CLI: Current blockers
        CLI-->>Tool: Current blockers
        Tool->>CLI: Add only missing blocker edges
        CLI->>Repo: Update dependencies
        Tool->>State: Record dependency progress
    end

    Tool->>CLI: Rewrite bodies with final issue references
    CLI->>Repo: Edit parent and child descriptions
    Tool->>CLI: Read parent, children, and blockers
    CLI->>Repo: Query live graph
    Repo-->>CLI: Native hierarchy and dependency graph
    CLI-->>Tool: Live graph
    Tool->>Tool: Compare plan, state, and GitHub
    Tool->>State: Mark completed with verification result
    Tool-->>Codex: Verified URLs and graph summary
    Codex-->>User: Publish evidence and residual gaps
```

## Plan-to-GitHub transformation

```mermaid
flowchart LR
    subgraph Plan[Plan JSON]
        EpicSpec[Epic contract]
        Phases[Ordered phases]
        ChildSpecs[Child contracts]
        Blockers[blocked_by references]
        MetadataSpec[Labels, assignees,<br/>milestones, issue types]
    end

    subgraph Local[Local transformation]
        Validation[Schema and graph validation]
        Rendering[Markdown rendering]
        Resolution[Stable key to issue-number resolution]
    end

    subgraph Live[GitHub live state]
        EpicIssue[Parent issue]
        ChildIssues[Native sub-issues]
        Edges[Native dependency edges]
        MetadataLive[Repository metadata assignments]
    end

    EpicSpec --> Validation --> Rendering --> EpicIssue
    Phases --> Validation
    ChildSpecs --> Validation --> Rendering --> ChildIssues
    Blockers --> Validation --> Resolution --> Edges
    MetadataSpec --> Validation --> MetadataLive
```

Phases remain descriptive roadmap structure in the issue bodies. Child-parent links and dependency edges become native GitHub relationships.

## Resume-state flow

The state file contains operational identity, not product truth:

```text
plan key + repository + plan SHA-256
    -> parent issue number and URL
    -> child key to issue number and URL mappings
    -> completed dependency operations
    -> final verification result
```

It is written atomically after each successful creation. The plan digest prevents a changed plan from silently resuming against issues created from different intent.

## Error and recovery paths

| Failure point | Expected effect | Recovery |
|---|---|---|
| Local validation | No GitHub access or mutation | Correct the plan and rerun |
| Preflight | No issue creation | Fix access, repository metadata, or CLI capability |
| Parent creation before response is known | GitHub outcome may be uncertain | Search for the plan marker before retrying |
| Child creation after earlier children succeeded | Partial native hierarchy remains | Preserve state and rerun after confirming the last outcome |
| Dependency update | Issues exist; some edges may be missing | Rerun; the tool reads current edges and adds only missing ones |
| Body rewrite | Relationships exist; prose may contain incomplete references | Rerun; body edits are repeatable |
| Verification | Live graph differs from the plan | Inspect the reported missing parent or blocker relationships, reconcile, then rerun |
| Plan digest mismatch | Apply stops before continuing | Restore the original plan or manually reconcile the plan, state, and live issues |

## Data that must not flow through the system

- GitHub access tokens or credential-store contents;
- environment dumps;
- secrets embedded in issue bodies or plan metadata;
- invented product requirements, owners, dates, metrics, or approval decisions; and
- claims that a live mutation succeeded without GitHub readback.
