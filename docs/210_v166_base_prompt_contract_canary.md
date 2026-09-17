# V1.6.6 Base Prompt Contract Canary

Status: `V166_BASE_PROMPT_CONTRACT_CANARY_BLOCKED`

- gates: `{'CANONICAL_SCHEMA_SINGLE_SOURCE_PASS': True, 'PROMPT_CONTRACT_ALIGNMENT_PASS': True, 'COMPLETION_ONLY_LABEL_MASK_PASS': True, 'PRIVATE_SYNTHETIC_SFT_V2_DATASET_PASS': False}`
- blocked_reason: v2 dataset gate did not pass; canary cannot run without validation split
