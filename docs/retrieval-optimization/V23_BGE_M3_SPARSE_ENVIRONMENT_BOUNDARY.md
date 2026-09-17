# V2.3 BGE-M3 Sparse Environment Boundary

```json
{
  "conflictEnvironmentStatus": "NOT_QUALIFIED",
  "currentCorePackageVersions": {
    "huggingfaceHub": "1.7.1",
    "safetensors": "0.7.0",
    "tokenizers": "0.22.2",
    "torch": "2.5.1+cu121",
    "transformers": "5.3.0"
  },
  "decision": "use isolated historical v2.2 environment for sparse qualification; do not use conflict environment for gates",
  "primaryEnvironment": {
    "coreDependencyFingerprint": "a9e4d5ebb2b7e4e8f1d600f6166db811343f05ffae443de119a836dd90a4e8c6",
    "dependencyFingerprint": "884a77f248fbd684da18323e3590dbb63a87c434b63a2039c683b2dce90e7590",
    "environmentId": "torchtest-current-conflict",
    "packageVersions": {
      "huggingfaceHub": "1.7.1",
      "safetensors": "0.7.0",
      "tokenizers": "0.22.2",
      "torch": "2.5.1+cu121",
      "torchCuda": "12.1",
      "transformers": "5.3.0"
    },
    "pipCheckPass": false,
    "pipCheckSummary": [
      "sentence-transformers 3.0.1 has requirement transformers<5.0.0,>=4.34.0, but you have transformers 5.3.0."
    ],
    "pythonVersion": "3.10.0",
    "qualificationStatus": "NOT_QUALIFIED",
    "role": "DEPENDENCY_CONFLICT_ENVIRONMENT",
    "tokenizerParityProbe": {
      "attentionMaskHash": "3c1425b38d52d1967a20a1ce4abe58b11af7d5260e368e378cbbc12574a967e8",
      "specialTokenIds": {
        "bos": 0,
        "cls": 0,
        "eos": 2,
        "pad": 1,
        "sep": 2
      },
      "tokenCount": 8,
      "tokenIdsHash": "4938bd69f3dd784423447bf8f6082c866911cea4be80ffe85b46a00acb405600"
    }
  },
  "primaryEnvironmentComparisonScope": [],
  "primaryEnvironmentRole": "DEPENDENCY_CONFLICT_ENVIRONMENT",
  "primaryEnvironmentUnchanged": true,
  "schemaVersion": "agent-rag-v23-bge-m3-sparse-environment-boundary-v1",
  "sourceCorePackageVersions": {
    "huggingfaceHub": "",
    "safetensors": "",
    "tokenizers": "",
    "torch": "",
    "transformers": ""
  },
  "torchtestEnvironmentRole": "DEPENDENCY_CONFLICT_ENVIRONMENT"
}
```
