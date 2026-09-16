# Epic plan format

Author the plan as UTF-8 JSON. The tool deliberately uses a small explicit schema so dependency mistakes are caught before GitHub is changed.

## Top-level fields

- `key`: Stable lowercase identifier for plan markers and resume checks.
- `repository`: Exact `OWNER/REPO` target.
- `defaults` (optional): `labels`, `assignees`, and `issue_type` inherited by every issue.
- `epic`: Parent contract and metadata.
- `phases`: Ordered phase definitions containing child issues.

The parent `epic` requires:

- `title`, normally beginning with `Epic:` when that matches repository convention.
- `objective` and `primary_invariant`.
- `in_scope`, `out_of_scope`, `exit_criteria`, and `completion_policy`.
- `labels` should include the repository's Epic label when labels are the local convention.

Optional parent fields are `context`, `decisions`, `delivery_rules`, `verification_doctrine`, `assignees`, `issue_type`, and `milestone`.

Each phase requires `key`, `title`, `purpose`, `checkpoint`, and `issues`.

Each child requires:

- `key`: Stable and unique within the plan.
- `title`: Prefer a phase-aware form such as `Payments 2.1: Make capture idempotent`.
- `outcome`.
- `in_scope` and `out_of_scope`.
- `acceptance_criteria`: Observable, checkable results.
- `verification`: Tests and authoritative oracles required before closure.
- `closure_evidence`: Exact evidence to post on the issue or PR.

Optional child fields are `problem`, `implementation_constraints`, `delivery_requirements`, `completion_rule`, `labels`, `assignees`, `issue_type`, and `milestone`.

## Dependencies

Add `blocked_by` to a child. A blocker may be:

- another child `key` in this plan;
- an existing issue number in the same repository; or
- a full GitHub issue URL.

Internal blockers must be in the same or an earlier phase. Omit dependency edges between work that is safely parallel.

```json
{
  "key": "checkout-reliability",
  "repository": "acme/storefront",
  "defaults": {
    "labels": ["mvp-critical"],
    "assignees": ["@me"]
  },
  "epic": {
    "title": "Epic: Checkout Reliability and Release Safety",
    "objective": "Make checkout complete exactly once or fail visibly without corrupting financial state.",
    "primary_invariant": "Every accepted checkout has one authoritative order and one reconcilable payment outcome.",
    "context": ["Current retries can create ambiguous payment outcomes."],
    "decisions": [
      {
        "title": "Financial authority",
        "points": ["The ledger and provider reconciliation record are authoritative; UI state is not."]
      }
    ],
    "in_scope": ["Checkout orchestration", "Payment reconciliation"],
    "out_of_scope": ["Unrelated catalog redesign"],
    "labels": ["Epic"],
    "delivery_rules": ["One focused pull request per child unless explicitly approved."],
    "verification_doctrine": ["Use controlled provider fixtures and database oracles."],
    "exit_criteria": ["The final certification child passes with linked evidence."],
    "completion_policy": "Do not close automatically after the final implementation merge; require accepted certification evidence."
  },
  "phases": [
    {
      "key": "phase-0",
      "title": "Phase 0: Establish the contract",
      "purpose": "Lock financial state ownership before changing orchestration.",
      "checkpoint": ["The state machine and retry semantics are approved."],
      "issues": [
        {
          "key": "contract",
          "title": "Checkout 0.1: Define authoritative payment state and retry semantics",
          "outcome": "Create one executable contract for order and payment transitions.",
          "problem": ["Current components disagree about terminal payment states."],
          "in_scope": ["State ownership", "Idempotency keys"],
          "out_of_scope": ["Provider migration"],
          "acceptance_criteria": ["Every transition has one owner and documented retry behavior."],
          "verification": ["Contract tests cover success, decline, timeout, and replay."],
          "closure_evidence": ["Link the state table and exact test results."],
          "labels": ["backend"]
        }
      ]
    },
    {
      "key": "phase-1",
      "title": "Phase 1: Implement and certify",
      "purpose": "Implement the contract, then independently exercise the integrated path.",
      "checkpoint": ["No test produces duplicate or ambiguous financial state."],
      "issues": [
        {
          "key": "implementation",
          "title": "Checkout 1.1: Make payment capture idempotent and recoverable",
          "outcome": "Apply the approved contract to the runtime path.",
          "in_scope": ["Capture orchestration", "Recovery"],
          "out_of_scope": ["New payment methods"],
          "acceptance_criteria": ["Replaying a request does not duplicate capture."],
          "verification": ["Database and provider-shaped integration tests pass."],
          "closure_evidence": ["Post database-oracle snapshots and exact commands."],
          "blocked_by": ["contract"]
        },
        {
          "key": "certification",
          "title": "Checkout 1.2: Certify the end-to-end checkout release gate",
          "outcome": "Independently prove the complete checkout invariant.",
          "in_scope": ["Integrated happy, negative, retry, and failure paths"],
          "out_of_scope": ["Implementation refactors"],
          "acceptance_criteria": ["The complete matrix passes against authoritative state."],
          "verification": ["Exercise the real UI, API, database, and controlled provider boundary."],
          "closure_evidence": ["Attach traces, redacted requests, database evidence, and residual risks."],
          "blocked_by": ["implementation"],
          "completion_rule": "Keep the Epic open until this evidence is independently accepted."
        }
      ]
    }
  ]
}
```

## Commands

```powershell
python scripts/epic_tool.py validate epic-plan.json
python scripts/epic_tool.py render epic-plan.json --output-dir preview
python scripts/epic_tool.py preflight epic-plan.json
python scripts/epic_tool.py apply epic-plan.json --confirm-repository acme/storefront
python scripts/epic_tool.py verify epic-plan.json
```

`preflight` is read-only. It checks GitHub authentication, repository access, CLI relationship support, labels, assignees, milestones, and issue types. `apply` repeats that check before it creates anything. Live creation is not transactional. The state file is written after each successful issue creation so a normal interruption can resume safely; inspect GitHub manually after an uncertain network failure.

Do not edit the plan or discard its state file during a partial apply. The tool stops on a plan digest mismatch because starting with a fresh state file could duplicate issues. Restore the original plan first, or manually reconcile the intended plan, live issues, and saved state before resuming.
