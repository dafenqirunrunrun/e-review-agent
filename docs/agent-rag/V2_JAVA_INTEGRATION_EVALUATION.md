# V2 Java Integration Evaluation

## Evaluation Goal

Validate that the Java backend can call the local Agent-RAG runtime through a
governed HTTP boundary and persist auditable business workflow evidence.

## Result

```text
status: PASS
caseCount: 13
passed: 13
failed: 0
```

## Covered Capabilities

- Admin Agent-RAG health endpoint.
- Governed Java-to-FastAPI analyze call.
- Trusted tenant overwrite on the Java side.
- Durable run persistence.
- Durable bounded evidence persistence.
- Idempotency for repeated and concurrent requests.
- Append-only human override.
- Original/effective decision separation.
- Replay with new run lineage.
- AI unavailable behavior.
- Circuit breaker open and recovery.
- Database duplicate checks.

## Runtime Evidence

```text
tenantViolations: 0
duplicateRuns: 0
duplicateEvidence: 0
duplicateRiskTasks: 0
overridePreservedOriginal: true
replayCreatedNewRun: true
circuitBreakerOpened: true
circuitBreakerRecovered: true
```

## Test Evidence

```text
pip check: PASS
Python pytest: 464 passed, 11 skipped
Python real_dense marker: 1 passed, 7 skipped, 467 deselected
Java Agent-RAG targeted tests: 20 passed
Maven package: BUILD SUCCESS
Java workflow gate: JAVA_AGENT_RAG_WORKFLOW_GATE_PASS
Aggregate gate: AGENT_RAG_JAVA_WORKFLOW_RUNTIME_PASS
```

## Full Maven Test Boundary

The full Maven test command failed in `litemall-core` on legacy tests unrelated
to Agent-RAG:

```text
AliyunStorageTest.test
QiniuStorageTest.test
TencentStorageTest.test
BCryptTest.initializationError
```

The storage tests depend on third-party object-storage resources or missing
test resources. `BCryptTest` fails due PowerMock/Objenesis access behavior on
the current JDK. These were recorded as existing project test debt, not hidden
or bypassed.

## Remaining Non-Claims

```text
PRODUCTION_HIGH_AVAILABILITY_NOT_VERIFIED
PRODUCTION_CONCURRENCY_NOT_VERIFIED
MODEL_RERANKER_NOT_VERIFIED
REAL_LLM_QUALITY_NOT_VERIFIED
NO_PUSH
NO_TAG
NO_RELEASE
```
