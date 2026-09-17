# V1.6.12 Experiment A Controls

Status: `V23_EXPERIMENT_A_SINGLE_FACTOR_FROZEN`

Experiment A changes exactly one major factor: Synthetic dataset `v2.2` is replaced by boundary-focused Synthetic dataset `v2.3`.

Frozen controls:

- base model: `Qwen3-1.7B`
- contract version: `v2.0.0`
- prompt version: `v2.1.0`
- evaluator version: `v2.1.0`
- max length: `384`
- completion-only encoding: `true`
- quantization: `4-bit NF4`
- double quantization: `true`
- LoRA target modules: `q_proj`, `v_proj`
- LoRA r/alpha/dropout: `8 / 16 / 0.05`
- epochs: `1`
- batch size: `1`
- gradient accumulation steps: `8`
- learning rate: `1e-4`
- checkpoint selection: `validation_loss_only`
- WDDM memory sentinel: `true`
- old adapter warm start: `false`
- old holdout access: `false`

Forbidden changes in this stage include prompt edits, contract edits, evaluator edits, LoRA module/rank changes, epoch increases, old adapter warm start, and any v2.2/v1.6.4 holdout access before the single final allowed evaluation.
