-- E-Review Agent v0.4 source tracking migration.
-- Safe to execute repeatedly on MySQL 8.x.

SET @schema_name = DATABASE();

SET @has_source_type = (
  SELECT COUNT(1)
  FROM information_schema.columns
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_review_ai_analysis'
    AND column_name = 'source_type'
);
SET @sql = IF(@has_source_type = 0,
  'ALTER TABLE litemall_review_ai_analysis ADD COLUMN source_type varchar(32) DEFAULT NULL COMMENT ''analysis source type'' AFTER id',
  'SELECT ''source_type already exists''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_source_id = (
  SELECT COUNT(1)
  FROM information_schema.columns
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_review_ai_analysis'
    AND column_name = 'source_id'
);
SET @sql = IF(@has_source_id = 0,
  'ALTER TABLE litemall_review_ai_analysis ADD COLUMN source_id int DEFAULT NULL COMMENT ''analysis source id'' AFTER source_type',
  'SELECT ''source_id already exists''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_source_index = (
  SELECT COUNT(1)
  FROM information_schema.statistics
  WHERE table_schema = @schema_name
    AND table_name = 'litemall_review_ai_analysis'
    AND index_name = 'idx_review_ai_source'
);
SET @sql = IF(@has_source_index = 0,
  'ALTER TABLE litemall_review_ai_analysis ADD KEY idx_review_ai_source (source_type, source_id)',
  'SELECT ''idx_review_ai_source already exists''');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE litemall_review_ai_analysis
SET source_type = CASE
    WHEN review_id LIKE 'demo-%' THEN 'demo_review'
    WHEN review_id LIKE 'comment-%' THEN 'litemall_comment'
    ELSE 'manual_input'
  END,
  source_id = CASE
    WHEN review_id LIKE 'demo-%' THEN CAST(REPLACE(review_id, 'demo-', '') AS UNSIGNED)
    WHEN review_id LIKE 'comment-%' THEN CAST(REPLACE(review_id, 'comment-', '') AS UNSIGNED)
    ELSE source_id
  END
WHERE deleted = 0
  AND source_type IS NULL;
