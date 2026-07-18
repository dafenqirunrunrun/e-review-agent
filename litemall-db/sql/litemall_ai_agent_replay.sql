-- E-Review Agent v1.0 Final Hardening: Agent Run replay and comparison.
-- Safe to run repeatedly on MySQL 5.7/8.x.

SET @schema_name = DATABASE();

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE litemall_ai_agent_run ADD COLUMN replay_from_run_id int DEFAULT NULL COMMENT ''Replay 鏉ユ簮 Run ID''',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_ai_agent_run'
    AND column_name = 'replay_from_run_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE litemall_ai_agent_run ADD COLUMN replay_count int DEFAULT 0 COMMENT ''琚噸鏀炬鏁?'',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_ai_agent_run'
    AND column_name = 'replay_count'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE litemall_ai_agent_run ADD COLUMN is_replay tinyint(1) DEFAULT 0 COMMENT ''鏄惁 Replay Run''',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_ai_agent_run'
    AND column_name = 'is_replay'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS `litemall_ai_agent_replay_compare` (
  `id` int NOT NULL AUTO_INCREMENT,
  `original_run_id` int NOT NULL,
  `replay_run_id` int NOT NULL,
  `sentiment_changed` tinyint(1) DEFAULT 0,
  `risk_changed` tinyint(1) DEFAULT 0,
  `confidence_delta` decimal(10,4) DEFAULT NULL,
  `original_summary` mediumtext,
  `replay_summary` mediumtext,
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `deleted` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_replay_compare` (`original_run_id`, `replay_run_id`),
  KEY `idx_replay_original` (`original_run_id`),
  KEY `idx_replay_run` (`replay_run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent Run Replay 瀵规瘮';
