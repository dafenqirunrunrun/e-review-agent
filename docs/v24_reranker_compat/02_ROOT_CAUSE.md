# Root Cause

The formal real reranker runtime test fails before model scoring because importing `FlagEmbedding` triggers an incompatible import path:

```text
from transformers.utils.import_utils import is_torch_fx_available
ImportError: cannot import name 'is_torch_fx_available'
```

The stack goes through:

```text
FlagEmbedding.__init__
FlagEmbedding.inference.auto_reranker
FlagEmbedding.inference.reranker.decoder_only.layerwise
FlagEmbedding.inference.reranker.decoder_only.models.modeling_minicpm_reranker
```

The project does not need a monkey patch or deterministic fallback. The clean remediation path is to align `FlagEmbedding` with the installed Transformers runtime, starting with `FlagEmbedding==1.4.0 --no-deps`.

Evidence:

- `logs/baseline-failure.log`
- `test-results/baseline-failure.xml`
