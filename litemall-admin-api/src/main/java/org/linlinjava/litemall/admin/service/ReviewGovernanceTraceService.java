package org.linlinjava.litemall.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeResponse;
import org.linlinjava.litemall.db.domain.LitemallReviewAiAnalysis;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class ReviewGovernanceTraceService {
    private final ObjectMapper objectMapper;

    public ReviewGovernanceTraceService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public List<Map<String, Object>> workflowTraceWithGovernance(AiReviewAnalyzeResponse response) {
        List<Map<String, Object>> trace = new ArrayList<Map<String, Object>>();
        Map<String, Object> governance = response == null ? null : response.getReviewGovernance();
        if (governance != null && !governance.isEmpty()) {
            trace.add(governanceSnapshotStep(governance));
        }
        if (response != null && response.getWorkflowTrace() != null) {
            trace.addAll(response.getWorkflowTrace());
        }
        return trace;
    }

    public Map<String, Object> extractGovernanceSnapshot(LitemallReviewAiAnalysis analysis) {
        if (analysis == null || analysis.getWorkflowTraceJson() == null) {
            return null;
        }
        try {
            List<Map<String, Object>> trace = objectMapper.readValue(
                    analysis.getWorkflowTraceJson(),
                    new TypeReference<List<Map<String, Object>>>() {
                    });
            for (Map<String, Object> step : trace) {
                if ("review_governance_snapshot".equals(step.get("node")) && step.get("output") instanceof Map) {
                    return castMap(step.get("output"));
                }
            }
        } catch (Exception ignored) {
            return null;
        }
        return null;
    }

    public ManualReviewDirective manualReviewDirective(LitemallReviewAiAnalysis analysis) {
        Map<String, Object> governance = extractGovernanceSnapshot(analysis);
        if (governance == null) {
            return null;
        }
        Map<String, Object> decision = castMap(governance.get("decision"));
        Map<String, Object> humanReview = castMap(governance.get("humanReview"));
        boolean required = Boolean.TRUE.equals(humanReview.get("required"))
                || "manual_review".equals(String.valueOf(decision.get("code")));
        if (!required) {
            return null;
        }
        List<Map<String, Object>> signals = castList(governance.get("riskSignals"));
        Map<String, Object> firstSignal = signals.isEmpty() ? new HashMap<String, Object>() : signals.get(0);
        String riskType = stringValue(firstSignal.get("riskType"), "manual_review");
        String riskLevel = normalizeSeverity(stringValue(firstSignal.get("severity"), stringValue(decision.get("riskLevel"), "medium")));
        String reason = stringValue(humanReview.get("reason"), stringValue(castMap(governance.get("summary")).get("reason"), "系统建议人工复核"));
        String note = buildManualReviewNote(reason, castList(governance.get("evidenceCitations")));
        return new ManualReviewDirective(riskType, riskLevel, note);
    }

    private Map<String, Object> governanceSnapshotStep(Map<String, Object> governance) {
        Map<String, Object> step = new HashMap<String, Object>();
        step.put("node", "review_governance_snapshot");
        step.put("step", "review_governance_snapshot");
        step.put("agent", "ReviewGovernanceContract");
        step.put("status", "success");
        step.put("message", snapshotMessage(governance));
        step.put("output_summary", snapshotMessage(governance));
        step.put("output", governance);
        return step;
    }

    private String snapshotMessage(Map<String, Object> governance) {
        Map<String, Object> decision = castMap(governance.get("decision"));
        Map<String, Object> summary = castMap(governance.get("summary"));
        String label = stringValue(decision.get("label"), "审核结论");
        String title = stringValue(summary.get("title"), "");
        return title.length() == 0 ? label : label + "：" + title;
    }

    private String buildManualReviewNote(String reason, List<Map<String, Object>> citations) {
        StringBuilder builder = new StringBuilder();
        builder.append("系统建议人工复核：").append(reason);
        if (!citations.isEmpty()) {
            builder.append(" | 依据：");
            int count = Math.min(2, citations.size());
            for (int i = 0; i < count; i++) {
                if (i > 0) {
                    builder.append("；");
                }
                Map<String, Object> citation = citations.get(i);
                builder.append(stringValue(citation.get("id"), "E" + (i + 1)))
                        .append(" ")
                        .append(stringValue(citation.get("sourceName"), "未命名来源"));
            }
        }
        return builder.toString();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castMap(Object value) {
        if (value instanceof Map) {
            return (Map<String, Object>) value;
        }
        return new HashMap<String, Object>();
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> castList(Object value) {
        if (value instanceof List) {
            return (List<Map<String, Object>>) value;
        }
        return new ArrayList<Map<String, Object>>();
    }

    private static String normalizeSeverity(String value) {
        if ("高".equals(value) || "high".equalsIgnoreCase(value)) {
            return "high";
        }
        if ("低".equals(value) || "low".equalsIgnoreCase(value)) {
            return "low";
        }
        return "medium";
    }

    private static String stringValue(Object value, String fallback) {
        String text = value == null ? "" : String.valueOf(value);
        return text.length() == 0 ? fallback : text;
    }

    public static class ManualReviewDirective {
        private final String riskType;
        private final String riskLevel;
        private final String handleNote;

        public ManualReviewDirective(String riskType, String riskLevel, String handleNote) {
            this.riskType = riskType;
            this.riskLevel = riskLevel;
            this.handleNote = handleNote;
        }

        public String getRiskType() {
            return riskType;
        }

        public String getRiskLevel() {
            return riskLevel;
        }

        public String getHandleNote() {
            return handleNote;
        }
    }
}
