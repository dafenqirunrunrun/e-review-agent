# SetFit Binary Router Report

## Scope

Step 21.3E evaluates one task-specific SetFit binary classifier. Runtime Router, Safety Gate, risk taxonomy, datasets, workflow, RAG, and Frozen Gold remain unchanged.

## Model And Training

Base encoder `BAAI/bge-small-zh-v1.5` at revision `7999E1D3359715C523056EF9478215996D62A620` uses `MIT`, `23953920` parameters, and `512`-dimensional embeddings.
Train/Dev `{'FAST_ELIGIBLE': 36, 'LONG_REQUIRED': 28}/{'FAST_ELIGIBLE': 9, 'LONG_REQUIRED': 7}`. Configuration: `{"batchSize": 8, "bodyLearningRate": 2e-05, "framework": "setfit", "headLearningRate": 0.01, "hyperparameterSearchCount": 0, "loss": "CosineSimilarityLoss", "maxLength": 256, "numEpochs": 1, "numIterations": 10, "resourceAdjustmentCount": 0, "samplingStrategy": "oversampling", "seed": 2135, "sentenceTransformersVersion": "3.4.1", "setfitVersion": "1.1.3", "useAmp": true}`.
Training time `15645.96 ms`; peak allocated/reserved VRAM `795.05/1062.0 MiB`.
Threshold `0.5` was selected on Dev16 only.

## Validation And Boundary

Validation accuracy/F1 `0.7000/0.5714`, LONG recall `0.7273`, FAST precision/coverage `0.8696/0.5750`, false fast `3`.
Boundary LONG recall `1.0000`, high-risk false fast `0`, abstention `5/5`, hard-negative FAST recall `0.0000`.

## Three-way Comparison

`{"cheapRule": {"falseFast": 8, "fastCoverage": 0.875, "fastPrecision": 0.771429, "hardNegativeFastRecall": 0.0, "highRiskFalseFast": 8, "longRecall": 0.272727, "p50Ms": null, "p95Ms": null, "safetyFalseFast": 8}, "frozenBgeLogistic": {"falseFast": 0, "fastCoverage": 0.05, "fastPrecision": 1.0, "hardNegativeFastRecall": 0.0, "highRiskFalseFast": 0, "longRecall": 1.0, "p50Ms": 29.614, "p95Ms": 54.793905, "safetyFalseFast": 0}, "setfitBinary": {"falseFast": 3, "fastCoverage": 0.575, "fastPrecision": 0.869565, "hardNegativeFastRecall": 0.0, "highRiskFalseFast": 3, "longRecall": 0.727273, "p50Ms": 4.3577, "p95Ms": 6.475895, "safetyFalseFast": 3}}`

## Gates

`STEP21_3E_GATE = PASS`
`SETFIT_BINARY_ROUTER_CANDIDATE_GATE = FAIL_SAFETY`
`NEXT_RECOMMENDATION = SETFIT_BINARY_ROUTER_UNSAFE`
