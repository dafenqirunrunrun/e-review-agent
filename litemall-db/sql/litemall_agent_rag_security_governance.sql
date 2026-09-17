-- Agent-RAG security governance and audit integrity migration.
-- Apply to the internal litemall schema. Do not edit litemall-db/test.sql.

ALTER TABLE litemall_agent_rag_run
  ADD COLUMN security_policy_version VARCHAR(64) NULL,
  ADD COLUMN pii_detected TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN pii_types_json TEXT NULL,
  ADD COLUMN pii_count INT NOT NULL DEFAULT 0,
  ADD COLUMN model_input_redacted TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN audit_redacted TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN ui_redacted TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN prompt_injection_detected TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN prompt_injection_risk_level VARCHAR(32) NULL,
  ADD COLUMN prompt_injection_signals_json TEXT NULL,
  ADD COLUMN prompt_injection_execution_suppressed TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN citation_set_hash CHAR(64) NULL,
  ADD COLUMN runtime_config_hash CHAR(64) NULL,
  ADD COLUMN effective_decision_hash CHAR(64) NULL,
  ADD COLUMN previous_audit_hash CHAR(64) NULL,
  ADD COLUMN audit_hash CHAR(64) NULL,
  ADD COLUMN audit_integrity_status VARCHAR(32) NULL,
  ADD COLUMN evidence_expires_at DATETIME NULL,
  ADD COLUMN raw_input_expires_at DATETIME NULL;

ALTER TABLE litemall_agent_rag_evidence
  ADD COLUMN pii_redacted TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN evidence_expired TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN expired_at DATETIME NULL,
  ADD COLUMN citation_set_hash CHAR(64) NULL;

ALTER TABLE litemall_agent_rag_override
  ADD COLUMN previous_override_hash CHAR(64) NULL,
  ADD COLUMN override_hash CHAR(64) NULL,
  ADD COLUMN effective_decision_hash CHAR(64) NULL;

CREATE TABLE IF NOT EXISTS litemall_agent_rag_audit_chain (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL,
  last_run_id BIGINT NULL,
  last_audit_hash CHAR(64) NULL,
  chain_version BIGINT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uk_agent_rag_audit_chain_tenant (tenant_id)
);
