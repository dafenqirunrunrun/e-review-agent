-- E-Review Agent v1.0 Final Hardening: lightweight RAG case memory.
-- Safe to run repeatedly. It only creates missing tables and indexes.

CREATE TABLE IF NOT EXISTS `litemall_ai_case_knowledge` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `case_title` varchar(128) NOT NULL COMMENT 'Case title',
  `source_type` varchar(32) DEFAULT NULL COMMENT 'Source type',
  `source_id` int(11) DEFAULT NULL COMMENT 'Source ID',
  `product_id` int(11) DEFAULT NULL COMMENT 'Goods ID',
  `product_name` varchar(128) DEFAULT NULL COMMENT 'Goods name',
  `comment_text` text COMMENT 'Review text',
  `image_signal` varchar(512) DEFAULT NULL COMMENT 'Image signal',
  `sentiment_label` varchar(32) DEFAULT NULL COMMENT 'Sentiment label',
  `risk_types` varchar(256) DEFAULT NULL COMMENT 'Risk types',
  `risk_level` varchar(32) DEFAULT NULL COMMENT 'Risk level',
  `evidence` text COMMENT 'Evidence summary',
  `operation_result` text COMMENT 'Operation result',
  `feedback_type` varchar(32) DEFAULT NULL COMMENT 'Feedback type',
  `tags` varchar(256) DEFAULT NULL COMMENT 'Retrieval tags',
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
  `updated_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated time',
  `deleted` tinyint(1) DEFAULT '0' COMMENT 'Logical deletion',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ai_case_source` (`source_type`, `source_id`),
  KEY `idx_ai_case_product` (`product_id`),
  KEY `idx_ai_case_risk` (`risk_level`, `sentiment_label`),
  KEY `idx_ai_case_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI case knowledge base';

CREATE TABLE IF NOT EXISTS `litemall_ai_case_retrieval_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `run_id` int(11) DEFAULT NULL COMMENT 'Agent Run ID',
  `source_type` varchar(32) DEFAULT NULL COMMENT 'Retrieval source type',
  `source_id` int(11) DEFAULT NULL COMMENT 'Retrieval source ID',
  `query_text` text COMMENT 'Retrieval query text',
  `retrieved_case_ids` varchar(512) DEFAULT NULL COMMENT 'Retrieved case IDs',
  `top_k` int(11) DEFAULT '3' COMMENT 'Top-K',
  `retrieval_mode` varchar(32) DEFAULT 'local_keyword' COMMENT 'Retrieval mode',
  `duration_ms` bigint(20) DEFAULT NULL COMMENT 'Retrieval duration ms',
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
  `deleted` tinyint(1) DEFAULT '0' COMMENT 'Logical deletion',
  PRIMARY KEY (`id`),
  KEY `idx_ai_case_log_run` (`run_id`),
  KEY `idx_ai_case_log_source` (`source_type`, `source_id`),
  KEY `idx_ai_case_log_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI case retrieval log';
