# V1.6.3.2 SFT Dependency Inventory

Status: `TRAINING_DEPENDENCY_PLAN_BLOCKED_TLS`

- environment: `ereview_sft`
- dry_run_returncode: `1`
- dependency_plan_modifies_torch_cuda: `False`
- wheel_sha256_verified: `False`

## Package Inventory

- torch: installed=`True`, version=`2.5.1+cu121`, import_success=`True`, required=`True`
- torchvision: installed=`True`, version=`0.20.1+cu121`, import_success=`True`, required=`False`
- torchaudio: installed=`True`, version=`2.5.1+cu121`, import_success=`True`, required=`False`
- transformers: installed=`True`, version=`5.3.0`, import_success=`True`, required=`True`
- accelerate: installed=`True`, version=`1.14.0`, import_success=`True`, required=`True`
- peft: installed=`False`, version=`None`, import_success=`False`, required=`True`
- datasets: installed=`False`, version=`None`, import_success=`False`, required=`True`
- safetensors: installed=`True`, version=`0.7.0`, import_success=`True`, required=`True`
- sentencepiece: installed=`False`, version=`None`, import_success=`False`, required=`True`
- protobuf: installed=`False`, version=`None`, import_success=`False`, required=`True`
- tensorboard: installed=`False`, version=`None`, import_success=`False`, required=`False`
- bitsandbytes: installed=`False`, version=`None`, import_success=`False`, required=`True`
- trl: installed=`False`, version=`None`, import_success=`False`, required=`False`
- swift: installed=`False`, version=`None`, import_success=`False`, required=`False`

## Dry Run Result

Official PyPI dry-run failed before dependency resolution because TLS/SSL EOF errors prevented fetching package metadata. No package was installed and `torchtest` was not modified.
