# V2.3 Phase 9.3 Data Consumption Boundary

Phase 9.2 consumed the original v23 calibration and evaluation splits. They are now diagnostic-only and cannot be reused for final unbiased qualification.

```json
{
  "calibration": true,
  "challenge": false,
  "evaluation": true,
  "futureQualificationAllowedForCalibration": false,
  "futureQualificationAllowedForChallenge": false,
  "futureQualificationAllowedForEvaluation": false
}
```

Decision: Phase 9.3 must build a new balanced benchmark before any new retrieval representation is qualified.
