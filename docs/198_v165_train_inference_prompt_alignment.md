# V1.6.5 Train Inference Prompt Alignment

Status: `TRAIN_INFERENCE_PROMPT_MISMATCH_CONFIRMED`
- training uses manual concat but runtime uses tokenizer.apply_chat_template
- training target fields use text_evidence/retrieved_case_evidence/route_reason/unsupported_claims
- runtime prompt asks for sentiment/evidence/reason/suggestion/confidence
- v1.6.4 validation prompt appends JSON: delimiter, not the runtime prompt
