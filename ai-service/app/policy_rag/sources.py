from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicySourceSpec:
    sourceId: str
    sourceUrl: str
    sourceName: str
    sourceType: str
    jurisdiction: str
    language: str
    licenseClass: str = "public_reference_restricted"
    fileName: str = ""
    fetchUrl: str = ""


REAL_POLICY_SOURCES = [
    PolicySourceSpec(
        sourceId="ftc_16_cfr_part_465",
        sourceUrl="https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-465",
        sourceName="16 CFR Part 465",
        sourceType="regulation",
        jurisdiction="US",
        language="en",
        licenseClass="public_domain",
        fileName="ftc_16_cfr_part_465.xml",
        fetchUrl="https://www.ecfr.gov/api/versioner/v1/full/2026-09-03/title-16.xml?part=465",
    ),
    PolicySourceSpec(
        sourceId="cn_ecommerce_law_review_credit",
        sourceUrl="https://www.mofcom.gov.cn/zhrmghgdzswf/fg/art/2018/art_cc9187dd95cd40158552d78a610e8c29.html",
        sourceName="中华人民共和国电子商务法",
        sourceType="law",
        jurisdiction="CN",
        language="zh",
        fileName="cn_ecommerce_law_review_credit.html",
    ),
    PolicySourceSpec(
        sourceId="cn_consumer_rights_protection_law",
        sourceUrl="https://www.samr.gov.cn/zfjcj/tzgg/art/2023/art_615af9ed6bcd4974bf853dd2e02bc663.html",
        sourceName="中华人民共和国消费者权益保护法",
        sourceType="law",
        jurisdiction="CN",
        language="zh",
        fileName="cn_consumer_rights_protection_law.pdf",
        fetchUrl="https://sjfg.samr.gov.cn/law/file/pdf/3235243/1663323673721.pdf",
    ),
    PolicySourceSpec(
        sourceId="cn_online_return_without_reason",
        sourceUrl="https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/fgs/art/2023/art_26ca8fe29e184edd899fa0a7a060d935.html",
        sourceName="网络购买商品七日无理由退货暂行办法",
        sourceType="regulation",
        jurisdiction="CN",
        language="zh",
        fileName="cn_online_return_without_reason.pdf",
        fetchUrl="https://sjfg.samr.gov.cn/law/file/pdf/3235243/1663578568290.pdf",
    ),
    PolicySourceSpec(
        sourceId="cn_online_transaction_supervision",
        sourceUrl="https://www.moj.gov.cn/pub/sfbgw/flfggz/flfggzbmgz/202104/t20210423_357848.html",
        sourceName="网络交易监督管理办法",
        sourceType="regulation",
        jurisdiction="CN",
        language="zh",
        fileName="cn_online_transaction_supervision.html",
    ),
    PolicySourceSpec(
        sourceId="google_maps_ugc_policy",
        sourceUrl="https://support.google.com/contributionpolicy/answer/7400114?hl=en",
        sourceName="Google Maps User Generated Content Policy",
        sourceType="platform_policy",
        jurisdiction="platform",
        language="en",
        fileName="google_maps_ugc_policy.html",
    ),
    PolicySourceSpec(
        sourceId="amazon_customer_reviews_guidelines",
        sourceUrl="https://www.amazon.com/gp/help/customer/display.html?nodeId=G3UA5WC5S5UUKB5G",
        sourceName="Amazon Customer Reviews Guidelines",
        sourceType="platform_policy",
        jurisdiction="platform",
        language="en",
        fileName="amazon_customer_reviews_guidelines.html",
    ),
]
