-- v1.6 Hybrid RAG observability migration. Safe to execute repeatedly.
DROP PROCEDURE IF EXISTS e_review_add_column_v16;
DELIMITER $$
CREATE PROCEDURE e_review_add_column_v16(IN table_name_value VARCHAR(64), IN column_name_value VARCHAR(64), IN definition_value VARCHAR(512))
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = table_name_value AND column_name = column_name_value
  ) THEN
    SET @ddl = CONCAT('ALTER TABLE `', table_name_value, '` ADD COLUMN `', column_name_value, '` ', definition_value);
    PREPARE statement_value FROM @ddl;
    EXECUTE statement_value;
    DEALLOCATE PREPARE statement_value;
  END IF;
END$$
DELIMITER ;

CALL e_review_add_column_v16('litemall_ai_agent_run', 'rag_enabled', 'tinyint(1) DEFAULT 0');
CALL e_review_add_column_v16('litemall_ai_agent_run', 'rag_strategy', 'varchar(32) DEFAULT NULL');
CALL e_review_add_column_v16('litemall_ai_agent_run', 'retrieval_hit_count', 'int DEFAULT 0');
CALL e_review_add_column_v16('litemall_ai_agent_run', 'retrieval_top_score', 'decimal(10,6) DEFAULT NULL');
CALL e_review_add_column_v16('litemall_ai_agent_run', 'embedding_provider', 'varchar(64) DEFAULT NULL');
CALL e_review_add_column_v16('litemall_ai_agent_run', 'reranker_provider', 'varchar(64) DEFAULT NULL');
CALL e_review_add_column_v16('litemall_ai_agent_run', 'retrieval_latency_ms', 'bigint DEFAULT NULL');
CALL e_review_add_column_v16('litemall_ai_agent_run', 'route_decision', 'varchar(64) DEFAULT NULL');
CALL e_review_add_column_v16('litemall_ai_agent_run', 'route_reason', 'varchar(512) DEFAULT NULL');

DROP PROCEDURE IF EXISTS e_review_add_column_v16;
