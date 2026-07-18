drop database if exists litemall;
drop user if exists 'litemall'@'%';
-- 支持emoji：需要mysql数据库参数： character_set_server=utf8mb4
create database litemall default character set utf8mb4 collate utf8mb4_unicode_ci;
use litemall;
-- Public snapshot note:
-- Replace change_me with a local development password before running this script.
create user 'litemall'@'%' identified by 'change_me';
grant all privileges on litemall.* to 'litemall'@'%';
flush privileges;
