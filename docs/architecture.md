# System architecture

## Purpose

The GitHub Epic Creation skill converts a broad initiative into a reviewable plan and, only after explicit authorization, a verified native GitHub issue graph. Its architecture deliberately separates reasoning and local artifact generation from external mutation.

The system is a local Codex skill plus a Python command-line tool. It is not a hosted service and has no database or long-running process.

## System context

```mermaid
flowchart LR
    PM[Product manager or maintainer]
    Codex[Codex]

    subgraph Local[Local trusted workspace]
        Skill[SKILL.md<br/>workflow and safety contract]
        Guidance[Planning references<br/>schema and quality guidance]
        Plan[Epic plan JSON<br/>desired structure]
        Tool[epic_tool.py<br/>deterministic command layer]
        Preview[Rendered Markdown preview]
        State[Resume state JSON<br/>plan digest and issue mapping]
    end

    GHCLI[Authenticated GitHub CLI]

    subgraph GitHub[GitHub repository]
        Metadata[Labels, assignees,<br/>milestones, issue types]
        Parent[Native parent Epic]
        Children[Native sub-issues]
        Dependencies[Blocked-by and<br/>blocking relationships]
    end

    PM -->|intent, decisions, approval| Codex
    Skill --> Codex
    Guidance --> Codex
    Codex -->|authors or revises| Plan
    Plan --> Tool
    Tool -->|render| Preview
    Tool -->|read/write during apply| State
    Tool -->|commands| GHCLI
    GHCLI -->|read-only preflight and verify| Metadata
    GHCLI -->|authorized apply| Parent
    GHCLI -->|authorized apply| Children
    GHCLI -->|authorized apply| Dependencies
    Parent -->|live graph readback| GHCLI
    Children -->|live graph readback| GHCLI
    Dependencies -->|live graph readback| GHCLI
```

## Components and responsibilities

| Component | Responsibility | Must not do |
|---|---|---|
| `SKILL.md` | Tell Codex when and how to design an Epic, including authorization boundaries | Encode repository-specific product requirements as universal rules |
| `references/plan-format.md` | Define the JSON plan contract and command usage | Become a second implementation of validation |
| `references/epic-quality.md` | Guide decomposition, phasing, evidence, and dependency judgment | Prescribe arbitrary phase counts or issue counts |
| Epic plan JSON | Declare the intended parent, phases, children, metadata, and blockers | Claim that GitHub mutations have already succeeded |
| `scripts/epic_tool.py` | Validate, render, preflight, apply, persist resume state, and verify | Infer approval, replace parents, close issues, merge pull requests, or approve release |
| Rendered preview | Make proposed issue bodies reviewable before mutation | Act as the authoritative hierarchy or dependency graph |
| Resume state | Map stable plan keys to created issue numbers and protect partial runs from duplication | Replace GitHub as the authority for current issue relationships |
| GitHub CLI | Supply authenticated transport to GitHub | Expose credentials to the plan, logs, or generated documentation |
| GitHub Issues | Store the live parent/sub-issue hierarchy and dependency graph | Define product requirements that were absent from the approved plan |

## Command architecture

```mermaid
flowchart TB
    Plan[Epic plan JSON]
    Validate[validate<br/>local and non-mutating]
    Render[render<br/>local and non-mutating]
    Preflight[preflight<br/>GitHub read-only]
    Apply[apply<br/>GitHub mutating]
    Verify[verify<br/>GitHub read-only]

    Schema[Schema and field checks]
    Graph[DAG, phase-order,<br/>and blocker checks]
    Markdown[Parent and child Markdown]
    RepoChecks[Authentication, repository,<br/>CLI and metadata checks]
    LiveGraph[Parent, sub-issues,<br/>and blocked-by edges]
    Evidence[Readback verification result]

    Plan --> Validate
    Validate --> Schema
    Validate --> Graph
    Plan --> Render
    Render --> Markdown
    Plan --> Preflight
    Preflight --> RepoChecks
    Plan --> Apply
    RepoChecks --> Apply
    Apply --> LiveGraph
    Plan --> Verify
    LiveGraph --> Verify
    Verify --> Evidence
```

All commands run the local plan validator first. `apply` repeats preflight immediately before the first live mutation so a previously successful preflight is never treated as permanent authorization or current repository truth.

## Sources of truth

The system has different authorities at different stages:

1. **Before live creation:** the reviewed Epic plan is the desired-state declaration.
2. **During a partial apply:** GitHub is authoritative for mutations that actually succeeded; the resume state is the local durable mapping used to continue safely.
3. **After apply:** GitHub's native parent, sub-issue, and dependency relationships are authoritative. Rendered Markdown is explanatory only.
4. **For product acceptance:** linked verification evidence and required human approval remain authoritative. The tool never declares release safety on its own.

## Trust and authorization boundaries

```mermaid
flowchart LR
    Draft[Drafting boundary<br/>Codex and local files]
    Read[Read-only GitHub boundary<br/>preflight and verify]
    Write[Mutation boundary<br/>apply only]
    Approval[Explicit user authorization<br/>plus exact repository confirmation]

    Draft --> Read
    Approval --> Write
    Read --> Write
```

- `validate` and `render` do not contact or mutate GitHub.
- `preflight` and `verify` contact GitHub but do not change issue state.
- `apply` is the only mutating command.
- The `--confirm-repository OWNER/REPO` value must exactly match the plan target.
- GitHub authentication remains owned by the GitHub CLI credential store; the skill does not accept or persist tokens.

## Failure and consistency model

Live issue creation is a sequence of GitHub operations, not one transaction. The architecture therefore favors resumability over attempted rollback:

- preflight rejects missing access or metadata before the first issue is created;
- the state file is updated after every successful parent or child creation;
- dependency creation reads the current live relationships and adds only missing edges;
- body rewrites are safe to repeat;
- verification reads the native hierarchy and blockers back from GitHub;
- a plan digest mismatch fails closed because continuing with changed intent can corrupt or duplicate the graph; and
- uncertain network outcomes require manual inspection for embedded plan markers before retrying.

The tool does not delete partially created issues automatically. Automatic rollback would be destructive and could erase work that GitHub accepted even when the client did not receive a clear response.

## Extension points

Safe future extensions include additional local validation, richer preview formats, or more read-only verification. Features that widen mutation scope—such as closing issues, replacing parents, creating labels, or changing project fields—require an explicit contract, authorization model, failure strategy, and tests before implementation.
