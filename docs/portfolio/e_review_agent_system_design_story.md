# System Design Story

The system evolved from a review analysis demo into a governed local platform. The key design choice was to separate decision generation from governance: retrieval provides traceable evidence, the Agent controls workflow and tools, the provider factory selects Base or Adapter, and policy modules decide when humans must review.

This keeps the platform understandable during a demo: every request has a trace, every retrieved document has a source hash, every risky action routes to humans, and every adapter failure rolls back to Base.
