# Dependency Change

Attempted change:

```text
FlagEmbedding==1.3.5 -> FlagEmbedding==1.4.0
```

Command:

```powershell
D:\anaconda\envs\ereview-v24-reranker-fix\python.exe -m pip install --upgrade --no-deps FlagEmbedding==1.4.0
```

Result: `BLOCKED`

Reason:

```text
TLS/SSL connection has been closed (EOF)
Could not fetch URL https://pypi.org/simple/flagembedding/
ERROR: No matching distribution found for FlagEmbedding==1.4.0
```

Local offline search found only cached `flagembedding-1.3.5-py3-none-any.whl`; no local `1.4.0` wheel was available.

Dependency diff after failed install is empty. The cloned environment remains unchanged.

Offline remediation command for next run:

```powershell
D:\anaconda\envs\ereview-v24-reranker-fix\python.exe -m pip install --no-index --no-deps D:\path\to\FlagEmbedding-1.4.0-py3-none-any.whl
```

Do not install or upgrade `torch`, `transformers`, `sentence-transformers`, `accelerate`, `peft`, `tokenizers`, or `safetensors` unless a separate change assessment is created.
