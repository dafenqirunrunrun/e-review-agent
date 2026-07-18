-- E-Review Agent v1.0.4: stateful Agent snapshots and lightweight role metadata.
-- Safe to run repeatedly on MySQL 5.7/8.x.

SET @schema_name = DATABASE();

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE litemall_ai_agent_run ADD COLUMN state_snapshot_json mediumtext COMMENT ''Agent state snapshot JSON'' AFTER error_message',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_ai_agent_run'
    AND column_name = 'state_snapshot_json'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE litemall_ai_agent_step ADD COLUMN agent_role varchar(64) DEFAULT NULL COMMENT ''Lightweight Agent role'' AFTER step_order',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_ai_agent_step'
    AND column_name = 'agent_role'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE litemall_ai_agent_step ADD COLUMN agent_goal varchar(255) DEFAULT NULL COMMENT ''Role goal summary'' AFTER agent_role',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_ai_agent_step'
    AND column_name = 'agent_goal'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

