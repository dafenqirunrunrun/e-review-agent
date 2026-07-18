CREATE TABLE IF NOT EXISTS `litemall_ai_operation_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `risk_task_id` int NOT NULL COMMENT '风险任务ID',
  `action_type` varchar(64) NOT NULL COMMENT '处理动作',
  `old_status` varchar(32) DEFAULT NULL COMMENT '原状态',
  `new_status` varchar(32) DEFAULT NULL COMMENT '新状态',
  `operator` varchar(64) DEFAULT NULL COMMENT '操作人',
  `note` varchar(512) DEFAULT NULL COMMENT '备注',
  `created_time` datetime DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_risk_task_id` (`risk_task_id`),
  KEY `idx_created_time` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI运营处理日志表';
