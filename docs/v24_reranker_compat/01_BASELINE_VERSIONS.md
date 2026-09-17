# Baseline Versions

Observed before attempted fix:

```text
FlagEmbedding=1.3.5
transformers=5.3.0
torch=2.5.1+cu121
sentence-transformers=3.0.1
accelerate=1.14.0
peft=0.19.1
tokenizers=0.22.2
safetensors=0.7.0
huggingface-hub=1.7.1
```

Observed after attempted fix:

```text
FlagEmbedding=1.3.5
transformers=5.3.0
torch=2.5.1+cu121
sentence-transformers=3.0.1
accelerate=1.14.0
peft=0.19.1
tokenizers=0.22.2
safetensors=0.7.0
huggingface-hub=1.7.1
```

`pip check` status:

```text
sentence-transformers 3.0.1 has requirement transformers<5.0.0,>=4.34.0, but you have transformers 5.3.0.
```

This pre-existing declared dependency mismatch was not changed in this stage.
