# V2.3 Phase 9.4B Input Baseline Lock

Source commit: `8e818612`

Phase 9.4A evidence hashes:

| Evidence | SHA-256 |
|---|---|
| `v23-bge-m3-sparse-isolated-environment.json` | `7b9bca64bb599031a6473d23f989b2b030887609ebf9c0e375f6f5494372604f` |
| `v23-bge-m3-sparse-tokenizer-parity.json` | `31eb33ff86e8211e675ddd016efb525582b6b41bc3936ad140a7421699a513a2` |
| `v23-bge-m3-sparse-runtime-smoke.json` | `90fc576701048403aa40cb08438ecc547b2b682293d8b00a0f961627eb9ffacb` |
| `v23-bge-m3-sparse-environment-gate.json` | `60fb7a0b2af6d5481371ec5a08707b81d803ab8ffdeab37a442a9daefc5c2d55` |

Locked environment:

```text
environmentFingerprint = 9820236f02e050fa189890df8dcf3a6055c7a6690d91d54f1afbddd1c8df0167
dependencyFingerprint = 9820236f02e050fa189890df8dcf3a6055c7a6690d91d54f1afbddd1c8df0167
pipCheckPass = true
cudaAvailable = true
realSparseExecution = true
fallbackUsed = false
tokenizerParityPass = true
```
Locked model:

```text
modelId = BAAI/bge-m3
modelRevision = external-existing
modelFingerprint = a36441812a43bc60e2464af3cc3ffc4d466fc2dc9a52d921264b0109c39094a2
tokenizerFingerprint = 4938bd69f3dd784423447bf8f6082c866911cea4be80ffe85b46a00acb405600
```

Locked benchmark:

```text
datasetVersion = v23-retrieval-qualification-v2
datasetHash = d638d44c69e1e678c2f990fd193af23d2ac18962b6e2be5eaf1ffd19e4575e47
knowledgeSnapshotHash = 70d9285947d8a84254206a70d9d31c6789b5ff902a8340cb18abdab20eaa30b4
eligibilityVersion = agent-rag-v22-canonical-evidence-eligibility-v1
retrievalContentVersion = content-only
```

Boundary:

```text
torchtest = DEPENDENCY_CONFLICT_ENVIRONMENT / NOT_QUALIFIED
Evaluation split = frozen and not consumed
Challenge split = frozen and not consumed
section_content = STRUCTURED_RETRIEVAL_CONTENT_NOT_QUALIFIED
```
