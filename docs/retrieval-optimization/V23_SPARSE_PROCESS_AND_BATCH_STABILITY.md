# V2.3 Sparse Process and Batch Stability

```json
{
  "batchParity": {
    "conclusion": "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED",
    "rows": [
      {
        "invocationPath": "ORIGINAL_INDEX_BUILDER_PATH",
        "precision": "FP16",
        "status": "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"
      },
      {
        "invocationPath": "ORIGINAL_INDEX_BUILDER_PATH",
        "precision": "FP32",
        "status": "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"
      },
      {
        "invocationPath": "RCA_OFFICIAL_DIRECT_PATH",
        "precision": "FP16",
        "status": "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"
      },
      {
        "invocationPath": "RCA_OFFICIAL_DIRECT_PATH",
        "precision": "FP32",
        "status": "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"
      },
      {
        "invocationPath": "DQA_CONTROL_PATH",
        "precision": "FP16",
        "status": "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"
      },
      {
        "invocationPath": "DQA_CONTROL_PATH",
        "precision": "FP32",
        "status": "SPARSE_BATCH_SIZE_SENSITIVITY_CONFIRMED"
      }
    ],
    "schemaVersion": "agent-rag-v23-sparse-batch-parity-v1"
  },
  "repeatability": {
    "conclusion": "SPARSE_PROCESS_REPEATABILITY_BLOCKED",
    "rows": [
      {
        "batchSize": 1,
        "invocationPath": "DQA_CONTROL_PATH",
        "precision": "FP16",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 8,
        "invocationPath": "DQA_CONTROL_PATH",
        "precision": "FP16",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 1,
        "invocationPath": "DQA_CONTROL_PATH",
        "precision": "FP32",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 8,
        "invocationPath": "DQA_CONTROL_PATH",
        "precision": "FP32",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 1,
        "invocationPath": "ORIGINAL_INDEX_BUILDER_PATH",
        "precision": "FP16",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 8,
        "invocationPath": "ORIGINAL_INDEX_BUILDER_PATH",
        "precision": "FP16",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 1,
        "invocationPath": "ORIGINAL_INDEX_BUILDER_PATH",
        "precision": "FP32",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 8,
        "invocationPath": "ORIGINAL_INDEX_BUILDER_PATH",
        "precision": "FP32",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 1,
        "invocationPath": "RCA_OFFICIAL_DIRECT_PATH",
        "precision": "FP16",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 8,
        "invocationPath": "RCA_OFFICIAL_DIRECT_PATH",
        "precision": "FP16",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 1,
        "invocationPath": "RCA_OFFICIAL_DIRECT_PATH",
        "precision": "FP32",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      },
      {
        "batchSize": 8,
        "invocationPath": "RCA_OFFICIAL_DIRECT_PATH",
        "precision": "FP32",
        "status": "SPARSE_OUTPUT_PROCESS_NONDETERMINISM_CONFIRMED"
      }
    ],
    "schemaVersion": "agent-rag-v23-sparse-process-repeatability-v1"
  }
}
```
