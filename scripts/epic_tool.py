#!/usr/bin/env python3
"""Validate, render, create, and verify phased GitHub Epic issue graphs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlparse


KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ISSUE_URL_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)/?$"
)


class PlanError(Exception):
    """Raised when a plan or live graph is invalid."""


def load_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanError(f"Plan file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise PlanError("The plan root must be a JSON object.")
    return value


def plan_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_string_list(errors: list[str], value: Any, path: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array of strings")
        return
    if not allow_empty and not value:
        errors.append(f"{path} must contain at least one item")
    for index, item in enumerate(value):
        if not _is_nonempty_string(item):
            errors.append(f"{path}[{index}] must be a non-empty string")


def _check_metadata(errors: list[str], item: dict[str, Any], path: str) -> None:
    for field in ("labels", "assignees"):
        if field in item:
            _check_string_list(errors, item[field], f"{path}.{field}", allow_empty=True)
    for field in ("issue_type", "milestone"):
        if field in item and not _is_nonempty_string(item[field]):
            errors.append(f"{path}.{field} must be a non-empty string")


def flatten_issues(plan: dict[str, Any]) -> list[tuple[int, dict[str, Any], dict[str, Any]]]:
    result: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for phase_index, phase in enumerate(plan.get("phases", [])):
        if not isinstance(phase, dict):
            continue
        for issue in phase.get("issues", []):
            if isinstance(issue, dict):
                result.append((phase_index, phase, issue))
    return result


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    key = plan.get("key")
    if not _is_nonempty_string(key) or not KEY_RE.fullmatch(key):
        errors.append("key must use lowercase letters, digits, and hyphens")

    repository = plan.get("repository")
    if not _is_nonempty_string(repository) or not REPOSITORY_RE.fullmatch(repository):
        errors.append("repository must be an exact OWNER/REPO value")

    defaults = plan.get("defaults", {})
    if not isinstance(defaults, dict):
        errors.append("defaults must be an object when present")
    else:
        _check_metadata(errors, defaults, "defaults")

    epic = plan.get("epic")
    if not isinstance(epic, dict):
        errors.append("epic must be an object")
        epic = {}
    for field in ("title", "objective", "primary_invariant", "completion_policy"):
        if not _is_nonempty_string(epic.get(field)):
            errors.append(f"epic.{field} must be a non-empty string")
    for field in ("in_scope", "out_of_scope", "exit_criteria"):
        _check_string_list(errors, epic.get(field), f"epic.{field}")
    for field in ("context", "delivery_rules", "verification_doctrine"):
        if field in epic:
            _check_string_list(errors, epic[field], f"epic.{field}", allow_empty=True)
    decisions = epic.get("decisions", [])
    if not isinstance(decisions, list):
        errors.append("epic.decisions must be an array")
    else:
        for index, decision in enumerate(decisions):
            path = f"epic.decisions[{index}]"
            if not isinstance(decision, dict):
                errors.append(f"{path} must be an object")
                continue
            if not _is_nonempty_string(decision.get("title")):
                errors.append(f"{path}.title must be a non-empty string")
            _check_string_list(errors, decision.get("points"), f"{path}.points")
    _check_metadata(errors, epic, "epic")

    phases = plan.get("phases")
    if not isinstance(phases, list) or not phases:
        errors.append("phases must contain at least one phase")
        phases = []

    phase_keys: set[str] = set()
    issue_keys: set[str] = set()
    phase_for_issue: dict[str, int] = {}
    issues_by_key: dict[str, dict[str, Any]] = {}

    for phase_index, phase in enumerate(phases):
        phase_path = f"phases[{phase_index}]"
        if not isinstance(phase, dict):
            errors.append(f"{phase_path} must be an object")
            continue
        phase_key = phase.get("key")
        if not _is_nonempty_string(phase_key) or not KEY_RE.fullmatch(phase_key):
            errors.append(f"{phase_path}.key must use lowercase letters, digits, and hyphens")
        elif phase_key in phase_keys:
            errors.append(f"Duplicate phase key: {phase_key}")
        else:
            phase_keys.add(phase_key)
        for field in ("title", "purpose"):
            if not _is_nonempty_string(phase.get(field)):
                errors.append(f"{phase_path}.{field} must be a non-empty string")
        _check_string_list(errors, phase.get("checkpoint"), f"{phase_path}.checkpoint")

        issues = phase.get("issues")
        if not isinstance(issues, list) or not issues:
            errors.append(f"{phase_path}.issues must contain at least one child issue")
            continue
        for issue_index, issue in enumerate(issues):
            issue_path = f"{phase_path}.issues[{issue_index}]"
            if not isinstance(issue, dict):
                errors.append(f"{issue_path} must be an object")
                continue
            issue_key = issue.get("key")
            if not _is_nonempty_string(issue_key) or not KEY_RE.fullmatch(issue_key):
                errors.append(f"{issue_path}.key must use lowercase letters, digits, and hyphens")
            elif issue_key in issue_keys:
                errors.append(f"Duplicate issue key: {issue_key}")
            else:
                issue_keys.add(issue_key)
                phase_for_issue[issue_key] = phase_index
                issues_by_key[issue_key] = issue
            for field in ("title", "outcome"):
                if not _is_nonempty_string(issue.get(field)):
                    errors.append(f"{issue_path}.{field} must be a non-empty string")
            for field in (
                "in_scope",
                "out_of_scope",
                "acceptance_criteria",
                "verification",
                "closure_evidence",
            ):
                _check_string_list(errors, issue.get(field), f"{issue_path}.{field}")
            for field in ("problem", "implementation_constraints", "delivery_requirements"):
                if field in issue:
                    _check_string_list(errors, issue[field], f"{issue_path}.{field}", allow_empty=True)
            if "completion_rule" in issue and not _is_nonempty_string(issue["completion_rule"]):
                errors.append(f"{issue_path}.completion_rule must be a non-empty string")
            _check_metadata(errors, issue, issue_path)
            blockers = issue.get("blocked_by", [])
            if not isinstance(blockers, list):
                errors.append(f"{issue_path}.blocked_by must be an array")
            else:
                for blocker_index, blocker in enumerate(blockers):
                    blocker_path = f"{issue_path}.blocked_by[{blocker_index}]"
                    if isinstance(blocker, int):
                        if blocker <= 0:
                            errors.append(f"{blocker_path} must be a positive issue number")
                    elif _is_nonempty_string(blocker):
                        if blocker == issue_key:
                            errors.append(f"{issue_path} cannot block itself")
                        elif blocker not in issue_keys and not KEY_RE.fullmatch(blocker) and not ISSUE_URL_RE.fullmatch(blocker):
                            errors.append(
                                f"{blocker_path} must be a child key, positive issue number, or full GitHub issue URL"
                            )
                    else:
                        errors.append(
                            f"{blocker_path} must be a child key, positive issue number, or full GitHub issue URL"
                        )

    issue_count = len(issue_keys)
    if issue_count > 100:
        errors.append(f"The Epic has {issue_count} children; GitHub permits at most 100 direct sub-issues")

    # Resolve internal blocker keys after all issues are known, then enforce phase order.
    graph: dict[str, list[str]] = {issue_key: [] for issue_key in issue_keys}
    for issue_key, issue in issues_by_key.items():
        for blocker in issue.get("blocked_by", []):
            if isinstance(blocker, str) and KEY_RE.fullmatch(blocker):
                if blocker not in issue_keys:
                    errors.append(f"Issue {issue_key} references unknown blocker key: {blocker}")
                    continue
                graph[issue_key].append(blocker)
                if phase_for_issue[blocker] > phase_for_issue[issue_key]:
                    errors.append(
                        f"Issue {issue_key} in phase {phase_for_issue[issue_key]} cannot be blocked by later-phase issue {blocker}"
                    )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in visiting:
            start = trail.index(node) if node in trail else 0
            errors.append("Dependency cycle: " + " -> ".join(trail[start:] + [node]))
            return
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            visit(dependency, trail + [node])
        visiting.remove(node)
        visited.add(node)

    for issue_key in sorted(issue_keys):
        visit(issue_key, [])

    if errors:
        raise PlanError("Plan validation failed:\n- " + "\n- ".join(errors))

    return {
        "plan_key": key,
        "repository": repository,
        "phase_count": len(phases),
        "issue_count": issue_count,
        "internal_dependency_count": sum(len(values) for values in graph.values()),
        "external_dependency_count": sum(
            1
            for _, _, issue in flatten_issues(plan)
            for blocker in issue.get("blocked_by", [])
            if not (isinstance(blocker, str) and blocker in issue_keys)
        ),
    }


def _bullets(items: Iterable[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _checks(items: Iterable[str]) -> list[str]:
    return [f"- [ ] {item}" for item in items]


def _section(lines: list[str], title: str, content: list[str]) -> None:
    if content:
        lines.extend([f"## {title}", "", *content, ""])


def _state_issue(state: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    if not state:
        return None
    value = state.get("issues", {}).get(key)
    return value if isinstance(value, dict) else None


def _blocker_display(
    blocker: str | int,
    plan: dict[str, Any],
    state: dict[str, Any] | None,
) -> str:
    if isinstance(blocker, int):
        return f"#{blocker}"
    child = _state_issue(state, blocker)
    if child:
        return f"#{child['number']}"
    if ISSUE_URL_RE.fullmatch(blocker):
        return blocker
    issue = next(
        (candidate for _, _, candidate in flatten_issues(plan) if candidate.get("key") == blocker),
        None,
    )
    return f"`{blocker}` — {issue['title']}" if issue else f"`{blocker}`"


def render_epic(plan: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    epic = plan["epic"]
    lines = [f"<!-- codex-epic-key: {plan['key']} -->", "", "## Objective", "", epic["objective"], ""]
    lines.extend(["## Primary invariant", "", f"> {epic['primary_invariant']}", ""])
    _section(lines, "Context and baseline", _bullets(epic.get("context", [])))
    for decision in epic.get("decisions", []):
        _section(lines, f"Locked decision: {decision['title']}", _bullets(decision["points"]))
    _section(lines, "Scope", ["### Included", "", *_bullets(epic["in_scope"]), "", "### Excluded", "", *_bullets(epic["out_of_scope"])])

    lines.extend(["## Phased roadmap", ""])
    for phase in plan["phases"]:
        lines.extend([f"### {phase['title']}", "", phase["purpose"], ""])
        for issue in phase["issues"]:
            child = _state_issue(state, issue["key"])
            ref = f"#{child['number']}" if child else f"`{issue['key']}`"
            lines.append(f"- [ ] {ref} — {issue['title']}")
        lines.extend(["", "#### Checkpoint", "", *_checks(phase["checkpoint"]), ""])

    dependency_lines: list[str] = []
    for _, _, issue in flatten_issues(plan):
        blockers = issue.get("blocked_by", [])
        if blockers:
            child = _state_issue(state, issue["key"])
            issue_ref = f"#{child['number']}" if child else f"`{issue['key']}`"
            rendered = ", ".join(_blocker_display(blocker, plan, state) for blocker in blockers)
            dependency_lines.append(f"- {issue_ref} is blocked by {rendered}.")
    if not dependency_lines:
        dependency_lines = ["- No blocking edges are required; all children may proceed according to phase checkpoints."]
    _section(lines, "Dependency order and safe parallelism", dependency_lines)
    _section(lines, "Delivery discipline", _bullets(epic.get("delivery_rules", [])))
    _section(lines, "Verification doctrine", _bullets(epic.get("verification_doctrine", [])))
    _section(lines, "Epic exit criteria", _checks(epic["exit_criteria"]))
    _section(lines, "Completion policy", [epic["completion_policy"]])
    return "\n".join(lines).rstrip() + "\n"


def render_child(
    plan: dict[str, Any],
    phase: dict[str, Any],
    issue: dict[str, Any],
    state: dict[str, Any] | None = None,
) -> str:
    epic_state = state.get("epic") if state else None
    parent_ref = f"#{epic_state['number']}" if isinstance(epic_state, dict) else "the Epic created from this plan"
    lines = [
        f"<!-- codex-epic-key: {plan['key']} -->",
        f"<!-- codex-epic-child: {issue['key']} -->",
        "",
        "## Parent and phase",
        "",
        f"- Parent: {parent_ref}",
        f"- Phase: {phase['title']}",
        "",
        "## Outcome",
        "",
        issue["outcome"],
        "",
    ]
    _section(lines, "Problem or evidence", _bullets(issue.get("problem", [])))
    _section(
        lines,
        "Scope",
        ["### Included", "", *_bullets(issue["in_scope"]), "", "### Excluded", "", *_bullets(issue["out_of_scope"])],
    )
    _section(lines, "Implementation constraints", _bullets(issue.get("implementation_constraints", [])))
    _section(lines, "Acceptance criteria", _checks(issue["acceptance_criteria"]))
    _section(lines, "Required verification", _bullets(issue["verification"]))
    _section(lines, "Required closure evidence", _bullets(issue["closure_evidence"]))
    blockers = issue.get("blocked_by", [])
    dependency_lines = (
        [f"- Blocked by: {', '.join(_blocker_display(blocker, plan, state) for blocker in blockers)}"]
        if blockers
        else ["- No blocking issue. This child may start when its phase checkpoint permits."]
    )
    _section(lines, "Dependencies", dependency_lines)
    inherited = plan["epic"].get("delivery_rules", [])
    _section(lines, "Delivery requirements", _bullets([*inherited, *issue.get("delivery_requirements", [])]))
    if issue.get("completion_rule"):
        _section(lines, "Completion rule", [issue["completion_rule"]])
    return "\n".join(lines).rstrip() + "\n"


def render_all(plan: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, str]:
    rendered = {"epic.md": render_epic(plan, state)}
    for _, phase, issue in flatten_issues(plan):
        rendered[f"children/{phase['key']}--{issue['key']}.md"] = render_child(plan, phase, issue, state)
    return rendered


def write_rendered(plan: dict[str, Any], output_dir: Path, state: dict[str, Any] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = render_all(plan, state)
    manifest: dict[str, Any] = {"repository": plan["repository"], "plan_key": plan["key"], "files": []}
    for relative, body in files.items():
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8", newline="\n")
        manifest["files"].append(relative)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def _run(command: list[str], *, input_text: str | None = None) -> str:
    try:
        completed = subprocess.run(
            command,
            input=input_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise PlanError(f"Required executable not found: {command[0]}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise PlanError(f"Command failed ({' '.join(command)}):\n{detail}")
    return completed.stdout.strip()


def _gh_json(arguments: list[str]) -> Any:
    output = _run(["gh", *arguments])
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise PlanError(f"GitHub CLI returned invalid JSON for: gh {' '.join(arguments)}") from exc


def _unique_strings(*collections: Iterable[str]) -> list[str]:
    result: list[str] = []
    for collection in collections:
        for item in collection:
            if item not in result:
                result.append(item)
    return result


def _metadata(plan: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    defaults = plan.get("defaults", {})
    return {
        "labels": _unique_strings(defaults.get("labels", []), item.get("labels", [])),
        "assignees": _unique_strings(defaults.get("assignees", []), item.get("assignees", [])),
        "issue_type": item.get("issue_type", defaults.get("issue_type")),
        "milestone": item.get("milestone"),
    }


def preflight(plan: dict[str, Any]) -> dict[str, Any]:
    repository = plan["repository"]
    owner, name = repository.split("/", 1)
    _run(["gh", "auth", "status", "--hostname", "github.com"])
    repo_info = _gh_json(["repo", "view", repository, "--json", "nameWithOwner,url"])
    if repo_info.get("nameWithOwner", "").lower() != repository.lower():
        raise PlanError(f"GitHub resolved {repository} as {repo_info.get('nameWithOwner')}")

    create_help = _run(["gh", "issue", "create", "--help"])
    edit_help = _run(["gh", "issue", "edit", "--help"])
    for flag, help_text in (("--parent", create_help), ("--add-blocked-by", edit_help)):
        if flag not in help_text:
            raise PlanError(f"Installed GitHub CLI does not support required flag {flag}; update gh first")

    all_items = [plan["epic"], *(issue for _, _, issue in flatten_issues(plan))]
    metadata = [_metadata(plan, item) for item in all_items]
    wanted_labels = {label for item in metadata for label in item["labels"]}
    available_labels = {
        item["name"] for item in _gh_json(["label", "list", "-R", repository, "--limit", "1000", "--json", "name"])
    }
    missing_labels = sorted(wanted_labels - available_labels)
    if missing_labels:
        raise PlanError("Missing repository labels: " + ", ".join(missing_labels))

    wanted_assignees = {login for item in metadata for login in item["assignees"] if login != "@me"}
    for login in sorted(wanted_assignees):
        _run(["gh", "api", f"repos/{owner}/{name}/assignees/{quote(login, safe='')}"])

    wanted_milestones = {item["milestone"] for item in metadata if item["milestone"]}
    if wanted_milestones:
        milestones = _gh_json(["api", f"repos/{owner}/{name}/milestones?state=all&per_page=100"])
        available_milestones = {item["title"] for item in milestones}
        missing_milestones = sorted(wanted_milestones - available_milestones)
        if missing_milestones:
            raise PlanError("Missing repository milestones: " + ", ".join(missing_milestones))

    wanted_types = {item["issue_type"] for item in metadata if item["issue_type"]}
    if wanted_types:
        query = """
query($owner:String!, $name:String!) {
  repository(owner:$owner, name:$name) { issueTypes(first:100) { nodes { name } } }
}
""".strip()
        response = _gh_json(
            ["api", "graphql", "-f", f"query={query}", "-F", f"owner={owner}", "-F", f"name={name}"]
        )
        nodes = (((response.get("data") or {}).get("repository") or {}).get("issueTypes") or {}).get("nodes", [])
        available_types = {item["name"] for item in nodes}
        missing_types = sorted(wanted_types - available_types)
        if missing_types:
            raise PlanError("Missing repository issue types: " + ", ".join(missing_types))

    return {
        "repository": repo_info["nameWithOwner"],
        "url": repo_info["url"],
        "labels_checked": len(wanted_labels),
        "assignees_checked": len(wanted_assignees),
        "milestones_checked": len(wanted_milestones),
        "issue_types_checked": len(wanted_types),
    }


def _load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlanError(f"Invalid state file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlanError(f"State file root must be an object: {path}")
    return value


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)


def _check_state(state: dict[str, Any], plan: dict[str, Any], digest: str) -> None:
    if state.get("repository", "").lower() != plan["repository"].lower():
        raise PlanError("State repository does not match the plan")
    if state.get("plan_key") != plan["key"]:
        raise PlanError("State plan_key does not match the plan")
    if state.get("plan_sha256") != digest:
        raise PlanError(
            "Plan changed since the state file was created. Do not discard the state file or rerun against a fresh one, "
            "because that can duplicate live issues. Restore the original plan, or manually reconcile the reviewed plan "
            "and state before resuming."
        )


def _parse_issue_url(output: str, repository: str) -> dict[str, Any]:
    matches = re.findall(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[1-9][0-9]*", output)
    if not matches:
        raise PlanError(f"Could not find a created issue URL in GitHub CLI output: {output}")
    url = matches[-1]
    match = ISSUE_URL_RE.fullmatch(url)
    assert match is not None
    actual_repository = f"{match.group(1)}/{match.group(2)}"
    if actual_repository.lower() != repository.lower():
        raise PlanError(f"Created issue URL belongs to unexpected repository: {url}")
    return {"number": int(match.group(3)), "url": url}


def _with_body_file(arguments: list[str], body: str) -> str:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", suffix=".md", delete=False) as handle:
            handle.write(body)
            temporary_path = Path(handle.name)
        return _run([*arguments, "--body-file", str(temporary_path)])
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def _create_issue(
    plan: dict[str, Any],
    item: dict[str, Any],
    body: str,
    *,
    parent: int | None = None,
) -> dict[str, Any]:
    repository = plan["repository"]
    metadata = _metadata(plan, item)
    command = ["gh", "issue", "create", "-R", repository, "--title", item["title"]]
    if parent is not None:
        command.extend(["--parent", str(parent)])
    for label in metadata["labels"]:
        command.extend(["--label", label])
    for assignee in metadata["assignees"]:
        command.extend(["--assignee", assignee])
    if metadata["issue_type"]:
        command.extend(["--type", metadata["issue_type"]])
    if metadata["milestone"]:
        command.extend(["--milestone", metadata["milestone"]])
    output = _with_body_file(command, body)
    return _parse_issue_url(output, repository)


def _canonical_blocker_url(blocker: str | int, plan: dict[str, Any], state: dict[str, Any]) -> str:
    if isinstance(blocker, int):
        return f"https://github.com/{plan['repository']}/issues/{blocker}"
    internal = _state_issue(state, blocker)
    if internal:
        return internal["url"].rstrip("/")
    if ISSUE_URL_RE.fullmatch(blocker):
        return blocker.rstrip("/")
    raise PlanError(f"Cannot resolve blocker: {blocker}")


def _blocker_cli_ref(blocker: str | int, state: dict[str, Any]) -> str:
    if isinstance(blocker, int):
        return str(blocker)
    internal = _state_issue(state, blocker)
    if internal:
        return str(internal["number"])
    return blocker


def _view_issue(repository: str, number: int) -> dict[str, Any]:
    return _gh_json(
        [
            "issue",
            "view",
            str(number),
            "-R",
            repository,
            "--json",
            "number,title,url,state,parent,subIssues,subIssuesSummary,blockedBy,blocking,labels,issueType",
        ]
    )


def apply_plan(plan_path: Path, plan: dict[str, Any], state_path: Path, confirmation: str) -> dict[str, Any]:
    repository = plan["repository"]
    if confirmation != repository:
        raise PlanError(f"Refusing live creation: --confirm-repository must exactly equal {repository}")
    digest = plan_digest(plan_path)
    state = _load_state(state_path)
    if state:
        _check_state(state, plan, digest)
    else:
        state = {
            "version": 1,
            "repository": repository,
            "plan_key": plan["key"],
            "plan_sha256": digest,
            "epic": None,
            "issues": {},
            "dependencies": [],
            "completed": False,
        }

    preflight_result = preflight(plan)

    if not state.get("epic"):
        state["epic"] = _create_issue(plan, plan["epic"], render_epic(plan, state))
        _write_state(state_path, state)
    epic_number = int(state["epic"]["number"])

    for _, phase, issue in flatten_issues(plan):
        if issue["key"] in state["issues"]:
            continue
        created = _create_issue(plan, issue, render_child(plan, phase, issue, state), parent=epic_number)
        state["issues"][issue["key"]] = created
        _write_state(state_path, state)

    for _, _, issue in flatten_issues(plan):
        blockers = issue.get("blocked_by", [])
        if not blockers:
            continue
        child = state["issues"][issue["key"]]
        live = _view_issue(repository, int(child["number"]))
        actual_urls = {node["url"].rstrip("/") for node in live["blockedBy"]["nodes"]}
        missing = [
            blocker
            for blocker in blockers
            if _canonical_blocker_url(blocker, plan, state) not in actual_urls
        ]
        if missing:
            refs = ",".join(_blocker_cli_ref(blocker, state) for blocker in missing)
            _run(
                [
                    "gh",
                    "issue",
                    "edit",
                    str(child["number"]),
                    "-R",
                    repository,
                    "--add-blocked-by",
                    refs,
                ]
            )
        edge_key = f"{issue['key']}<-" + ",".join(str(blocker) for blocker in blockers)
        if edge_key not in state["dependencies"]:
            state["dependencies"].append(edge_key)
            _write_state(state_path, state)

    _with_body_file(
        ["gh", "issue", "edit", str(epic_number), "-R", repository],
        render_epic(plan, state),
    )
    for _, phase, issue in flatten_issues(plan):
        child = state["issues"][issue["key"]]
        _with_body_file(
            ["gh", "issue", "edit", str(child["number"]), "-R", repository],
            render_child(plan, phase, issue, state),
        )

    verification = verify_live(plan_path, plan, state_path)
    state["completed"] = True
    state["verification"] = verification
    _write_state(state_path, state)
    return {"preflight": preflight_result, "state_file": str(state_path), **verification}


def verify_live(plan_path: Path, plan: dict[str, Any], state_path: Path) -> dict[str, Any]:
    state = _load_state(state_path)
    if not state:
        raise PlanError(f"State file does not exist: {state_path}")
    _check_state(state, plan, plan_digest(plan_path))
    if not state.get("epic"):
        raise PlanError("State does not contain a created Epic")

    repository = plan["repository"]
    epic_number = int(state["epic"]["number"])
    epic_live = _view_issue(repository, epic_number)
    expected_children = {entry["url"].rstrip("/") for entry in state.get("issues", {}).values()}
    actual_children = {node["url"].rstrip("/") for node in epic_live["subIssues"]["nodes"]}
    missing_children = sorted(expected_children - actual_children)
    if missing_children:
        raise PlanError("Live Epic is missing native sub-issues: " + ", ".join(missing_children))

    issue_results: dict[str, Any] = {}
    for _, _, issue in flatten_issues(plan):
        child = state.get("issues", {}).get(issue["key"])
        if not child:
            raise PlanError(f"State is missing child issue: {issue['key']}")
        live = _view_issue(repository, int(child["number"]))
        parent = live.get("parent")
        if not parent or int(parent["number"]) != epic_number:
            raise PlanError(f"Child {issue['key']} is not a native sub-issue of #{epic_number}")
        if live.get("title") != issue["title"]:
            raise PlanError(f"Child {issue['key']} title drifted from the plan")
        expected_blockers = {
            _canonical_blocker_url(blocker, plan, state) for blocker in issue.get("blocked_by", [])
        }
        actual_blockers = {node["url"].rstrip("/") for node in live["blockedBy"]["nodes"]}
        missing_blockers = sorted(expected_blockers - actual_blockers)
        if missing_blockers:
            raise PlanError(f"Child {issue['key']} is missing blockers: {', '.join(missing_blockers)}")
        issue_results[issue["key"]] = {
            "number": live["number"],
            "url": live["url"],
            "state": live["state"],
            "blocked_by_count": len(actual_blockers),
        }

    return {
        "repository": repository,
        "epic": {"number": epic_live["number"], "url": epic_live["url"], "state": epic_live["state"]},
        "children_verified": len(issue_results),
        "issues": issue_results,
        "status": "verified",
    }


def default_state_path(plan_path: Path) -> Path:
    return plan_path.with_name(plan_path.name + ".state.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate plan structure and dependency graph")
    validate_parser.add_argument("plan", type=Path)

    render_parser = subparsers.add_parser("render", help="Render parent and child issue Markdown locally")
    render_parser.add_argument("plan", type=Path)
    render_parser.add_argument("--output-dir", type=Path, required=True)
    render_parser.add_argument("--state-file", type=Path)

    preflight_parser = subparsers.add_parser("preflight", help="Check GitHub prerequisites without changing issues")
    preflight_parser.add_argument("plan", type=Path)

    apply_parser = subparsers.add_parser("apply", help="Create or resume the live GitHub issue graph")
    apply_parser.add_argument("plan", type=Path)
    apply_parser.add_argument("--state-file", type=Path)
    apply_parser.add_argument("--confirm-repository", required=True)

    verify_parser = subparsers.add_parser("verify", help="Verify the live hierarchy and dependencies")
    verify_parser.add_argument("plan", type=Path)
    verify_parser.add_argument("--state-file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan_path = args.plan.resolve()
        plan = load_plan(plan_path)
        summary = validate_plan(plan)
        if args.command == "validate":
            result: dict[str, Any] = {"status": "valid", **summary}
        elif args.command == "render":
            state = _load_state(args.state_file.resolve()) if args.state_file else None
            write_rendered(plan, args.output_dir.resolve(), state)
            result = {"status": "rendered", "output_dir": str(args.output_dir.resolve()), **summary}
        elif args.command == "preflight":
            result = {"status": "ready", **summary, **preflight(plan)}
        elif args.command == "apply":
            state_path = (args.state_file or default_state_path(plan_path)).resolve()
            result = apply_plan(plan_path, plan, state_path, args.confirm_repository)
        elif args.command == "verify":
            state_path = (args.state_file or default_state_path(plan_path)).resolve()
            result = verify_live(plan_path, plan, state_path)
        else:  # pragma: no cover
            parser.error(f"Unknown command: {args.command}")
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except PlanError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
