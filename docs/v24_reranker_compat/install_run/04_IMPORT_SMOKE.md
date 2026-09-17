# Import Smoke

Independent import smoke passed after installation:

- `transformers.__version__ == 4.51.3`
- `torch.__version__ == 2.5.1+cu121`
- CUDA available: true
- `is_torch_fx_available` import: PASS
- `Qwen3ForCausalLM` import: PASS
- `FlagReranker` import: PASS

Evidence:

- `import-smoke.log`
- `import-smoke-exit.txt`
