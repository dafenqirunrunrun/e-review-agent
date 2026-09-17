# V2.3 BGE-M3 Sparse Environment

Decision: `BGE_M3_SPARSE_ENVIRONMENT_BLOCKED`

The sparse runtime can execute with a compatibility shim, but Phase 9.4 environment qualification requires `pip check` to pass. Because the current environment keeps `transformers==5.3.0` and the offline `sentence-transformers==3.0.1` metadata requires `<5.0.0`, the gate remains blocked without downgrading core dependencies.

Resume-ready note: restored real BGE-M3 sparse execution from an offline verified wheelhouse, found a library metadata/runtime compatibility conflict, and blocked the three-way retrieval experiment instead of silently downgrading core model dependencies.

```json
{
  "bgeM3ModelClassAvailable": true,
  "checks": {
    "bgeM3ModelClassAvailable": true,
    "cudaAvailable": true,
    "denseProviderImportPass": true,
    "flagEmbeddingImportPass": true,
    "llmProviderImportPass": true,
    "noTlsBypass": true,
    "noUnverifiedLocalPackage": true,
    "pipCheckPass": false
  },
  "cudaAvailable": true,
  "cudaVersion": "12.1",
  "decision": "BGE_M3_SPARSE_ENVIRONMENT_BLOCKED",
  "denseProviderImportPass": true,
  "dependencyFingerprint": "5eff793abb20d00fded57c982e858c00e43637e88f8aa82d8e57b61a2d603a33",
  "environmentSource": "OFFLINE_VERIFIED_WHEELHOUSE",
  "externalManifestLabel": "<external-models>/v2.3/manifests/v23-bge-m3-sparse-python-environment.json",
  "flagEmbeddingImportPass": true,
  "flagEmbeddingVersion": "1.3.5",
  "llmProviderImportPass": true,
  "model": {
    "assetFingerprint": "a36441812a43bc60e2464af3cc3ffc4d466fc2dc9a52d921264b0109c39094a2",
    "modelId": "BAAI/bge-m3",
    "modelPathLabel": "<external-models>/bge-m3",
    "revision": "external-existing"
  },
  "noTlsBypass": true,
  "noUnverifiedLocalPackage": true,
  "packageVersions": {
    "FlagEmbedding": "1.3.5",
    "datasets": "5.0.0",
    "peft": "0.19.1",
    "protobuf": "7.35.1",
    "safetensors": "0.7.0",
    "sentence_transformers": "3.0.1",
    "sentencepiece": "0.2.2",
    "tokenizers": "0.22.2",
    "torch": "2.5.1+cu121",
    "transformers": "5.3.0"
  },
  "pipCheckOutputHash": "9d29acf16f4c92e7c99bde57e07364a4971fb555d4c7a4b0cdfcc3d8de8667ce",
  "pipCheckPass": false,
  "pipCheckSummary": [
    "sentence-transformers 3.0.1 has requirement transformers<5.0.0,>=4.34.0, but you have transformers 5.3.0."
  ],
  "pythonVersion": "3.10.0",
  "runtimeProbe": {
    "averageNonZeroDimensions": 9.333333,
    "bgeM3ModelClassAvailable": true,
    "compatibilityShimUsed": true,
    "cudaUsed": true,
    "deterministicRepeat": true,
    "errorClass": "",
    "errorHash": "",
    "fallbackUsed": false,
    "finiteWeights": true,
    "flagEmbeddingImportPass": true,
    "loadDurationMs": 2032.07,
    "maxCudaMemoryBytes": 1147526656,
    "nonEmptyWeights": true,
    "realSparseExecution": true,
    "relevantGreaterThanIrrelevantSmoke": true,
    "sampleWeightHash": "b4021a022c2786790f03ad732ec39feead76e7583961c5b85c5ef3ebdbc4640f",
    "scoreType": "BGE_M3_LEARNED_SPARSE_DOT_PRODUCT"
  },
  "safetensorsVersion": "0.7.0",
  "schemaVersion": "agent-rag-v23-bge-m3-sparse-environment-audit-v1",
  "status": "BLOCKED",
  "tokenizersVersion": "0.22.2",
  "torchVersion": "2.5.1+cu121",
  "transformersVersion": "5.3.0"
}
```
