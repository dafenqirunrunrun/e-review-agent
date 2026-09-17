from scripts.run_step242i_business_evidence_dev import (
    BUSINESS_REQUIREMENTS,
    MAX_FINAL_EVIDENCE,
    audit_case,
    requirement_for_case,
)


def test_business_evidence_contract_covers_each_after_sales_dev_topic() -> None:
    assert len(BUSINESS_REQUIREMENTS) == 20
    assert all(requirement.clauseGroups for requirement in BUSINESS_REQUIREMENTS.values())
    assert all(group.alternatives for requirement in BUSINESS_REQUIREMENTS.values() for group in requirement.clauseGroups)


def test_business_audit_accepts_a_semantically_equivalent_official_clause_not_only_exact_qrels_target() -> None:
    case = _case("unreasonable_delay")
    result, chunk_index = _realistic_result("对消费者提出的退货要求故意拖延或者无理拒绝。", "五十六")

    audit = audit_case(case, result, chunk_index)

    assert audit["verdict"] == "sufficient"
    assert audit["selectedEvidenceCount"] <= MAX_FINAL_EVIDENCE


def test_business_audit_does_not_mark_generic_policy_as_sufficient() -> None:
    case = _case("after_sales_terms")
    result = {
        "abstained": False,
        "top5": [
            {
                "chunkId": "generic-return-rule",
                "sourceName": "网络购买商品七日无理由退货暂行办法",
                "sourceUrl": "https://example.test/return-rule",
                "clauseId": "四",
                "contentHash": "hash-4",
            }
        ],
    }
    chunk_index = {"generic-return-rule": {"documentId": "cn_network_seven_day_return_rules"}}

    audit = audit_case(case, result, chunk_index)

    assert audit["verdict"] == "insufficient"


def test_business_requirement_uses_the_actual_review_claim_when_a_topic_paraphrase_drops_property_damage() -> None:
    requirement = requirement_for_case("civil_remedy", "卖家提供的商品有问题，我要求换货或退款却被拒绝。")

    assert requirement is not None
    assert requirement.clauseGroups[0].alternatives[0] == ("cn_consumer_rights_protection_law", "二十四")


def _realistic_result(text: str, clause: str = "二十六"):
    from hashlib import sha256

    chunk = {
        "documentId": "cn_consumer_rights_protection_law",
        "sourceName": "消费者权益保护法",
        "sourceUrl": "https://www.samr.gov.cn/policy",
        "sectionPath": ["消费者权益保护法", clause],
        "clauseId": clause,
        "text": text,
        "contentHash": sha256(text.encode()).hexdigest(),
    }
    hit = {key: chunk[key] for key in ("sourceName", "sourceUrl", "sectionPath", "clauseId", "contentHash")}
    hit["chunkId"] = "test-chunk"
    return {"top5": [hit]}, {"test-chunk": chunk}


def test_same_clause_number_without_relevant_text_is_not_sufficient():
    result, chunks = _realistic_result("第二十六条（续）其内容无效。")
    assert audit_case(_case("after_sales_terms"), result, chunks)["verdict"] == "insufficient"


def test_source_or_hash_mismatch_rejects_citation():
    result, chunks = _realistic_result("格式条款应以显著方式提请消费者注意。")
    result["top5"][0]["contentHash"] = "fabricated"
    audit = audit_case(_case("after_sales_terms"), result, chunks)
    assert not audit["citationValid"]
    assert audit["verdict"] != "sufficient"


def test_evidence_bundle_cannot_silently_trim_overflow():
    result, chunks = _realistic_result("格式条款应以显著方式提请消费者注意。")
    result["top5"] *= 4
    audit = audit_case(_case("after_sales_terms"), result, chunks)
    assert audit["selectedEvidenceCount"] == 4
    assert audit["verdict"] != "sufficient"


def test_relevant_text_with_verified_citation_is_sufficient():
    result, chunks = _realistic_result("格式条款应以显著方式提请消费者注意。")
    audit = audit_case(_case("after_sales_terms"), result, chunks)
    assert audit["citationValid"]
    assert audit["verdict"] == "sufficient"


def _case(topic: str):
    return type(
        "Case",
        (),
        {"caseId": f"case-{topic}", "metadata": {"topic": topic}, "noAnswer": False, "reviewText": "测试评论", "riskTypes": ["after_sales_risk"]},
    )()
