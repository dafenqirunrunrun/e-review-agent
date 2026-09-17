package org.linlinjava.litemall.admin;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Test;
import org.linlinjava.litemall.admin.service.ReviewGovernanceTraceService;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeResponse;
import org.linlinjava.litemall.db.domain.LitemallReviewAiAnalysis;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.*;

public class ReviewGovernanceTraceServiceTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private final ReviewGovernanceTraceService service = new ReviewGovernanceTraceService(mapper);

    @Test
    public void minimalGovernanceSnapshotAndManualReviewDirective() throws Exception {
        AiReviewAnalyzeResponse response = new AiReviewAnalyzeResponse();
        response.setReviewGovernance(manualReviewGovernance());
        response.setWorkflowTrace(Arrays.<Map<String, Object>>asList(step("intent_router")));

        List<Map<String, Object>> trace = service.workflowTraceWithGovernance(response);
        assertEquals("review_governance_snapshot", trace.get(0).get("node"));
        assertEquals("intent_router", trace.get(1).get("node"));

        LitemallReviewAiAnalysis analysis = new LitemallReviewAiAnalysis();
        analysis.setWorkflowTraceJson(mapper.writeValueAsString(trace));

        Map<String, Object> snapshot = service.extractGovernanceSnapshot(analysis);
        assertNotNull(snapshot);
        assertEquals("review-governance-v1", snapshot.get("schemaVersion"));

        ReviewGovernanceTraceService.ManualReviewDirective directive = service.manualReviewDirective(analysis);
        assertNotNull(directive);
        assertEquals("review_suppression", directive.getRiskType());
        assertEquals("high", directive.getRiskLevel());
        assertTrue(directive.getHandleNote().contains("系统建议人工复核"));
        assertTrue(directive.getHandleNote().contains("电子商务法"));
    }

    @Test
    public void autoPassGovernanceDoesNotCreateManualDirective() throws Exception {
        AiReviewAnalyzeResponse response = new AiReviewAnalyzeResponse();
        Map<String, Object> governance = manualReviewGovernance();
        map(governance, "decision").put("code", "auto_pass");
        map(governance, "decision").put("label", "自动通过");
        map(governance, "humanReview").put("required", Boolean.FALSE);
        response.setReviewGovernance(governance);

        LitemallReviewAiAnalysis analysis = new LitemallReviewAiAnalysis();
        analysis.setWorkflowTraceJson(mapper.writeValueAsString(service.workflowTraceWithGovernance(response)));

        assertNull(service.manualReviewDirective(analysis));
    }

    @Test
    public void governanceSnapshotKeepsPolicyEvidenceForReviewDetail() throws Exception {
        AiReviewAnalyzeResponse response = new AiReviewAnalyzeResponse();
        Map<String, Object> governance = manualReviewGovernance();
        governance.put("evidenceStatus", "mismatch");
        governance.put("reflectionReason", "政策依据未覆盖全部风险类型，需要人工复核。");
        governance.put("requiresHumanReview", Boolean.TRUE);
        response.setReviewGovernance(governance);

        LitemallReviewAiAnalysis analysis = new LitemallReviewAiAnalysis();
        analysis.setWorkflowTraceJson(mapper.writeValueAsString(service.workflowTraceWithGovernance(response)));

        Map<String, Object> snapshot = service.extractGovernanceSnapshot(analysis);
        assertEquals("mismatch", snapshot.get("evidenceStatus"));
        assertEquals(Boolean.TRUE, snapshot.get("requiresHumanReview"));
        assertEquals("政策依据未覆盖全部风险类型，需要人工复核。", snapshot.get("reflectionReason"));
        List<Map<String, Object>> citations = castList(snapshot.get("evidenceCitations"));
        assertEquals("E1", citations.get(0).get("id"));
        assertEquals("https://example.test/law", citations.get(0).get("sourceUrl"));
    }

    private Map<String, Object> manualReviewGovernance() {
        Map<String, Object> governance = new HashMap<String, Object>();
        governance.put("schemaVersion", "review-governance-v1");
        governance.put("decision", mapOf(
                "code", "manual_review",
                "label", "需人工复核",
                "riskLevel", "high",
                "confidence", 0.82));
        governance.put("summary", mapOf(
                "title", "疑似压制差评",
                "reason", "评论涉及删除差评后再退款。"));
        governance.put("humanReview", mapOf(
                "required", Boolean.TRUE,
                "reason", "风险较高，需要审核员查看订单沟通记录。"));
        governance.put("riskSignals", Arrays.asList(mapOf(
                "riskType", "review_suppression",
                "label", "压制差评",
                "severity", "高")));
        governance.put("evidenceCitations", Arrays.asList(mapOf(
                "id", "E1",
                "sourceName", "电子商务法",
                "sourceUrl", "https://example.test/law")));
        return governance;
    }

    private Map<String, Object> step(String node) {
        Map<String, Object> step = new HashMap<String, Object>();
        step.put("node", node);
        step.put("status", "success");
        return step;
    }

    private Map<String, Object> mapOf(Object... values) {
        Map<String, Object> map = new HashMap<String, Object>();
        for (int i = 0; i < values.length; i += 2) {
            map.put(String.valueOf(values[i]), values[i + 1]);
        }
        return map;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> map(Map<String, Object> root, String key) {
        return (Map<String, Object>) root.get(key);
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> castList(Object value) {
        return (List<Map<String, Object>>) value;
    }
}
