-- Step 21.4.2: distinguish real user ratings from legacy/default values.
-- Legacy star=1 cannot be distinguished from the old database default and is
-- therefore UNKNOWN/null. Values 2-5 could not have come from that default and
-- retain their user-provided meaning.
ALTER TABLE `litemall_comment`
  MODIFY COLUMN `star` smallint(6) NULL DEFAULT NULL COMMENT '评分，1-5；未知评分必须为NULL',
  ADD COLUMN `rating_source` varchar(20) NOT NULL DEFAULT 'UNKNOWN'
    COMMENT '评分来源：USER_PROVIDED或UNKNOWN' AFTER `star`;

UPDATE `litemall_comment`
SET `rating_source` = CASE WHEN `star` BETWEEN 2 AND 5 THEN 'USER_PROVIDED' ELSE 'UNKNOWN' END,
    `star` = CASE WHEN `star` BETWEEN 2 AND 5 THEN `star` ELSE NULL END;
