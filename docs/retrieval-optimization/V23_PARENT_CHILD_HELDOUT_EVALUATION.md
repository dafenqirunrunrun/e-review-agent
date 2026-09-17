# V2.3 Parent-Child Held-out Evaluation

## Decision

`PARENT_AWARE_QUALITY_BLOCKED`

## Flat

- Coverage@20: `0.65`
- MRR: `0.17893`
- nDCG@5: `0.177197`

## Parent-aware

- Coverage@20: `0.633333`
- MRR: `0.170905`
- nDCG@5: `0.163507`

## Increment

- Coverage@20 lift: `-0.016667`
- Parent-aware-only hits: `3`
- Flat-only hits: `5`
- Net recovered: `-2`

The mechanism is accurately described as Document/Section Parent-Chunk Retrieval with parent-aware fusion. ParentTopN covers all 18 parents, so this result must not be described as child-scope reduction.
