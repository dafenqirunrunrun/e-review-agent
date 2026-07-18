-- E-Review Agent v1.5 LLM provider observability migration.
-- Safe to run repeatedly on MySQL 5.7/8.x after the Agent platform tables exist.
-- No API keys, authorization headers, or complete sensitive requests are stored.

DELIMITER //
DROP PROCEDURE IF EXISTS e_review_add_column_v15//
CREATE PROCEDURE e_review_add_column_v15(
  IN p_table varchar(128),
  IN p_column varchar(128),
  IN p_definition varchar(512)
)
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = p_table AND column_name = p_column
  ) THEN
    SET @ddl = CONCAT('ALTER TABLE `', p_table, '` ADD COLUMN `', p_column, '` ', p_definition);
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END//
DELIMITER ;

CALL e_review_add_column_v15('litemall_ai_agent_run', 'llm_provider', 'varchar(64) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'model_name', 'varchar(128) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'prompt_template', 'varchar(128) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'schema_valid', 'tinyint(1) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'schema_error', 'varchar(1024) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'repair_used', 'tinyint(1) DEFAULT 0');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'fallback_used', 'tinyint(1) DEFAULT 0');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'token_usage_input', 'int DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'token_usage_output', 'int DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_run', 'latency_ms', 'bigint DEFAULT NULL');

CALL e_review_add_column_v15('litemall_ai_agent_step', 'llm_provider', 'varchar(64) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'model_name', 'varchar(128) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'prompt_template', 'varchar(128) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'schema_valid', 'tinyint(1) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'schema_error', 'varchar(1024) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'repair_used', 'tinyint(1) DEFAULT 0');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'fallback_used', 'tinyint(1) DEFAULT 0');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'token_usage_input', 'int DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'token_usage_output', 'int DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_agent_step', 'latency_ms', 'bigint DEFAULT NULL');

CALL e_review_add_column_v15('litemall_ai_tool_execution_log', 'provider', 'varchar(64) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_tool_execution_log', 'request_summary', 'varchar(512) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_tool_execution_log', 'response_summary', 'varchar(512) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_tool_execution_log', 'error_message', 'varchar(512) DEFAULT NULL');
CALL e_review_add_column_v15('litemall_ai_tool_execution_log', 'latency_ms', 'bigint DEFAULT NULL');

DROP PROCEDURE IF EXISTS e_review_add_column_v15;
