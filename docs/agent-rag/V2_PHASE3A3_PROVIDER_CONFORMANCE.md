# Agent-RAG Phase 3A.3 Provider Conformance

## Provider Contract

All dense providers keep the common protocol:

```text
embed_documents(texts)
embed_query(text)
health()
metadata()
close()
```

Implemented provider classes:

- `HashEmbeddingProvider`
- `BgeM3EmbeddingProvider` as Legacy CLS
- `OfficialBgeM3FlagProvider`
- `SentenceTransformerBgeM3Provider`
- `DisabledEmbeddingProvider`

## Legacy CLS

Legacy CLS remains available for historical reproducibility and fallback.

Metadata:

```text
providerType=bge-m3-legacy-cls
providerImpl=legacy-cls
providerConformance=legacy-experimental
library=transformers
encodeMethod=AutoModel.last_hidden_state[:,0]
pooling=cls-token
```

This path is numerically stable but is not equivalent to the official BGE-M3
retrieval encode path.

## Official FlagEmbedding

`OfficialBgeM3FlagProvider` is implemented to use:

```text
from FlagEmbedding import BGEM3FlagModel
BGEM3FlagModel.encode(..., return_dense=True, return_sparse=False, return_colbert_vecs=False)
dense_vecs
```

The implementation forbids remote download by only accepting a local model path
from `RAG_BGE_M3_MODEL_PATH`. It does not use `last_hidden_state[:,0]`.

Current runtime status:

```text
PROVIDER_DEPENDENCY_MISSING:FlagEmbedding
```

## Sentence Transformers Reference

`SentenceTransformerBgeM3Provider` is implemented as a reference provider using
local-only `SentenceTransformer.encode`. It is not selected as the default.

Current runtime status:

```text
PROVIDER_DEPENDENCY_MISSING:sentence-transformers
```

## Fingerprints

Provider metadata now separates:

- `assetFingerprint`
- `providerFingerprint`
- `effectiveEmbeddingFingerprint`

`assetFingerprint` excludes absolute local paths and user names. It is based on
model config/tokenizer hashes and weight file names, sizes and sampled hashes.

`providerFingerprint` includes implementation, library, encode method, pooling,
max length, normalization, dtype and dimension.

`effectiveEmbeddingFingerprint` is derived from asset and provider fingerprints.
The same model asset with Legacy CLS, FlagEmbedding and Sentence Transformers
must produce different effective fingerprints.

## Index Compatibility

FAISS manifests now store:

- `assetFingerprint`
- `providerFingerprint`
- `effectiveEmbeddingFingerprint`
- `providerImpl`
- `providerConformance`

Index activation rejects mismatched `providerImpl` or
`effectiveEmbeddingFingerprint`.

## Fallback

Fallback must report the actual effective provider. A failed FlagEmbedding load
must not return `effectiveProviderImpl=flagembedding`.

## Phase 3A.3.2 Conformance Result

The official FlagEmbedding provider now conforms to the provider contract under
the isolated `torchtest-phase3a3-tf4` validation environment.

Verified behavior:

- `FlagEmbedding` imports successfully.
- `BGEM3FlagModel` loads the local BGE-M3 asset in offline mode.
- `BGEM3FlagModel.encode(...).dense_vecs` executes for query and document
  batches.
- Output vectors are 1024-dimensional, finite, stable for repeated input, and
  normalized when `RAG_BGE_M3_NORMALIZE=true`.
- Provider metadata includes `providerImpl=flagembedding`,
  `providerConformance=official-library`, and distinct provider/index
  fingerprints.
- Index activation rejects mismatched provider/index fingerprints.

The Sentence Transformers reference path remains implemented but is not selected
as default because the available local BGE-M3 asset does not load as a Sentence
Transformers model directory.
