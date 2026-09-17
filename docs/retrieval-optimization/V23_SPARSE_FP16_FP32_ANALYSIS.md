# V2.3 Sparse FP16/FP32 Analysis

```json
{
  "conclusion": "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED",
  "fp16": {
    "averageMaxWeight": 0.18110482,
    "averageNonZeroDimensions": 3.743,
    "averageWeightSum": 0.58390835,
    "caseCount": 35,
    "encodeP50Ms": 50.903,
    "encodeP95Ms": 50.903,
    "medianNonZeroDimensions": 2.0,
    "p95NonZeroDimensions": 14.0,
    "peakCudaMemoryMb": 1097.681,
    "rawSparseNonEmptyCount": 29,
    "rawSparseNonEmptyRate": 0.828571,
    "tokenCountMedian": 24.0,
    "tokenCountP95": 24.0
  },
  "fp32Summary": {
    "fp16NonEmptyRate": 0.828571,
    "fp16P95Ms": 50.903,
    "fp16PeakCudaMemoryMb": 1097.681,
    "fp32IndexBuildThroughputPerSecond": 14.959,
    "fp32NonEmptyRate": 0.657143,
    "fp32P95Ms": 66.849,
    "fp32PeakCudaMemoryMb": 2184.802
  }
}
```
