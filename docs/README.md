# Design documentation

This directory explains how the GitHub Epic Creation skill works as a system, why its safety boundaries exist, and how data moves from a product-planning request to a verified GitHub issue graph.

## Documents

- [System architecture](architecture.md) — components, trust boundaries, sources of truth, and failure model.
- [Data flow](data-flow.md) — command paths, live-creation sequence, state transitions, and recovery behavior.
- [ADR-0001: Separate planning from resumable live mutation](decisions/0001-separate-planning-from-live-mutation.md) — the architectural decision behind the tool's safety model.

## Documentation boundary

These documents describe system structure and rationale. The canonical plan schema and command contract remain in [the plan format reference](../references/plan-format.md), while decomposition and evidence guidance remain in [the Epic quality reference](../references/epic-quality.md).
