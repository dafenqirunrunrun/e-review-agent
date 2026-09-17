# v2.0 Agent-RAG Phase 2 Knowledge Contract

## Document

Required fields:

- `documentId`
- `tenantId`
- `sourceType`
- `title`
- `content`
- `status`
- `version`
- `contentHash`

Supported `sourceType` values:

- `policy`
- `product-manual`
- `platform-rule`
- `risk-case`
- `faq`
- `customer-service`
- `public-regulation`
- `internal-guideline`

Visibility currently supports:

- `tenant`
- `public`

## Chunk

Required fields include `chunkId`, `documentId`, `tenantId`, `chunkIndex`,
`text`, `tokenCount`, `contentHash`, `sourceType`, `documentVersion`, and
`status`.

Chunking rules:

- Empty content is rejected.
- Duplicate content hashes are deduplicated.
- Disabled, deleted, retired, expired, and future documents do not enter
  default retrieval.
- `documentVersion` and `contentHash` are preserved for audit.

## Manifest

`IndexManifest` records index version, tenant, status, embedding mode,
document/chunk counts, sparse/dense index type, config hash, content root hash,
and activation time.
