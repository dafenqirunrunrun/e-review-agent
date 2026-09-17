-- E-Review Agent v2.0 Agent-RAG durable workflow.
-- Apply with the litemall database selected.

CREATE TABLE IF NOT EXISTS `litemall_agent_rag_run` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `request_id` VARCHAR(64) NOT NULL,
  `idempotency_key` CHAR(64) NOT NULL,
  `tenant_id` VARCHAR(64) NOT NULL,
  `subject_type` VARCHAR(32) NOT NULL,
  `subject_id` VARCHAR(128) NOT NULL,
  `parent_run_id` BIGINT NULL,
  `replay_of_run_id` BIGINT NULL,
  `status` VARCHAR(32) NOT NULL,
  `risk_level` VARCHAR(32) NULL,
  `risk_types_json` TEXT NULL,
  `action` VARCHAR(64) NULL,
  `confidence` DECIMAL(8,6) NULL,
  `requires_human_review` TINYINT(1) NOT NULL DEFAULT 0,
  `runtime_mode` VARCHAR(64) NULL,
  `target_mode` VARCHAR(64) NULL,
  `requested_provider_impl` VARCHAR(64) NULL,
  `effective_provider_impl` VARCHAR(64) NULL,
  `requested_retrieval_mode` VARCHAR(64) NULL,
  `effective_retrieval_mode` VARCHAR(64) NULL,
  `index_version` VARCHAR(128) NULL,
  `fallback_used` TINYINT(1) NOT NULL DEFAULT 0,
  `fallback_reason` VARCHAR(255) NULL,
  `schema_version` VARCHAR(32) NOT NULL,
  `analyzer_version` VARCHAR(128) NULL,
  `evidence_id` VARCHAR(64) NULL,
  `retry_count` INT NOT NULL DEFAULT 0,
  `error_code` VARCHAR(128) NULL,
  `error_message` VARCHAR(512) NULL,
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  `duration_ms` BIGINT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_rag_run_tenant_request` (`tenant_id`, `request_id`),
  UNIQUE KEY `uk_agent_rag_run_idem` (`idempotency_key`),
  KEY `idx_agent_rag_run_subject` (`tenant_id`, `subject_type`, `subject_id`),
  KEY `idx_agent_rag_run_status_time` (`tenant_id`, `status`, `created_at`),
  KEY `idx_agent_rag_run_risk_time` (`tenant_id`, `risk_level`, `created_at`),
  KEY `idx_agent_rag_run_evidence` (`evidence_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `litemall_agent_rag_evidence` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `evidence_id` VARCHAR(64) NOT NULL,
  `run_id` BIGINT NOT NULL,
  `request_id` VARCHAR(64) NOT NULL,
  `tenant_id` VARCHAR(64) NOT NULL,
  `bundle_hash` CHAR(64) NOT NULL,
  `bounded_json` LONGTEXT NOT NULL,
  `citation_count` INT NOT NULL DEFAULT 0,
  `payload_size_bytes` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_rag_evidence_tenant_id` (`tenant_id`, `evidence_id`),
  UNIQUE KEY `uk_agent_rag_evidence_run` (`run_id`),
  KEY `idx_agent_rag_evidence_request` (`tenant_id`, `request_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `litemall_agent_rag_override` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `run_id` BIGINT NOT NULL,
  `tenant_id` VARCHAR(64) NOT NULL,
  `previous_risk_level` VARCHAR(32) NULL,
  `new_risk_level` VARCHAR(32) NOT NULL,
  `previous_action` VARCHAR(64) NULL,
  `new_action` VARCHAR(64) NOT NULL,
  `reason` VARCHAR(1000) NOT NULL,
  `operator_id` BIGINT NOT NULL,
  `created_at` DATETIME NOT NULL,
  `deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_agent_rag_override_run_time` (`run_id`, `created_at`),
  KEY `idx_agent_rag_override_tenant_time` (`tenant_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Rollback:
-- DROP TABLE IF EXISTS `litemall_agent_rag_override`;
-- DROP TABLE IF EXISTS `litemall_agent_rag_evidence`;
-- DROP TABLE IF EXISTS `litemall_agent_rag_run`;
