# V1.6.8 V2.1 Controlled Training

Status: `PRIVATE_SYNTHETIC_SFT_V21_QLORA_TRAIN_NOT_RUN_PRETRAIN_DATA_BLOCKED`

- pretrain_contract_integrity: `V168_PRETRAIN_CONTRACT_INTEGRITY_PASS`
- holdout_provenance: `V21_HOLDOUT_PROVENANCE_PASS`
- holdout_seal: `V21_ENGINEERING_HOLDOUT_SEALED`
- train_validation_data: `V21_TRAIN_VALIDATION_DATA_BLOCKED`

Training was not started. The full train/validation completion-only audit found target truncation under the frozen prompt, chat template, and `max_length=384`. Per the stage stop rules, QLoRA budget, controlled training, holdout evaluation, and real-text robustness were not executed.

No v1.6.4 adapter, v1.6.4 holdout, v2.1 holdout body during training, Amazon, ASAP, public pilot, real images, or external test data entered training.
