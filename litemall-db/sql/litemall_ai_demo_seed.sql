-- E-Review Agent demo seed data for thesis defense and screenshots.
-- Safe to rerun: it removes only rows with review_id like 'EREVIEW-DEMO-%'
-- and demo-review rows with nickname = 'demo-seed'.

delete from litemall_ai_operation_log
where risk_task_id in (
  select id from litemall_ai_review_risk_task
  where review_id like 'EREVIEW-DEMO-%'
);

delete from litemall_ai_review_risk_task
where review_id like 'EREVIEW-DEMO-%';

delete from litemall_review_ai_analysis
where review_id like 'EREVIEW-DEMO-%';

delete from litemall_ai_demo_review
where nickname = 'demo-seed';

insert into litemall_ai_demo_review
  (product_id, product_name, category_name, nickname, rating, review_text, image_url, analysis_status, created_time, updated_time, deleted)
values
  (1006002, 'E-Review Cup', 'Home', 'demo-seed', 5, 'Great heat preservation, refined appearance, and fast delivery.', 'https://example.com/demo-positive.jpg', 'analyzed', date_sub(now(), interval 6 day), date_sub(now(), interval 6 day), 0),
  (1006003, 'E-Review Backpack', 'Bags', 'demo-seed', 3, 'The capacity is acceptable, the workmanship is average, and the overall experience meets expectations.', 'https://example.com/demo-neutral.jpg', 'analyzed', date_sub(now(), interval 5 day), date_sub(now(), interval 5 day), 0),
  (1006004, 'E-Review Earbuds', 'Digital', 'demo-seed', 1, 'The earbuds have obvious noise, the connection often drops, and the experience is poor.', 'https://example.com/demo-negative.jpg', 'analyzed', date_sub(now(), interval 4 day), date_sub(now(), interval 4 day), 0),
  (1006005, 'E-Review Jacket', 'Apparel', 'demo-seed', 5, 'The text says very satisfied, but the uploaded image shows loose seams and stains.', 'https://example.com/demo-conflict.jpg', 'analyzed', date_sub(now(), interval 3 day), date_sub(now(), interval 3 day), 0),
  (1006006, 'E-Review Lamp', 'Appliance', 'demo-seed', 3, 'It is hard to say whether it is good or bad; the brightness is sometimes unstable and maybe I do not know how to adjust it.', 'https://example.com/demo-low-confidence.jpg', 'analyzed', date_sub(now(), interval 2 day), date_sub(now(), interval 2 day), 0),
  (1006007, 'E-Review Desk', 'Furniture', 'demo-seed', 1, 'The desk corner was broken. I requested a refund and after-sales support, but no one replied.', 'https://example.com/demo-after-sales.jpg', 'analyzed', date_sub(now(), interval 1 day), date_sub(now(), interval 1 day), 0);

insert into litemall_review_ai_analysis
  (review_id, product_id, product_name, review_text, rating, image_urls, sentiment_label, confidence,
   positive_score, neutral_score, negative_score, evidence_json, similar_cases_json, agent_suggestion_json,
   workflow_trace_json, add_time, update_time, deleted)
values
  (
    'EREVIEW-DEMO-POSITIVE', 1006002, 'E-Review Cup',
    'Great heat preservation, refined appearance, and fast delivery.', 5, '["https://example.com/demo-positive.jpg"]',
    'positive', 0.9400, 0.9200, 0.0600, 0.0200,
    '{"keywords":["great heat preservation","refined appearance","fast delivery"],"risk":"none"}',
    '[{"case":"high satisfaction positive review","action":"use as product selling-point material"}]',
    '{"customer_reply":"Thank you for your recognition. We look forward to serving you again.","operation_advice":"Extract heat preservation, appearance, and delivery as product-page highlights.","after_sales_suggestion":"No after-sales action is required.","notice":"AI suggestion is for reference only. Please combine it with business judgment."}',
    '{"steps":["parse_review","sentiment_positive","risk_none"]}',
    date_sub(now(), interval 6 day), date_sub(now(), interval 6 day), 0
  ),
  (
    'EREVIEW-DEMO-NEUTRAL', 1006003, 'E-Review Backpack',
    'The capacity is acceptable, the workmanship is average, and the overall experience meets expectations.', 3, '["https://example.com/demo-neutral.jpg"]',
    'neutral', 0.8100, 0.1800, 0.7000, 0.1200,
    '{"keywords":["capacity acceptable","workmanship average"],"risk":"watch"}',
    '[{"case":"neutral experience review","action":"watch workmanship-related feedback"}]',
    '{"customer_reply":"Thank you for your feedback. We will continue to improve workmanship details.","operation_advice":"Monitor whether average-workmanship comments appear repeatedly.","after_sales_suggestion":"No immediate after-sales action is required.","notice":"AI suggestion is for reference only. Please combine it with business judgment."}',
    '{"steps":["parse_review","sentiment_neutral","risk_watch"]}',
    date_sub(now(), interval 5 day), date_sub(now(), interval 5 day), 0
  ),
  (
    'EREVIEW-DEMO-NEGATIVE', 1006004, 'E-Review Earbuds',
    'The earbuds have obvious noise, the connection often drops, and the experience is poor.', 1, '["https://example.com/demo-negative.jpg"]',
    'negative', 0.9100, 0.0300, 0.0900, 0.8800,
    '{"keywords":["obvious noise","connection drops","poor experience"],"risk":"negative_review"}',
    '[{"case":"digital accessory quality complaint","action":"customer service should contact user"}]',
    '{"customer_reply":"Sorry for the poor experience. Please provide the order information and we will verify it quickly.","operation_advice":"Check whether this batch has repeated connection-stability complaints.","after_sales_suggestion":"Suggest after-sales inspection or replacement.","notice":"AI suggestion is for reference only. Please combine it with business judgment."}',
    '{"steps":["parse_review","sentiment_negative","risk_high"]}',
    date_sub(now(), interval 4 day), date_sub(now(), interval 4 day), 0
  ),
  (
    'EREVIEW-DEMO-CONFLICT', 1006005, 'E-Review Jacket',
    'The text says very satisfied, but the uploaded image shows loose seams and stains.', 5, '["https://example.com/demo-conflict.jpg"]',
    'neutral', 0.6200, 0.3600, 0.4300, 0.2100,
    '{"keywords":["text satisfied","image loose seams","image stains"],"risk":"image_text_conflict"}',
    '[{"case":"image-text conflict review","action":"manual image review recommended"}]',
    '{"customer_reply":"Thank you for the feedback. We will verify the image evidence carefully.","operation_advice":"Text and image signals conflict. Manual image review is recommended.","after_sales_suggestion":"If the image is valid, guide the user to after-sales support.","notice":"AI suggestion is for reference only. Please combine it with business judgment."}',
    '{"steps":["parse_text","inspect_image_hint","conflict_detected"]}',
    date_sub(now(), interval 3 day), date_sub(now(), interval 3 day), 0
  ),
  (
    'EREVIEW-DEMO-LOWCONF', 1006006, 'E-Review Lamp',
    'It is hard to say whether it is good or bad; the brightness is sometimes unstable and maybe I do not know how to adjust it.', 3, '["https://example.com/demo-low-confidence.jpg"]',
    'neutral', 0.4200, 0.2800, 0.3900, 0.3300,
    '{"keywords":["hard to say","sometimes unstable","maybe adjustment issue"],"risk":"low_confidence"}',
    '[{"case":"ambiguous low-confidence review","action":"manual review recommended"}]',
    '{"customer_reply":"Thank you for the feedback. If the issue continues, customer service can help with setup.","operation_advice":"The expression is ambiguous. Manual review is recommended before risk escalation.","after_sales_suggestion":"Provide usage guidance first.","notice":"AI suggestion is for reference only. Please combine it with business judgment."}',
    '{"steps":["parse_review","ambiguous_expression","low_confidence"]}',
    date_sub(now(), interval 2 day), date_sub(now(), interval 2 day), 0
  ),
  (
    'EREVIEW-DEMO-AFTERSALES', 1006007, 'E-Review Desk',
    'The desk corner was broken. I requested a refund and after-sales support, but no one replied.', 1, '["https://example.com/demo-after-sales.jpg"]',
    'negative', 0.9600, 0.0100, 0.0500, 0.9400,
    '{"keywords":["broken corner","refund requested","after-sales no reply"],"risk":"after_sales_risk"}',
    '[{"case":"after-sales response risk","action":"handle with high priority"}]',
    '{"customer_reply":"We are sorry for the inconvenience. An after-sales specialist will follow up immediately.","operation_advice":"This review involves refund and response delay. Escalate with priority.","after_sales_suggestion":"Transfer to after-sales supervisor and track SLA.","notice":"AI suggestion is for reference only. Please combine it with business judgment."}',
    '{"steps":["parse_review","sentiment_negative","after_sales_risk_high"]}',
    date_sub(now(), interval 1 day), date_sub(now(), interval 1 day), 0
  );

insert into litemall_ai_review_risk_task
  (analysis_id, source_type, source_id, review_id, product_id, product_name, review_text, image_url,
   risk_type, risk_level, sentiment_label, confidence, conflict_score, status, handler, handle_note,
   created_time, updated_time, deleted)
select id, 'seed', id, review_id, product_id, product_name, review_text, image_urls,
       'negative_review', 'high', sentiment_label, confidence, 0.8800, 'pending', null, null,
       add_time, update_time, 0
from litemall_review_ai_analysis
where review_id = 'EREVIEW-DEMO-NEGATIVE';

insert into litemall_ai_review_risk_task
  (analysis_id, source_type, source_id, review_id, product_id, product_name, review_text, image_url,
   risk_type, risk_level, sentiment_label, confidence, conflict_score, status, handler, handle_note,
   created_time, updated_time, deleted)
select id, 'seed', id, review_id, product_id, product_name, review_text, image_urls,
       'image_text_conflict', 'medium', sentiment_label, confidence, 0.7600, 'viewed', 'demo-admin', 'Image-text conflict viewed; manual review is pending.',
       add_time, update_time, 0
from litemall_review_ai_analysis
where review_id = 'EREVIEW-DEMO-CONFLICT';

insert into litemall_ai_review_risk_task
  (analysis_id, source_type, source_id, review_id, product_id, product_name, review_text, image_url,
   risk_type, risk_level, sentiment_label, confidence, conflict_score, status, handler, handle_note,
   created_time, updated_time, deleted)
select id, 'seed', id, review_id, product_id, product_name, review_text, image_urls,
       'low_confidence', 'medium', sentiment_label, confidence, 0.5800, 'replied', 'demo-admin', 'User has been replied to and asked for more information.',
       add_time, update_time, 0
from litemall_review_ai_analysis
where review_id = 'EREVIEW-DEMO-LOWCONF';

insert into litemall_ai_review_risk_task
  (analysis_id, source_type, source_id, review_id, product_id, product_name, review_text, image_url,
   risk_type, risk_level, sentiment_label, confidence, conflict_score, status, handler, handle_note,
   created_time, updated_time, deleted)
select id, 'seed', id, review_id, product_id, product_name, review_text, image_urls,
       'after_sales_risk', 'high', sentiment_label, confidence, 0.9300, 'transferred', 'demo-admin', 'Transferred to after-sales supervisor for refund and damage handling.',
       add_time, update_time, 0
from litemall_review_ai_analysis
where review_id = 'EREVIEW-DEMO-AFTERSALES';

insert into litemall_ai_review_risk_task
  (analysis_id, source_type, source_id, review_id, product_id, product_name, review_text, image_url,
   risk_type, risk_level, sentiment_label, confidence, conflict_score, status, handler, handle_note,
   created_time, updated_time, deleted)
select id, 'seed', id, review_id, product_id, product_name, review_text, image_urls,
       'quality_watch', 'low', sentiment_label, confidence, 0.2600, 'closed', 'demo-admin', 'Neutral workmanship watch item has been closed.',
       add_time, update_time, 0
from litemall_review_ai_analysis
where review_id = 'EREVIEW-DEMO-NEUTRAL';

insert into litemall_ai_operation_log
  (risk_task_id, action_type, old_status, new_status, operator, note, created_time)
select id, 'mark_viewed', 'pending', 'viewed', 'demo-admin', 'Demo seed: image-text conflict task viewed.', date_sub(now(), interval 3 day)
from litemall_ai_review_risk_task
where review_id = 'EREVIEW-DEMO-CONFLICT';

insert into litemall_ai_operation_log
  (risk_task_id, action_type, old_status, new_status, operator, note, created_time)
select id, 'mark_replied', 'viewed', 'replied', 'demo-admin', 'Demo seed: low-confidence review replied.', date_sub(now(), interval 2 day)
from litemall_ai_review_risk_task
where review_id = 'EREVIEW-DEMO-LOWCONF';

insert into litemall_ai_operation_log
  (risk_task_id, action_type, old_status, new_status, operator, note, created_time)
select id, 'transfer_after_sales', 'pending', 'transferred', 'demo-admin', 'Demo seed: after-sales risk transferred.', date_sub(now(), interval 1 day)
from litemall_ai_review_risk_task
where review_id = 'EREVIEW-DEMO-AFTERSALES';

insert into litemall_ai_operation_log
  (risk_task_id, action_type, old_status, new_status, operator, note, created_time)
select id, 'close_task', 'replied', 'closed', 'demo-admin', 'Demo seed: neutral watch item closed.', now()
from litemall_ai_review_risk_task
where review_id = 'EREVIEW-DEMO-NEUTRAL';
