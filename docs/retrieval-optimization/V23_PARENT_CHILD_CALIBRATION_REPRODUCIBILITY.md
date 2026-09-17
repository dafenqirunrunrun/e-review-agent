# V2.3 Parent-Child Calibration Reproducibility

- Fresh-process runs: `2`
- Frozen configuration only: `true`
- Coverage@20: `0.766667` / `0.766667`
- Deep-Rank Recovery: `0.354839` / `0.354839`
- Hierarchical-only Hits: `11` / `11`
- Candidate and ranking hashes match: `True`
- Status: `E_REVIEW_V23_PARENT_CHILD_CALIBRATION_REPRODUCIBILITY_PASS`

The dense route fields are recorded as deterministic f60948d7 calibration-route hashes because the frozen calibration implementation did not use real dense scoring inside the selected Parent-Child algorithm. Real BGE-M3/FAISS runtime remains covered by the separate required runtime gate.
