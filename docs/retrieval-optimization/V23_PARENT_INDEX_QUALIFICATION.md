# V2.3 Parent Index Qualification

## Index Scope

The parent index is qualified as a manifest-only artifact. No vector index file, model path, full parent content, or full chunk content is committed.

## Allowed Parent Routes

- Parent BM25
- Parent BGE-M3 Dense

The dense route reuses the already verified BGE-M3 Dense asset identity. Sparse is explicitly excluded from this phase.

## Qualification Result

The generated manifest records:

- parent count
- child count
- selected parent representation
- max parent tokens
- BM25 configuration hash
- Dense configuration hash
- parent index fingerprint

The parent index gate requires zero tenant violations, zero expired parent content, zero hash mismatch, and no missing parents.
