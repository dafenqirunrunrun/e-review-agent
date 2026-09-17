# Governed Agent Design

```mermaid
stateDiagram-v2
  [*] --> input_guard
  input_guard --> intent_router
  intent_router --> query_planner
  query_planner --> retrieve
  retrieve --> rerank
  rerank --> verify_evidence
  verify_evidence --> decide
  decide --> policy_guard
  policy_guard --> human_review_router
  human_review_router --> response_assembler
  response_assembler --> audit_sink
  audit_sink --> [*]
```

The Agent is bounded by configured maximum steps and tool calls. It cannot execute shell, Python, network fetches, or business write actions. Registered tools are read-only or human-review routing tools.
