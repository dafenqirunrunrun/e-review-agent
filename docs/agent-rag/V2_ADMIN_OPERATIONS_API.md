# V2 Admin Operations API

## Overview

```text
GET /admin/agent-rag/overview
permission: admin:ai:review:list
query: from, to
```

Returns tenant-scoped counts, distributions, recent failures, pending reviews,
duration statistics, sample size, and sampled flag.

## Runs

```text
GET /admin/agent-rag/runs
permission: admin:ai:review:list
query: page, limit, subjectType, subjectId, requestId, status, riskLevel,
       providerImpl, fallbackUsed, requiresHumanReview, createdFrom, createdTo
```

Each item contains run identity, status, original decision, effective decision,
provider, retrieval, index, fallback, duration, override count, replay marker,
and timestamps.

## Detail and Evidence

```text
GET /admin/agent-rag/runs/{id}
GET /admin/agent-rag/runs/{id}/evidence
permission: admin:ai:review:list
```

Detail returns the run, evidence, override history, original decision, and
effective decision. Evidence remains bounded by backend policy.

## Override

```text
POST /admin/agent-rag/override
permission: admin:ai:review:analyze
body: runId, newRiskLevel, newAction, reason, operatorId
```

Override is append-only. It does not overwrite the original AI decision.

## Replay and Compare

```text
POST /admin/agent-rag/runs/{id}/replay
GET /admin/agent-rag/runs/{id}/compare/{otherRunId}
permission: admin:ai:review:analyze for replay, admin:ai:review:list for compare
```

Replay creates a new run. Compare returns deltas for risk, action, confidence,
provider, index version, fallback, duration, status, and citation add/remove
arrays.

## Runtime Health

```text
GET /admin/agent-rag/health
permission: admin:ai:review:list
```

Returns runtime status and circuit-breaker snapshot.
