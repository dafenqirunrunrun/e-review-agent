# V2 Admin Operations UX

## Goals

The operations center is designed for administrators who need to inspect
Agent-RAG decisions, understand why a fallback happened, append human review,
and compare replay results without reading backend logs.

## Display Rules

- High or critical risk uses `danger`.
- Medium risk uses `warning`.
- Low or none uses `success`.
- Unknown values use `info`.
- Original and effective risk are displayed separately.
- When an override exists, the UI marks the effective decision as human review.

## Runtime Language

- `Ready`: runtime ready, index compatible, circuit closed, no provider
  degradation.
- `Degraded`: runtime reachable but fallback, provider degradation, or circuit
  warning exists.
- `Not Ready`: runtime state cannot be confirmed.

## Runtime Observability Page

The runtime page now presents a screenshot-friendly operational view:

- Overall readiness.
- Request, success, failure, fallback, and idempotency-hit counters.
- Latency p95 and sample count.
- Provider implementation and conformance.
- Active index version, load state, and compatibility.
- Circuit Breaker state and next probe time.
- Optional refresh intervals of paused, 15 seconds, 30 seconds, or 60 seconds.

Auto refresh pauses when the browser tab is hidden.

## Evidence Experience

Evidence is shown as a bounded timeline: request context, retrieval/citations,
analysis summary, runtime metadata, and audit trail. The UI renders plain text
with `pre`, not `v-html`.

## Error, Loading and Empty States

Each page has explicit loading states, error alerts, and friendly empty states.
Override and replay use separate submitting flags to avoid duplicate actions.

## Manual Visual Acceptance

Manual browser screenshot acceptance has not been executed in this phase:

```text
MANUAL_VISUAL_ACCEPTANCE_NOT_EXECUTED
```
