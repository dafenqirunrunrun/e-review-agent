# v1.8.0 Governed Agent Hardening

Status: `V180_GOVERNED_AGENT_HARDENING_PASS`

## Implemented Controls

- Prompt-injection input now stops retrieval and model decision execution.
- Blocked input is routed to human review with `PROMPT_INJECTION`.
- Tool audit records only safe metadata: tool name, status, risk level, tenant scope, and audit policy.
- Tool calls are blocked when tool timeout exceeds runtime policy.
- Tool registration rejects unsafe contracts: non-read-only risk, optional tenant scope, raw audit policy, unsafe output sanitizer, non-idempotent tools, broad retry policy, and unbounded timeout.
- SQLite idempotency store restart behavior is verified.

## Test Evidence

Command:

```powershell
D:\anaconda\envs\torchtest\python.exe -m pytest ai-service\tests\test_v180_governed_agent_hardening.py ai-service\tests\test_v170_agent_platform_api.py ai-service\tests\test_v170_enterprise_eval_scripts.py
```

Result: `20 passed in 3.15s`

## Boundary

This phase does not add business actions, does not train models, does not access closed holdouts, and does not change API contracts. It hardens the local governed Agent path and preserves v1.7 compatibility tests.
