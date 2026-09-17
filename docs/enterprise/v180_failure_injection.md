# v1.8.0 Failure Injection

Status: `V180_FAILURE_INJECTION_25_PASS`

Case count: `25`
Pass count: `25`
Fail count: `0`

## Cases

- `prompt_injection_english`: `PASS`
- `prompt_injection_chinese`: `PASS`
- `pii_phone_redaction`: `PASS`
- `pii_bearer_redaction`: `PASS`
- `safe_logger_drops_raw`: `PASS`
- `tenant_empty_rejected`: `PASS`
- `tenant_path_traversal_rejected`: `PASS`
- `tenant_zero_width_rejected`: `PASS`
- `acl_cross_tenant_filtered`: `PASS`
- `acl_deleted_filtered`: `PASS`
- `bm25_empty_query_safe`: `PASS`
- `faiss_no_active_version_blocked`: `PASS`
- `tool_forbidden_business_action`: `PASS`
- `tool_unregistered_blocked`: `PASS`
- `tool_non_idempotent_blocked`: `PASS`
- `tool_timeout_policy_blocked`: `PASS`
- `agent_prompt_injection_skips_tools`: `PASS`
- `agent_max_tool_calls_enforced`: `PASS`
- `cache_injection_not_stored`: `PASS`
- `cache_key_no_raw_query`: `PASS`
- `memory_idempotency_expiry`: `PASS`
- `sqlite_idempotency_restart`: `PASS`
- `runtime_config_rejects_absolute_adapter_path`: `PASS`
- `runtime_config_rejects_bad_adapter_hash`: `PASS`
- `human_review_on_high_risk`: `PASS`
