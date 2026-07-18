CREATE TABLE IF NOT EXISTS `litemall_ai_patrol_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_batch_no` varchar(64) NOT NULL COMMENT '巡检批次号',
  `start_time` datetime DEFAULT NULL COMMENT '开始时间',
  `end_time` datetime DEFAULT NULL COMMENT '结束时间',
  `scan_count` int DEFAULT '0' COMMENT '扫描数量',
  `success_count` int DEFAULT '0' COMMENT '成功数量',
  `failed_count` int DEFAULT '0' COMMENT '失败数量',
  `high_risk_count` int DEFAULT '0' COMMENT '高风险数量',
  `status` varchar(32) DEFAULT NULL COMMENT '状态：running/success/failed',
  `error_message` varchar(512) DEFAULT NULL COMMENT '错误信息',
  `created_time` datetime DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_batch_no` (`task_batch_no`),
  KEY `idx_created_time` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI Agent巡检日志表';
