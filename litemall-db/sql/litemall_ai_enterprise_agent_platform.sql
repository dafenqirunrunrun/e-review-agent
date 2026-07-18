-- E-Review Agent v1.1 experimental enterprise Agent platform tables.
-- Safe to run repeatedly. This migration documents persistent storage for
-- Tool Registry, policy approval, local memory, and guardrail events.

CREATE TABLE IF NOT EXISTS `litemall_ai_tool_registry` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `tool_name` varchar(96) NOT NULL,
  `provider` varchar(64) DEFAULT NULL,
  `request_summary` varchar(512) DEFAULT NULL,
  `response_summary` varchar(512) DEFAULT NULL,
  `tool_display_name` varchar(128) NOT NULL,
  `tool_description` varchar(512) DEFAULT NULL,
  `tool_category` varchar(64) DEFAULT NULL,
  `input_schema_json` mediumtext,
  `output_schema_json` mediumtext,
  `risk_level` varchar(32) DEFAULT 'low',
  `requires_approval` tinyint(1) DEFAULT 0,
  `enabled` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ai_tool_name` (`tool_name`),
  KEY `idx_ai_tool_enabled` (`enabled`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='E-Review local MCP-like tool registry';

CREATE TABLE IF NOT EXISTS `litemall_ai_tool_invocation_policy` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `tool_name` varchar(96) NOT NULL,
  `allowed_roles` varchar(512) DEFAULT NULL,
  `allowed_trigger_types` varchar(256) DEFAULT NULL,
  `max_calls_per_run` int(11) DEFAULT 3,
  `timeout_ms` int(11) DEFAULT 3000,
  `approval_required` tinyint(1) DEFAULT 0,
  `data_scope` varchar(128) DEFAULT 'local_demo_data_only',
  `enabled` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ai_tool_policy_name` (`tool_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='E-Review local tool invocation policy';

CREATE TABLE IF NOT EXISTS `litemall_ai_tool_execution_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `run_id` int(11) DEFAULT NULL,
  `step_id` int(11) DEFAULT NULL,
  `tool_name` varchar(96) NOT NULL,
  `input_summary` varchar(512) DEFAULT NULL,
  `output_summary` varchar(512) DEFAULT NULL,
  `status` varchar(32) DEFAULT NULL,
  `duration_ms` bigint(20) DEFAULT NULL,
  `error_message` varchar(512) DEFAULT NULL,
  `latency_ms` bigint(20) DEFAULT NULL,
  `blocked_reason` varchar(512) DEFAULT NULL,
  `approval_status` varchar(32) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `deleted` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_ai_tool_log_run` (`run_id`, `step_id`),
  KEY `idx_ai_tool_log_name` (`tool_name`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='E-Review local tool execution log';

CREATE TABLE IF NOT EXISTS `litemall_ai_memory_profile` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `entity_type` varchar(32) NOT NULL,
  `entity_id` varchar(64) NOT NULL,
  `profile_summary` text,
  `risk_count` int(11) DEFAULT 0,
  `positive_count` int(11) DEFAULT 0,
  `negative_count` int(11) DEFAULT 0,
  `repeated_issue_tags` varchar(512) DEFAULT NULL,
  `last_event_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ai_memory_profile` (`entity_type`, `entity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='E-Review local long-term memory profile';

CREATE TABLE IF NOT EXISTS `litemall_ai_memory_event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `entity_type` varchar(32) NOT NULL,
  `entity_id` varchar(64) NOT NULL,
  `source_type` varchar(32) DEFAULT NULL,
  `source_id` int(11) DEFAULT NULL,
  `event_type` varchar(64) DEFAULT NULL,
  `event_summary` text,
  `risk_level` varchar(32) DEFAULT NULL,
  `evidence_json` mediumtext,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `deleted` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_ai_memory_event_entity` (`entity_type`, `entity_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='E-Review local long-term memory event';

CREATE TABLE IF NOT EXISTS `litemall_ai_guardrail_event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `run_id` int(11) DEFAULT NULL,
  `step_id` int(11) DEFAULT NULL,
  `guardrail_type` varchar(64) NOT NULL,
  `rule_name` varchar(128) NOT NULL,
  `severity` varchar(32) DEFAULT NULL,
  `action` varchar(32) DEFAULT NULL,
  `message` varchar(512) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `deleted` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_ai_guardrail_event_run` (`run_id`, `step_id`),
  KEY `idx_ai_guardrail_event_type` (`guardrail_type`, `rule_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='E-Review local guardrail event';
