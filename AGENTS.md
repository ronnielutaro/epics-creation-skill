# Repository guidance

## Purpose

This repository contains the `github-epic-creation` Codex skill and its deterministic helper tool. Changes must preserve the distinction between drafting an Epic and mutating live GitHub issues.

## Canonical files

- `SKILL.md` is the skill entrypoint and operating contract.
- `references/plan-format.md` defines the supported plan schema and commands.
- `references/epic-plan.example.json` must remain valid against the current tool.
- `references/epic-quality.md` owns decomposition, dependency, and evidence guidance.
- `scripts/epic_tool.py` is the executable behavior.
- `tests/test_epic_tool.py` covers meaningful behavioral invariants.
- `agents/openai.yaml` must remain consistent with the skill name and purpose.

Do not duplicate the same normative rule across several files unless a short user-facing summary is necessary. Put schema mechanics in `plan-format.md`, planning judgment in `epic-quality.md`, and essential invocation behavior in `SKILL.md`.

## Before changing files

1. Read `SKILL.md` and the reference relevant to the change.
2. Check `git status --short` and preserve unrelated work.
3. For GitHub behavior, confirm current GitHub CLI help or official documentation instead of assuming flags or response shapes.
4. Treat remembered repository or issue state as potentially stale; verify it live when the claim matters.

## Safety boundaries

- `validate`, `render`, and `preflight` must remain non-mutating with respect to GitHub.
- `apply` is the only command that creates or edits GitHub issues.
- Never run `apply` in tests or examples against a real repository.
- Live mutation requires explicit user authorization and an exact `--confirm-repository OWNER/REPO` match.
- Do not add automatic issue closing, deletion, parent replacement, PR merging, or release approval.
- Preserve resumable state after each successful creation. Do not silently restart from an empty state after partial live work.
- A plan digest mismatch must fail closed; a fresh state file can duplicate live issues.
- Preflight all available labels, assignees, milestones, issue types, repository access, and required CLI relationship support before the first mutation.
- Do not log GitHub tokens, secrets, full environment dumps, or credential-bearing command output.

## Plan and graph invariants

- Child keys are unique and stable.
- Internal dependencies form a directed acyclic graph.
- A child cannot depend on work assigned to a later phase.
- Missing edges represent safe parallelism, not unspecified order.
- Native GitHub parent/sub-issue and `blocked by` relationships are authoritative; Markdown roadmap lists are summaries.
- Each child remains independently implementable, reviewable, and verifiable.
- Acceptance criteria state observable outcomes rather than implementation activity.
- Final certification, when present, depends on every prerequisite required to prove the integrated claim.

## Editing rules

- Use Python standard-library functionality unless a new dependency has a demonstrated recurring benefit.
- Keep live mutations idempotent or safely resumable.
- Prefer explicit errors over guessed recovery after uncertain GitHub responses.
- Preserve UTF-8 output and Windows compatibility.
- Update documentation and the example in the same change when behavior or schema changes.
- Add behavioral tests for graph validation, rendering contracts, safety gates, resume behavior, and verification changes.
- Do not add tests that only match incidental wording when a state or behavior assertion is possible.

## Required verification

Run from the repository root:

```powershell
python -m py_compile scripts\epic_tool.py
python -m unittest discover -s tests -v
python scripts\epic_tool.py validate references\epic-plan.example.json
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .
```

For changes to preflight behavior, run a read-only preflight against a repository you can access. Do not use live `apply` as a routine verification step.

Before committing:

- inspect the staged diff;
- run `git diff --cached --check`;
- scan the staged diff for credentials;
- confirm generated previews, state files, caches, and environment files are not staged; and
- use a focused Conventional Commit message.

## Commit discipline

Keep code/tooling behavior separate from documentation-only changes when practical. Recommended prefixes are `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, and `chore:`. Do not merge unrelated cleanup into a behavior change.
