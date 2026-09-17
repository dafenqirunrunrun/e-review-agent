# V2 Java Integration Audit

## Scope

This audit covers the current Java to Python AI/RAG integration before adding a
durable Agent-RAG business workflow. It is an audit-only step: no Java API,
database schema, or business behavior is changed by this document.

## Existing Java To Python Entrypoints

`AiReviewService` is the main Java client for the FastAPI service.

Current operations:

- `analyze` -> `POST /api/v1/review/analyze`
- `frameworkStatus` -> `GET /api/v1/agent-framework/status`
- `ragV2Status` -> `GET /api/v1/rag-v2/status`
- `ragV2Search` -> `POST /api/v1/rag-v2/search`
- `ragV2Evaluate` -> `POST /api/v1/rag-v2/evaluate`
- `ragV2Report` -> `GET /api/v1/rag-v2/report`
- `enterpriseHealth` -> `GET /api/v1/e-review/health`
- `enterpriseRuntimeStatus` -> `GET /api/v1/e-review/runtime-status`
- `enterpriseMetrics` -> `GET /api/v1/e-review/metrics`
- `enterpriseAnalyze` -> `POST /api/v1/e-review/analyze`
- `enterpriseAnalyzeRag` -> `POST /api/v1/e-review/analyze/rag`

The current code uses `RestTemplate` with `SimpleClientHttpRequestFactory`.
There is no `WebClient` usage.

## Existing DTOs

The stable review-analysis DTOs are:

- `AiReviewAnalyzeRequest`
- `AiReviewAnalyzeResponse`

They support the existing comment-governance workflow, including review text,
product metadata, rating, image URL list, scores, evidence, similar cases,
agent suggestion, workflow trace, LLM observability, and RAG observability.

Current gaps for Agent-RAG v2:

- No dedicated Java `AgentRagAnalyzeRequest`.
- No dedicated Java `AgentRagAnalyzeResponse`.
- No first-class `requestId` field in the Java AI review request.
- No first-class `tenantId` field in the Java AI review request.
- No first-class `schemaVersion`, `runtimeMode`, or bounded retrieval options in
  the Java AI review request.

## Existing Timeouts And Errors

`AiReviewService` has:

```text
ai.service.connect-timeout: 3000 ms
ai.service.read-timeout: 10000 ms
```

Current behavior:

- Each operation creates a new `RestTemplate`.
- `RestClientException` is mapped to `AiReviewServiceException`.
- Admin controller returns `502` for temporary AI service failures.

Current gaps:

- No total request timeout.
- No bounded retry policy.
- No explicit idempotent-only retry rule.
- No local Java circuit breaker.
- No typed error mapping for timeout, unavailable, invalid schema, tenant
  rejection, no evidence, or fallback-required states.

## Existing Business Flow

Manual analysis flow:

```text
AdminAiReviewController.analyze
-> AiReviewService.analyze
-> litemall_review_ai_analysis
-> AiRiskTaskService.createTasksForAnalysis
```

Patrol flow:

```text
AiReviewPatrolService.runOnce
-> scan demo_review and litemall_comment
-> AgentPlatformService.startRun
-> AiReviewService.analyze
-> litemall_review_ai_analysis
-> AiRiskTaskService.createTasksForAnalysis
-> AgentPlatformService.finishRun
```

Replay flow:

```text
AgentPlatformService.replay
-> build AiReviewAnalyzeRequest from persisted analysis
-> start a new replay run
-> AiReviewService.analyze
-> save replay comparison
```

Human feedback flow:

```text
AgentPlatformService.createFeedback
-> litemall_ai_agent_feedback
```

This means the project already has a useful product loop, but it is not yet the
durable Agent-RAG v2 workflow requested by this maturity route.

## Existing Database Tables

Current tables involved in the Java AI governance loop:

- `litemall_review_ai_analysis`
- `litemall_ai_review_risk_task`
- `litemall_ai_agent_run`
- `litemall_ai_agent_step`
- `litemall_ai_agent_tool_call`
- `litemall_ai_agent_feedback`
- `litemall_ai_agent_replay_compare`
- `litemall_ai_patrol_log`
- `litemall_ai_case_knowledge`
- `litemall_ai_case_retrieval_log`

The proposed Agent-RAG v2 durable tables are not yet implemented:

- `agent_rag_run`
- `agent_rag_evidence`
- `agent_rag_override`

## Idempotency

Current idempotency behavior:

- Manual review analysis checks `reviewAiAnalysisService.findBySource`.
- Patrol skips `litemall_comment` rows that already have analysis for
  `source_type='litemall_comment'` and the same `source_id`.
- Risk task creation checks `findByAnalysisAndType`.
- Replay creates a separate run and does not overwrite the original run.

Current gaps:

- No database unique key is audited here for Agent-RAG run idempotency.
- No unique Agent-RAG key over tenant, subject type, subject ID, analyzer
  version, and index version.
- No duplicate-key handling path for concurrent Agent-RAG requests.

## Evidence Persistence

Current evidence behavior:

- `litemall_review_ai_analysis.evidence_json` stores analysis evidence.
- `similar_cases_json`, `agent_suggestion_json`, and `workflow_trace_json`
  preserve additional bounded observability.
- `litemall_ai_agent_step` and `litemall_ai_agent_tool_call` store step and tool
  traces.

Current gaps:

- No dedicated Agent-RAG evidence bundle table.
- No bundle hash or previous bundle hash.
- No explicit source commit, analyzer version, prompt version, provider
  fingerprint, or index version in a Java Agent-RAG run record.
- Existing evidence is useful for demo/audit, but not yet a strict replayable
  Agent-RAG evidence bundle.

## Tenant State

Current Java AI review flow does not expose a first-class `tenantId` in the AI
review request DTO. Existing product data mostly flows from the single local
litemall database. Python Agent-RAG internals enforce tenant-aware retrieval,
but Java does not yet provide a uniform tenant contract for Agent-RAG calls.

Required next step:

```text
Every Java Agent-RAG request must include tenantId, and every admin API for
runs, evidence, replay, and override must validate tenant scope server-side.
```

## Risk Task Creation

`AiRiskTaskService.createTasksForAnalysis` creates risk tasks from persisted AI
analysis. It already avoids duplicate tasks by `analysisId` and `riskType`.

Current limitation:

- Duplicate prevention is tied to analysis records, not a future
  `agent_rag_run` unique identity.

## Replay And Override

Replay exists through `AgentPlatformService.replay` and creates a new replay
run. Human feedback exists through `AgentPlatformService.createFeedback`.

Current gaps:

- There is no dedicated Agent-RAG override table.
- Override is feedback-oriented and does not yet record previous/new risk level
  and previous/new action in the proposed Agent-RAG schema.

## Recommended Minimal Phase 2 Implementation

1. Add Java DTOs for Agent-RAG request, response, health, replay, and override.
2. Add `AgentRagClient` with `analyze`, `health`, and `replay`.
3. Add explicit connect/read/total timeout and max retry configuration.
4. Add a small local circuit breaker with `CLOSED`, `OPEN`, and `HALF_OPEN`.
5. Add `agent_rag_run`, `agent_rag_evidence`, and `agent_rag_override` SQL and
   Java persistence services.
6. Use database uniqueness for idempotency; do not rely on in-memory maps.
7. Add admin endpoints under `/admin/agent-rag/*`.
8. Add targeted Java tests for DTO serialization, timeout mapping, circuit
   breaker state, idempotency, evidence persistence, override, replay, and tenant
   rejection.

## Audit Conclusion

```text
AGENT_RAG_JAVA_INTEGRATION_AUDIT_COMPLETE
AGENT_RAG_JAVA_CLIENT_NOT_YET_IMPLEMENTED
AGENT_RAG_DURABLE_RUN_TABLE_NOT_YET_IMPLEMENTED
AGENT_RAG_JAVA_TENANT_CONTRACT_NOT_YET_IMPLEMENTED
```
