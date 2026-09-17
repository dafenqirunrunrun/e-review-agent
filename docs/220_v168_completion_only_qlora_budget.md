# V1.6.8 Completion-only QLoRA Budget

Status: `V21_COMPLETION_ONLY_QLORA_BUDGET_NOT_RUN_PRETRAIN_DATA_BLOCKED`
- train_count: `336`
- validation_count: `54`
- system_user_mask_rate: `1.0`
- assistant_trainable_rate: `1.0`
- eos_present_rate: `1.0`
- eos_trainable_rate: `0.7487179487179487`
- truncation_rate: `0.2512820512820513`
- zero_trainable_sample_count: `0`

QLoRA budget and training were not run because the full train/validation audit failed before GPU execution.
No prompt, schema, max_length, split, or training configuration was changed to bypass this gate.
