# GitHub Epic Creation Skill

A Codex skill for designing and publishing implementation-ready GitHub Epics with phased native sub-issues, explicit `blocked by` relationships, release checkpoints, and evidence-based closure rules.

The skill helps turn a broad initiative into:

- one parent Epic that acts as the release contract;
- independently implementable child issues grouped into meaningful phases;
- a directed, cycle-free dependency graph;
- native GitHub parent/sub-issue and dependency relationships;
- a final integrated certification gate when the work warrants one; and
- a resumable record of every live issue created.

## What makes this different

Markdown checklists are useful summaries, but they do not create GitHub's native hierarchy or dependency indicators. This skill uses the GitHub features that show an issue's parent, sub-issues, `blocked by`, and `blocking` relationships directly in the interface.

It also separates safe planning from live mutation:

1. `validate` checks the plan and dependency graph locally.
2. `render` creates reviewable Markdown previews.
3. `preflight` checks GitHub access and repository metadata without changing issues.
4. `apply` creates or resumes the live issue graph only with an exact repository confirmation.
5. `verify` reads the live graph back and confirms its hierarchy and blockers.

## Requirements

- Python 3.10 or newer.
- An authenticated [GitHub CLI](https://cli.github.com/) version that supports issue `--parent` and dependency flags.
- At least triage permission in the target repository to manage sub-issues and dependencies.
- Codex for automatic skill discovery, or direct use of the bundled Python tool.

## Install as a Codex skill

On Windows PowerShell:

```powershell
git clone https://github.com/ronnielutaro/epics-creation-skill.git "$env:USERPROFILE\.codex\skills\github-epic-creation"
```

Start a new Codex task after installation so the skill is discovered. Invoke it explicitly with `$github-epic-creation`, or let Codex select it for multi-issue Epic planning requests.

## Quick start

Copy the example plan and replace its repository, outcomes, phases, issue contracts, and dependencies:

```powershell
Copy-Item references\epic-plan.example.json my-epic.json
python scripts\epic_tool.py validate my-epic.json
python scripts\epic_tool.py render my-epic.json --output-dir .epic-preview
python scripts\epic_tool.py preflight my-epic.json
```

Review the rendered parent and child issue bodies before creating anything on GitHub.

After the repository owner explicitly approves live creation:

```powershell
python scripts\epic_tool.py apply my-epic.json --confirm-repository OWNER/REPO
```

Verify the graph later with:

```powershell
python scripts\epic_tool.py verify my-epic.json
```

The default resume file is `my-epic.json.state.json`. Keep it until verification succeeds. Do not discard it during a partial run, because it prevents accidental duplicate issue creation.

## Plan model

An Epic plan contains:

- a stable plan key and exact `OWNER/REPO` target;
- the parent Epic's objective, primary invariant, boundaries, decisions, exit criteria, and completion policy;
- ordered phases with explicit checkpoints;
- child issues with outcomes, bounded scope, acceptance criteria, verification, and closure evidence; and
- `blocked_by` edges referencing another child key, an existing issue number, or a full GitHub issue URL.

See [the plan format and complete example](references/plan-format.md) and the reusable [example JSON](references/epic-plan.example.json).

## Dependency rules

The validator rejects:

- duplicate phase or child keys;
- unknown internal blockers;
- dependency cycles;
- children blocked by work in a later phase;
- malformed external issue references; and
- Epics exceeding GitHub's 100 direct sub-issue limit.

No dependency edge means the work may proceed in parallel when its phase checkpoint permits. Numbering alone does not create a blocker.

## Safety model

- Planning and rendering are local operations.
- Preflight is read-only.
- Live creation requires the `apply` subcommand and an exact `--confirm-repository OWNER/REPO` value.
- Repository labels, assignees, milestones, and issue types are checked before the first issue is created.
- State is written after every successful creation so normal interruptions can resume.
- Existing parent relationships are never replaced by this tool.
- The tool does not close issues, delete issues, merge pull requests, or automatically declare an Epic complete.

Live creation is not transactional. If GitHub accepts a mutation but the network response is uncertain, inspect GitHub for the embedded `codex-epic-key` markers before retrying.

## Project structure

```text
.
|-- SKILL.md                         Codex entrypoint and operating contract
|-- agents/openai.yaml               Skill display metadata
|-- docs/                             Architecture, data flow, and decisions
|-- references/
|   |-- epic-plan.example.json       Reusable plan example
|   |-- epic-quality.md              Decomposition and evidence guidance
|   `-- plan-format.md               Plan schema and command reference
|-- scripts/epic_tool.py             Validate/render/preflight/apply/verify tool
`-- tests/test_epic_tool.py           Behavioral tests
```

## Development and verification

Run the behavioral suite:

```powershell
python -m unittest discover -s tests -v
```

Validate the example:

```powershell
python scripts\epic_tool.py validate references\epic-plan.example.json
```

Validate the skill package with Codex's `skill-creator` validator when it is available:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .
```

## Design guidance

Read [Epic decomposition and evidence](references/epic-quality.md) before publishing a cross-layer or release-critical initiative. The central rule is simple: phases communicate risk retirement, while native dependency edges encode prerequisites that truly block safe completion.

For the implementation design, see the [documentation index](docs/README.md), [system architecture](docs/architecture.md), and [data-flow design](docs/data-flow.md).

GitHub references:

- [Adding sub-issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues)
- [Creating issue dependencies](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies)

## Contributing

Keep changes focused and preserve the separation between read-only planning and external mutation. Run the complete test suite and skill validator before committing. Changes to live-mutation behavior should include tests for failure, retry, resume, and duplicate-prevention boundaries.
