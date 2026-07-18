CREATE TABLE IF NOT EXISTS `litemall_ai_demo_review` (
  `id` int NOT NULL AUTO_INCREMENT,
  `product_id` int NOT NULL COMMENT '商品ID',
  `product_name` varchar(127) NOT NULL COMMENT '商品名称',
  `category_name` varchar(127) DEFAULT NULL COMMENT '商品类目',
  `nickname` varchar(63) DEFAULT NULL COMMENT '用户昵称',
  `rating` tinyint DEFAULT NULL COMMENT '用户评分',
  `review_text` text NOT NULL COMMENT '评论文本',
  `image_url` varchar(512) DEFAULT NULL COMMENT '评论图片URL',
  `analysis_status` varchar(32) NOT NULL DEFAULT 'pending' COMMENT '分析状态：pending/analyzing/analyzed/failed',
  `created_time` datetime DEFAULT NULL COMMENT '创建时间',
  `updated_time` datetime DEFAULT NULL COMMENT '更新时间',
  `deleted` tinyint(1) DEFAULT '0' COMMENT '逻辑删除',
  PRIMARY KEY (`id`),
  KEY `idx_product_id` (`product_id`),
  KEY `idx_analysis_status` (`analysis_status`),
  KEY `idx_created_time` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI演示图文评论表';
