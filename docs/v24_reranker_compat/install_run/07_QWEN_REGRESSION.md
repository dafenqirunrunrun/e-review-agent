# Qwen Regression

## Result

Qwen real generation smoke passed under Transformers 4.51.3.

Key evidence from `real-llm-smoke-summary.json`:

- `fallbackUsed=false`
- `realGenerate=true`
- `schemaValid=true`
- `cudaUsed=true`
- `modelClass=Qwen3ForCausalLM`
- peak CUDA memory: 3326.15 MB
- duration: 21694 ms
- output tokens: 104
- tokens per second: 4.866

This validates that the Transformers 4.x compatibility stack does not break the local Qwen3-1.7B runtime smoke path.
