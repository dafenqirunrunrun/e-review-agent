# V2 Java Agent-RAG Client Contract

## Scope

This document describes the first Java Agent-RAG client module for the
enterprise-maturity local single-node route. It covers DTOs, tenant resolution,
timeouts, finite retry, error mapping, response validation, response size
limits, and circuit breaker behavior. It does not add persistence tables or
business workflow APIs; those are handled by the next module.

## Java Package

```text
org.linlinjava.litemall.admin.service.agentrag
```

The client is placed in `litemall-admin-api` because existing AI HTTP calls
already live in that module and use `RestTemplate`.

## HTTP Implementation

```text
RestTemplate
SimpleClientHttpRequestFactory
```

No new HTTP stack is introduced.

## Request DTO

`AgentRagAnalyzeRequest` contains:

- `requestId`
- `tenantId`
- `subjectType`
- `subjectId`
- `query`
- `context`
- `runtimeMode`
- `schemaVersion`
- `retrieval`

`AgentRagRetrievalOptions` contains:

- `enabled`
- `topK`
- `rerankTopK`
- `requestedMode`
- `publicTenantEnabled`

Required fields:

```text
requestId
tenantId
subjectType
subjectId
query
schemaVersion
```

## Tenant Resolver

Java does not trust a frontend-provided tenant value. Before every analyze
request, `AgentRagTenantResolver` overwrites the request tenant with the current
trusted tenant.

Current local mode:

```text
agent-rag.single-tenant-id=__local__
```

This is a controlled single-tenant local default. Future multi-tenant deployment
must replace the resolver with a principal/org/store-aware implementation.

## Response DTO

`AgentRagAnalyzeResponse` parses:

- `requestId`
- `tenantId`
- `subjectId`
- `decision`
- `analysis`
- `retrieval`
- `runtime`
- `audit`

Unknown fields are ignored for forward compatibility. Required protocol fields
are still validated by the client after deserialization.

## Validation

The client rejects the full response when:

- `requestId` does not match.
- `tenantId` does not match.
- `subjectId` does not match.
- Required `decision`, `runtime`, or `audit` is missing.
- `schemaVersion` is missing from runtime.
- `riskLevel` is not `low`, `medium`, or `high`.
- `action` is not `none`, `create-risk-task`, `manual-review`, or
  `explicit-failure`.
- `confidence` is outside `0..1`.
- Any citation belongs to a tenant other than the current tenant or
  `__public__`.
- Citation count, snippet length, summary length, context size, or response
  size exceeds configured limits.

Cross-tenant citations reject the entire response; they are not silently
filtered.

## Timeouts And Retry

Configuration defaults:

```text
agent-rag.connect-timeout-ms=2000
agent-rag.read-timeout-ms=30000
agent-rag.total-timeout-ms=35000
agent-rag.max-retries=1
agent-rag.retry-backoff-ms=200
```

Retry is allowed only for transient transport/server failures:

```text
AGENT_RAG_CONNECT_TIMEOUT
AGENT_RAG_READ_TIMEOUT
AGENT_RAG_HTTP_5XX
```

Retry is not allowed for:

```text
AGENT_RAG_HTTP_4XX
AGENT_RAG_INVALID_JSON
AGENT_RAG_SCHEMA_MISMATCH
AGENT_RAG_TENANT_MISMATCH
AGENT_RAG_SUBJECT_MISMATCH
AGENT_RAG_RESPONSE_TOO_LARGE
```

Retries reuse the same request body and `requestId`.

## Error Codes

The client maps failures to:

```text
AGENT_RAG_CONNECT_TIMEOUT
AGENT_RAG_READ_TIMEOUT
AGENT_RAG_HTTP_4XX
AGENT_RAG_HTTP_5XX
AGENT_RAG_INVALID_JSON
AGENT_RAG_SCHEMA_MISMATCH
AGENT_RAG_TENANT_MISMATCH
AGENT_RAG_SUBJECT_MISMATCH
AGENT_RAG_RESPONSE_TOO_LARGE
AGENT_RAG_CIRCUIT_OPEN
AGENT_RAG_DISABLED
AGENT_RAG_UNKNOWN_ERROR
```

## Circuit Breaker

`AgentRagCircuitBreaker` is a lightweight in-process breaker with states:

```text
CLOSED
OPEN
HALF_OPEN
```

Defaults:

```text
failure-threshold=5
open-duration-ms=30000
half-open-max-calls=1
```

Failures counted:

- connection failure
- timeout
- HTTP 5xx
- invalid JSON
- schema mismatch
- response too large

Failures not counted:

- normal HTTP 4xx business rejection
- tenant mismatch
- user input validation

The breaker uses a small synchronized state transition section, but does not
hold a global lock around network I/O.

## Tests

Executed command:

```powershell
mvn -pl litemall-admin-api -am -Dtest=*AgentRag* -DfailIfNoTests=false test
```

Result:

```text
16 tests passed
```

Covered:

- request JSON shape
- trusted tenant propagation
- unknown response field compatibility
- requestId mismatch
- tenant mismatch
- citation tenant mismatch
- HTTP 400 no retry
- HTTP 500 single retry
- invalid JSON
- response size limit
- health parsing
- DTO round trip
- circuit open/half-open/close transitions
- non-counted business failures
- concurrent open-state rejection
