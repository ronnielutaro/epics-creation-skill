# Epic decomposition and evidence guide

Use this guide when the initiative crosses several layers or the right issue boundaries are not obvious.

## Start from invariants

Write the primary invariant as a falsifiable statement about user-visible and authoritative state. Good invariants connect an action to a durable result or explicit failure. Avoid goals such as “improve,” “support,” or “complete implementation” without a measurable meaning.

Separate these layers when they have different owners or evidence:

- product behavior and lifecycle;
- application use case or orchestration;
- API/generated contract;
- persistence, identity, and transactions;
- projections, search, cache, or downstream freshness;
- UI behavior and failure state;
- operational migration/backfill;
- independent integrated certification.

Do not split solely by frontend/backend if doing so creates two children that cannot deliver or verify any outcome independently.

## Choose phases by risk retirement

Useful phase shapes include:

1. containment or baseline evidence;
2. canonical contract and decisions;
3. core implementation and data integrity;
4. downstream integration and operations;
5. independent release certification.

Not every Epic needs all five. Every phase does need a checkpoint that changes what is safe to start or claim next.

## Build the dependency graph

For each child, ask: “Would starting or completing this be unsafe or invalid if the proposed blocker were unfinished?” Add an edge only when the answer is yes.

Common valid edges:

- UI payload work blocked by the canonical API contract;
- aggregate transactions blocked by stable identity semantics;
- a backfill blocked by prevention fixes and an approved repair design;
- downstream projection work blocked by committed domain events;
- final certification blocked by every implementation and approved repair it must exercise.

Common invalid edges:

- two children happen to be in numbered order;
- the same person will implement both;
- both touch a shared module but have stable contracts;
- one issue would be convenient to finish first.

## Child issue contract

An implementation-ready child answers:

- What observable outcome becomes true?
- What evidence or defect makes this necessary?
- What is included and explicitly excluded?
- Which authoritative state and identities must be preserved?
- What negative, retry, concurrency, authorization, or failure paths matter?
- Which tests and real-system oracles are required?
- What artifacts and exact results must be posted before closure?
- What decision or issue blocks it?

Acceptance criteria state outcomes. “Add an endpoint,” “write tests,” or “update docs” belong in scope or delivery requirements unless their observable contract is also stated.

## Parent contract

The parent should make the program understandable without duplicating each child body. It owns:

- the objective and primary invariant;
- locked product, data, security, or governance decisions;
- the audit/baseline context and confidence limits;
- in/out scope;
- roadmap and phase checkpoints;
- dependency order and safe parallelism;
- shared delivery and evidence rules;
- integrated exit criteria;
- the explicit completion/approval policy.

Every exit criterion must map to at least one child acceptance criterion, the certification matrix, or an explicit owner approval.

## Evidence strength

Match evidence to the claim:

- persistence claim: database oracle plus API readback;
- contract claim: generated-client drift check and value-level request/response tests;
- UI claim: real browser journey plus authoritative backend state;
- authorization claim: allowed and denied raw API paths;
- transaction/idempotency claim: injected failure, retry, concurrency, and durable-state checks;
- projection/freshness claim: committed source version traced to serving representation;
- performance claim: reproducible percentile measurements under a declared load and build;
- migration/backfill claim: approved dry run, counts, reconciliation, rollback/recovery evidence;
- integrated release claim: exact-head end-to-end evidence across every authoritative boundary.

Mocks and unit tests are useful but cannot prove behavior outside their boundary. Make that distinction in both child verification and Epic closure policy.
