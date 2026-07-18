-- Public CI seed data. This prepares users, permissions, products and
-- reviewable orders only. It must not insert AI analysis or risk-task results.

insert into litemall_role
  (id, name, `desc`, enabled, add_time, update_time, deleted)
values
  (1, 'public-ci-admin', 'Public CI administrator role', 1, now(), now(), 0)
on duplicate key update
  `desc` = values(`desc`),
  enabled = values(enabled),
  deleted = 0,
  update_time = now();

insert into litemall_permission
  (id, role_id, permission, add_time, update_time, deleted)
values
  (1, 1, '*', now(), now(), 0)
on duplicate key update
  role_id = values(role_id),
  permission = values(permission),
  deleted = 0,
  update_time = now();

insert into litemall_admin
  (id, username, password, last_login_ip, last_login_time, avatar, add_time, update_time, deleted, role_ids)
values
  (1, 'ci_public_admin', '$2a$12$RuiGeJNxtYCfdl.PMLlX1u6BppciX.3Bu/Jqa5L5qosgK6NbsWyKS', '127.0.0.1', now(), '', now(), now(), 0, '[1]')
on duplicate key update
  username = values(username),
  password = values(password),
  role_ids = values(role_ids),
  deleted = 0,
  update_time = now();

insert into litemall_user
  (id, username, password, gender, last_login_time, last_login_ip, user_level, nickname, mobile, avatar, weixin_openid, session_key, status, add_time, update_time, deleted)
values
  (1, 'ci_public_user', '$2a$12$i2igeZc9xOe45pqiOhYTP.zSosDSLus3i5L2QcgHlwBqyCygR56LW', 0, now(), '127.0.0.1', 0, 'CI Public User', '', '', '', '', 0, now(), now(), 0)
on duplicate key update
  password = values(password),
  nickname = values(nickname),
  status = 0,
  deleted = 0,
  update_time = now();

insert into litemall_goods
  (id, goods_sn, name, category_id, brand_id, gallery, keywords, brief, is_on_sale, sort_order, pic_url, share_url, is_new, is_hot, unit, counter_price, retail_price, detail, add_time, update_time, deleted)
values
  (1181000, 'PUBLIC-CI-GOODS', 'Public CI Review Governance Product', 0, 0, '["https://example.com/public-ci-product.jpg"]', 'public-ci,review', 'Public seed product for review-governance runtime verification.', 1, 1, 'https://example.com/public-ci-product.jpg', '', 1, 1, 'item', 199.00, 99.00, '<p>Public CI seed product.</p>', now(), now(), 0)
on duplicate key update
  name = values(name),
  is_on_sale = 1,
  deleted = 0,
  update_time = now();

insert into litemall_goods_product
  (id, goods_id, specifications, price, number, url, add_time, update_time, deleted)
values
  (1181000, 1181000, '["standard"]', 99.00, 100, 'https://example.com/public-ci-product.jpg', now(), now(), 0)
on duplicate key update
  goods_id = values(goods_id),
  price = values(price),
  number = values(number),
  deleted = 0,
  update_time = now();

insert into litemall_order
  (id, user_id, order_sn, order_status, aftersale_status, consignee, mobile, address, message, goods_price, freight_price, coupon_price, integral_price, groupon_price, order_price, actual_price, pay_id, pay_time, ship_sn, ship_channel, ship_time, confirm_time, comments, add_time, update_time, deleted)
values
  (190001, 1, 'PUBLICCIORDER0001', 401, 0, 'Public CI User', '13800000000', 'Public CI address', 'normal review seed order', 99.00, 0.00, 0.00, 0.00, 0.00, 99.00, 99.00, 'PUBLIC-CI-PAY-1', now(), 'PUBLIC-CI-SHIP-1', 'PUBLIC-CI', now(), now(), 1, now(), now(), 0),
  (190002, 1, 'PUBLICCIORDER0002', 401, 0, 'Public CI User', '13800000000', 'Public CI address', 'high risk review seed order', 99.00, 0.00, 0.00, 0.00, 0.00, 99.00, 99.00, 'PUBLIC-CI-PAY-2', now(), 'PUBLIC-CI-SHIP-2', 'PUBLIC-CI', now(), now(), 1, now(), now(), 0),
  (190003, 1, 'PUBLICCIORDER0003', 401, 0, 'Public CI User', '13800000000', 'Public CI address', 'AI unavailable recovery seed order', 99.00, 0.00, 0.00, 0.00, 0.00, 99.00, 99.00, 'PUBLIC-CI-PAY-3', now(), 'PUBLIC-CI-SHIP-3', 'PUBLIC-CI', now(), now(), 1, now(), now(), 0)
on duplicate key update
  order_status = 401,
  comments = 1,
  deleted = 0,
  update_time = now();

insert into litemall_order_goods
  (id, order_id, goods_id, goods_name, goods_sn, product_id, number, price, specifications, pic_url, comment, add_time, update_time, deleted)
values
  (190001, 190001, 1181000, 'Public CI Review Governance Product', 'PUBLIC-CI-GOODS', 1181000, 1, 99.00, '["standard"]', 'https://example.com/public-ci-product.jpg', 0, now(), now(), 0),
  (190002, 190002, 1181000, 'Public CI Review Governance Product', 'PUBLIC-CI-GOODS', 1181000, 1, 99.00, '["standard"]', 'https://example.com/public-ci-product.jpg', 0, now(), now(), 0),
  (190003, 190003, 1181000, 'Public CI Review Governance Product', 'PUBLIC-CI-GOODS', 1181000, 1, 99.00, '["standard"]', 'https://example.com/public-ci-product.jpg', 0, now(), now(), 0)
on duplicate key update
  comment = 0,
  deleted = 0,
  update_time = now();
