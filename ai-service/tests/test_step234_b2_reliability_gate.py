from scripts.run_step234_b2_reliability_gate import evaluate_gate, latency_summary, summarize_response


def test_step234_gate_accepts_safe_reranker_fallback():
    readiness = {
        "status": "ready",
        "policyRag": {
            "retrievalMode": "hybrid",
            "reranker": {"status": "ready", "loaded": True},
        },
    }
    normal = {"route": "low_touch", "rerankerRuns": 0, "citationCount": 0}
    levels = [
        {
            "apiErrors": 0,
            "highRiskAutoPass": 0,
            "citationInvalid": 0,
            "fallbackSafe": True,
            "rerankerRuns": 4,
            "rerankerFallbacks": 2,
            "denseCacheMissDelta": 4,
            "requestCount": 4,
        }
    ]

    checks = evaluate_gate(readiness, normal, levels)

    assert all(checks.values())


def test_step234_gate_rejects_high_risk_auto_pass():
    readiness = {
        "status": "ready",
        "policyRag": {
            "retrievalMode": "hybrid",
            "reranker": {"status": "ready", "loaded": True},
        },
    }
    normal = {"route": "low_touch", "rerankerRuns": 0, "citationCount": 0}
    levels = [
        {
            "apiErrors": 0,
            "highRiskAutoPass": 1,
            "citationInvalid": 0,
            "fallbackSafe": True,
            "rerankerRuns": 1,
            "denseCacheMissDelta": 1,
            "requestCount": 1,
        }
    ]

    assert evaluate_gate(readiness, normal, levels)["noHighRiskAutoPass"] is False


def test_step234_gate_rejects_cached_queries_that_skip_dense_execution():
    readiness = {
        "status": "ready",
        "policyRag": {
            "retrievalMode": "hybrid",
            "reranker": {"status": "ready", "loaded": True},
        },
    }
    normal = {"route": "low_touch", "rerankerRuns": 0, "citationCount": 0}
    levels = [
        {
            "apiErrors": 0,
            "highRiskAutoPass": 0,
            "citationInvalid": 0,
            "fallbackSafe": True,
            "rerankerRuns": 4,
            "denseCacheMissDelta": 0,
            "requestCount": 4,
        }
    ]

    assert evaluate_gate(readiness, normal, levels)["allRiskQueriesExecuteDense"] is False


def test_step234_summary_tracks_business_safety_without_raw_text():
    response = {
        "review_id": "risk-1",
        "route_decision": "human_review",
        "risk_types": ["rating_manipulation"],
        "evidence_status": "supported",
        "requires_human_review": True,
        "extra": {
            "agentic": {
                "route": "governance_required",
                "evidenceBundle": {
                    "citations": [
                        {
                            "sourceName": "Policy",
                            "sourceUrl": "https://example.test/policy",
                            "sectionPath": ["Clause 1"],
                            "contentHash": "abc123def456",
                            "snippet": "Short citation.",
                        }
                    ]
                },
            },
            "latencyBreakdown": {"totalMs": 1200, "embeddingComputeMs": 400, "policyRerankerMs": 600},
        },
        "workflow_trace": [
            {
                "node": "policy_evidence_rerank",
                "output": {"effectiveMode": "rrf_fallback", "fallbackUsed": True},
            }
        ],
    }

    summary = summarize_response("risk", response, 1300)

    assert summary["citationValid"] is True
    assert summary["rerankerFallbacks"] == 1
    assert summary["safeFromAutoPass"] is True
    assert "review_text" not in summary
    assert latency_summary([10, 20, 30])["p95Ms"] == 30
