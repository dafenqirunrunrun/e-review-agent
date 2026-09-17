# V2 Admin Operations Manual Acceptance

Manual visual acceptance was not executed in this phase.

```text
MANUAL_VISUAL_ACCEPTANCE_NOT_EXECUTED
```

## Checklist

- `/agent-rag/overview` is visible in the sidebar.
- Overview metrics load or show a clear error.
- Recent failures and pending review tables have empty states.
- `/agent-rag/runs` supports quick filters, advanced filters, pagination, and
  table actions.
- Risk tags show both text and color.
- Fallback shows requested/effective Provider and reason.
- `/agent-rag/runs/:id` shows original decision, effective decision, runtime
  metadata, bounded evidence timeline, override history, and replay comparison.
- Override dialog validates required reason length.
- Replay asks for confirmation and opens the new run.
- `/agent-rag/runtime` shows runtime, Provider, Index, and Circuit Breaker.
- Auto-refresh can be enabled and is cleaned up when leaving the page.
- No prompt, local model path, token, password, or full unbounded evidence is
  displayed.
