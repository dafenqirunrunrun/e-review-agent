-- E-Review Agent v1.0 Final Hardening: lightweight RAG case memory.
-- Safe to run repeatedly. It only creates missing tables and indexes.

CREATE TABLE IF NOT EXISTS `litemall_ai_case_knowledge` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `case_title` varchar(128) NOT NULL COMMENT '妗堜緥鏍囬',
  `source_type` varchar(32) DEFAULT NULL COMMENT '鏉ユ簮绫诲瀷',
  `source_id` int(11) DEFAULT NULL COMMENT '鏉ユ簮 ID',
  `product_id` int(11) DEFAULT NULL COMMENT '鍟嗗搧 ID',
  `product_name` varchar(128) DEFAULT NULL COMMENT '鍟嗗搧鍚嶇О',
  `comment_text` text COMMENT '璇勮鏂囨湰',
  `image_signal` varchar(512) DEFAULT NULL COMMENT '鍥剧墖淇″彿',
  `sentiment_label` varchar(32) DEFAULT NULL COMMENT '鎯呮劅鏍囩',
  `risk_types` varchar(256) DEFAULT NULL COMMENT '椋庨櫓绫诲瀷',
  `risk_level` varchar(32) DEFAULT NULL COMMENT '椋庨櫓绛夌骇',
  `evidence` text COMMENT '璇佹嵁鎽樿',
  `operation_result` text COMMENT '杩愯惀澶勭悊缁撴灉',
  `feedback_type` varchar(32) DEFAULT NULL COMMENT '鍙嶉绫诲瀷',
  `tags` varchar(256) DEFAULT NULL COMMENT '妫€绱㈡爣绛?,
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '鍒涘缓鏃堕棿',
  `updated_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '鏇存柊鏃堕棿',
  `deleted` tinyint(1) DEFAULT '0' COMMENT '閫昏緫鍒犻櫎',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ai_case_source` (`source_type`, `source_id`),
  KEY `idx_ai_case_product` (`product_id`),
  KEY `idx_ai_case_risk` (`risk_level`, `sentiment_label`),
  KEY `idx_ai_case_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI 妗堜緥鐭ヨ瘑搴?;

CREATE TABLE IF NOT EXISTS `litemall_ai_case_retrieval_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `run_id` int(11) DEFAULT NULL COMMENT 'Agent Run ID',
  `source_type` varchar(32) DEFAULT NULL COMMENT '妫€绱㈡潵婧愮被鍨?,
  `source_id` int(11) DEFAULT NULL COMMENT '妫€绱㈡潵婧?ID',
  `query_text` text COMMENT '妫€绱㈡枃鏈?,
  `retrieved_case_ids` varchar(512) DEFAULT NULL COMMENT '鍙洖妗堜緥 ID',
  `top_k` int(11) DEFAULT '3' COMMENT 'Top-K',
  `retrieval_mode` varchar(32) DEFAULT 'local_keyword' COMMENT '妫€绱㈡ā寮?,
  `duration_ms` bigint(20) DEFAULT NULL COMMENT '妫€绱㈣€楁椂',
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '鍒涘缓鏃堕棿',
  `deleted` tinyint(1) DEFAULT '0' COMMENT '閫昏緫鍒犻櫎',
  PRIMARY KEY (`id`),
  KEY `idx_ai_case_log_run` (`run_id`),
  KEY `idx_ai_case_log_source` (`source_type`, `source_id`),
  KEY `idx_ai_case_log_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI 妗堜緥妫€绱㈡棩蹇?;
