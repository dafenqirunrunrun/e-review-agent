# V2.3 Phase 9.5A-QC2 Input Lock

## Scope

- Source commit: `088208a1`
- Algorithm base commit: `c230fffd`
- Parent-Child implementation commit: `f60948d7`
- QC2 worktree commit at collection time: `291c7ef9ce4a0668e140942e79adcc41e68c8655`
- Evaluation consumed: `false`
- Challenge consumed: `false`

## Frozen Configuration

- `parentRepresentation=P2`
- `strategy=H2`
- `parentTopN=20`
- `parentPriorEnabled=true`
- `parentPriorConstant=60`
- `postFusionCandidateK=30`
- `maximumFinalK=5`
- `allowBackfill=false`

This phase records reproducibility and regression evidence only. It does not retune Parent-Child retrieval and does not read held-out Evaluation or Challenge splits.
