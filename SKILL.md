---
name: github-epic-creation
description: Design and create GitHub Epic parent issues with phased native sub-issues, explicit blocked-by dependencies, implementation-ready contracts, and verified hierarchy. Use when planning or publishing a multi-issue GitHub initiative; do not use for a single standalone issue.
metadata:
  short-description: Create phased GitHub Epics and dependencies
---

# GitHub Epic Creation

Turn a broad outcome into one GitHub parent issue and a dependency-safe set of native sub-issues that can be implemented and certified in phases.

## Operating boundary

- Inspect the repository's `AGENTS.md`, issue templates, labels, issue types, open roadmap, and 2-3 recent Epics before drafting. Do not copy conventions from another repository without checking the target repository.
- Treat issue creation, relationship changes, and edits as external mutations. Draft and validate first; create or change GitHub issues only when the user has explicitly authorized it.
- Never close, delete, merge, reprioritize, or replace an existing parent relationship unless the user explicitly asks.
- Use GitHub native parent/sub-issue and dependency relationships. Markdown checklists may summarize the roadmap, but they are not substitutes for those relationships.
- Do not invent requirements, evidence, measurements, owners, dates, or approval decisions. Mark unknowns and decision gates explicitly.

## Workflow

1. **Establish repository truth.** Read governance and current artifacts. Identify the outcome, present failure or opportunity, authoritative systems, scope boundaries, irreversible decisions, verification environment, and existing issues that constrain the work.
2. **Design the dependency graph before writing prose.** Define stable child keys, assign them to phases, and add only real prerequisite edges. Work without an edge may proceed in parallel. Reject cycles and any issue that depends on a later phase.
3. **Make every child independently deliverable.** Each child needs one outcome, bounded in/out scope, testable acceptance criteria, required verification, closure evidence, and explicit blockers. Split a child when it spans unrelated contracts or cannot be reviewed in one focused change.
4. **Add a final certification child for risky or cross-layer work.** It must depend on every prerequisite needed for release and verify the integrated outcome against authoritative state. A build, HTTP 200, mock, screenshot, or UI success message alone is not release evidence.
5. **Write the parent as the release contract.** Include the objective, primary invariant, locked decisions, boundaries, phased roadmap and checkpoints, dependency order, delivery discipline, exit criteria, and completion policy. Keep implementation detail in children.
6. **Validate and review the draft.** Use the bundled tool and inspect the rendered Markdown. Check that the graph matches the prose, every exit criterion has an owning child or certification check, and the final gate is actually blocked by its prerequisites.
7. **Create only after approval.** Run the explicit apply command. It creates the parent, creates children with native parent links, adds native `blocked by` relationships, rewrites bodies with final issue links, records resumable state, and verifies the live graph.
8. **Report evidence.** Return the parent URL, child URLs grouped by phase, dependency/parallelism summary, verification result, and any residual gaps. Do not call a partial run complete.

## Plan and tooling

Read [references/plan-format.md](references/plan-format.md) before authoring a plan. Use [references/epic-quality.md](references/epic-quality.md) when deciding issue boundaries, phases, evidence, and closure gates.

```powershell
python scripts/epic_tool.py validate path\to\epic-plan.json
python scripts/epic_tool.py render path\to\epic-plan.json --output-dir path\to\preview
python scripts/epic_tool.py preflight path\to\epic-plan.json
```

Show the rendered parent and child contracts to the user before live creation when the requested scope is still being negotiated.

After explicit authorization, create the live graph with an exact repository confirmation:

```powershell
python scripts/epic_tool.py apply path\to\epic-plan.json --confirm-repository OWNER/REPO
```

The default state file is `<plan>.state.json`. Preserve it until verification succeeds; rerunning `apply` resumes recorded work instead of intentionally creating duplicates. If a mutation succeeds but the process stops before state is written, inspect GitHub for the plan markers before retrying.

Verify again at any time:

```powershell
python scripts/epic_tool.py verify path\to\epic-plan.json
```

## Relationship semantics

For `blocked_by`, read the edge literally: issue A with `blocked_by: [B]` cannot complete until B completes. Do not encode mere sequence preferences, shared context, or likely coordination as blockers. Use phase text for those.

Prefer a shallow hierarchy: one Epic parent and implementation children. Introduce nested children only when a child is itself a separately managed program. GitHub supports at most 100 direct sub-issues per parent and eight hierarchy levels; a plan near those limits should be split into multiple Epics.

## Quality standard

An Epic is ready to publish only when:

- the parent states an observable outcome and a falsifiable invariant;
- phases have meaningful checkpoints, not arbitrary buckets;
- dependencies form a directed acyclic graph and safe parallelism is visible;
- child acceptance criteria describe behavior or state, not implementation activity;
- verification names the relevant authority (database, API, generated contract, UI, provider, or operational signal);
- destructive, schema, migration, production-data, security, or release decisions have explicit approval gates where needed;
- closure requires integrated evidence and any required human approval, not automatic closure after the last PR.
