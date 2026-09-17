from __future__ import annotations

from app.policy_rag.parser import PolicyDocumentParser


def seed_policy_documents():
    parser = PolicyDocumentParser()
    return [
        parser.parse_text(
            source_id="ftc_16_cfr_part_465",
            source_url="https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-465",
            source_name="16 CFR Part 465",
            source_type="regulation",
            jurisdiction="US",
            language="en",
            license_class="public_domain",
            content="""
# Part 465 Consumer Reviews and Testimonials
## § 465.2 Fake or False Consumer Reviews
Fake, fabricated, or misleading consumer reviews can distort customer choice and should be treated as review integrity risk.

## § 465.4 Buying Positive or Negative Consumer Reviews
Paid review incentives, compensation, cashback benefits, or benefits tied to positive or negative review sentiment are rating manipulation evidence.

## § 465.7 Review Suppression
Suppressing, removing, or threatening consumers over unfavorable reviews is review suppression evidence.
""",
        ),
        parser.parse_text(
            source_id="google_maps_ugc_policy",
            source_url="https://support.google.com/contributionpolicy/answer/7400114?hl=en",
            source_name="Google Maps User Generated Content Policy",
            source_type="platform_policy",
            jurisdiction="platform",
            language="en",
            content="""
# Google Maps User Generated Content Policy
## Fake engagement
Content intended to manipulate ratings, including fake engagement, incentives, or conflicts of interest, is policy evidence for rating manipulation.

## Personal information
Reviews that expose personal information or privacy-sensitive data are privacy risk evidence.

## Harassment
Threats, harassment, or abusive content in reviews should be routed as harassment or abuse risk.
""",
        ),
        parser.parse_text(
            source_id="amazon_customer_reviews_guidelines",
            source_url="https://www.amazon.com/gp/help/customer/display.html?nodeId=G3UA5WC5S5UUKB5G",
            source_name="Amazon Customer Reviews Guidelines",
            source_type="platform_policy",
            jurisdiction="platform",
            language="en",
            content="""
# Amazon Customer Reviews Guidelines
## Authentic experience
Customer reviews should reflect authentic customer experience rather than promotional, fake, or misleading content.

## Promotional and compensated reviews
Promotional reviews, compensation-driven reviews, and undisclosed incentives are evidence for fake review or rating manipulation risk.
""",
        ),
        parser.parse_text(
            source_id="cn_ecommerce_law_review_credit",
            source_url="https://www.mofcom.gov.cn/zhrmghgdzswf/fg/art/2018/art_cc9187dd95cd40158552d78a610e8c29.html",
            source_name="中华人民共和国电子商务法",
            source_type="law",
            jurisdiction="CN",
            language="zh",
            license_class="public_reference_restricted",
            content="""
# 中华人民共和国电子商务法
## 信用评价制度
电子商务平台经营者应当建立健全信用评价制度，公示信用评价规则。

## 不得删除评价
平台不得删除消费者对其平台内销售的商品或者提供的服务的评价。删除差评、屏蔽评价、压制负面反馈可作为 review_suppression 风险证据。
""",
        ),
        parser.parse_text(
            source_id="cn_online_transaction_supervision",
            source_url="https://www.moj.gov.cn/pub/sfbgw/flfggz/flfggzbmgz/202104/t20210423_357848.html",
            source_name="网络交易监督管理办法",
            source_type="regulation",
            jurisdiction="CN",
            language="zh",
            license_class="public_reference_restricted",
            content="""
# 网络交易监督管理办法
## 虚构交易与编造评价
虚构交易、编造用户评价、误导性展示评价信息属于评价治理风险，可作为 fake_review 和 rating_manipulation 证据。

## 售后与消费者权益
涉及退款、退货、破损、商品质量和售后争议的评论，应结合消费者权益和售后规则进入人工复核或风险任务。
""",
        ),
    ]
