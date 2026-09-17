# v2.1 Local Capacity Qualification

## Scope

This module records local single-node qualification observations only. It does
not claim production SLA, high availability, or production concurrency.

## Runner

Added:

```text
ai-service/scripts/qualification/run_local_capacity_qualification.py
```

The workload is synthetic and deterministic. It does not call real customer
data, real payment/logistics paths, or real model inference.

## Concurrency Matrix

| Concurrency | Measured | Throughput/s | P50 ms | P95 ms | P99 ms | Unhandled errors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100 | 64.538464 | 15.3581 | 16.0570 | 16.3189 | 0 |
| 2 | 100 | 128.860217 | 15.44435 | 16.1211 | 16.3623 | 0 |
| 4 | 100 | 255.270702 | 15.55695 | 16.4795 | 16.6564 | 0 |
| 8 | 100 | 490.789115 | 15.5221 | 16.1548 | 16.4147 | 0 |
| 16 | 100 | 911.189129 | 15.4683 | 16.0249 | 16.0737 | 0 |

## 30-Minute Soak

- Requested duration: 1800 seconds
- Observed duration: 1800.009 seconds
- Completed synthetic requests: 463232
- P95 latency: 15.9718 ms
- Unhandled errors: 0
- 30-minute soak pass: true

## Safety Checks

- Tenant violations: 0
- Duplicate runs: 0
- Duplicate evidence: 0
- Duplicate risk tasks: 0
- Semaphore leaks: 0
- Index lease leaks: 0
- Unhandled errors: 0

## Tokens

```text
LOCAL_QUALIFICATION_CAPACITY_OBSERVED
E_REVIEW_V21_30_MINUTE_SOAK_PASS
```

## Boundary

This result is a local synthetic capacity observation. It does not remove:

```text
PRODUCTION_CONCURRENCY_NOT_VERIFIED
HIGH_AVAILABILITY_NOT_VERIFIED
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
```
