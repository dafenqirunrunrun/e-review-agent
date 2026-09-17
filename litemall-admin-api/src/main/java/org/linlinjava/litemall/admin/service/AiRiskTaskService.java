package org.linlinjava.litemall.admin.service;

import org.apache.commons.lang3.StringUtils;
import org.linlinjava.litemall.admin.vo.AiRiskHumanReviewRequest;
import org.linlinjava.litemall.admin.vo.AiRiskHumanReviewResult;
import org.linlinjava.litemall.db.domain.LitemallAiOperationLog;
import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;
import org.linlinjava.litemall.db.domain.LitemallReviewAiAnalysis;
import org.linlinjava.litemall.db.service.LitemallAiOperationLogService;
import org.linlinjava.litemall.db.service.LitemallAiReviewRiskTaskService;
import org.linlinjava.litemall.db.service.LitemallReviewAiAnalysisService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.math.BigDecimal;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class AiRiskTaskService {
    private static final BigDecimal LOW_CONFIDENCE = new BigDecimal("0.6000");
    private static final BigDecimal HIGH_NEGATIVE = new BigDecimal("0.6500");

    @Autowired
    private LitemallAiReviewRiskTaskService riskTaskService;

    @Autowired
    private LitemallReviewAiAnalysisService analysisService;

    @Autowired
    private ReviewGovernanceTraceService governanceTraceService;

    @Autowired
    private LitemallAiOperationLogService operationLogService;

    @Autowired
    private AgentPlatformService agentPlatformService;

    @Autowired
    private GovernanceQualityService governanceQualityService;

    public void syncFromAnalyses() {
        List<LitemallReviewAiAnalysis> analyses = analysisService.querySelective(null, null, 1, 10000);
        for (LitemallReviewAiAnalysis analysis : analyses) {
            createTasksForAnalysis(analysis);
        }
    }

    public int createTasksForAnalysis(LitemallReviewAiAnalysis analysis) {
        if (analysis == null || analysis.getId() == null) {
            return 0;
        }
        int created = 0;
        ReviewGovernanceTraceService.ManualReviewDirective directive = governanceTraceService.manualReviewDirective(analysis);
        if (directive != null) {
            created += createTask(analysis, directive.getRiskType(), directive.getRiskLevel(), directive.getHandleNote());
        }
        if ("negative".equals(analysis.getSentimentLabel())) {
            created += createTask(analysis, "negative_review", "high");
        }
        if (analysis.getConfidence() == null || analysis.getConfidence().compareTo(LOW_CONFIDENCE) < 0) {
            created += createTask(analysis, "low_confidence", "medium");
        }
        if (analysis.getNegativeScore() != null && analysis.getNegativeScore().compareTo(HIGH_NEGATIVE) >= 0) {
            created += createTask(analysis, "after_sales_risk", "high");
        }
        if (analysis.getRating() != null && analysis.getRating() <= 2 && !"negative".equals(analysis.getSentimentLabel())) {
            created += createTask(analysis, "rating_conflict", "medium");
        }
        String text = analysis.getReviewText() == null ? "" : analysis.getReviewText();
        if (text.contains("售后") || text.contains("退款") || text.contains("退货") || text.contains("坏了") || text.contains("破损") || text.contains("无法使用")) {
            created += createTask(analysis, "after_sales_risk", "high");
        }
        return created;
    }

    public List<LitemallAiReviewRiskTask> list(String riskLevel, String riskType, String status, Integer page, Integer limit) {
        syncFromAnalyses();
        return riskTaskService.querySelective(riskLevel, riskType, status, page, limit);
    }

    public Map<String, Object> detail(Integer id) {
        LitemallAiReviewRiskTask task = riskTaskService.findById(id);
        LitemallReviewAiAnalysis analysis = task == null || task.getAnalysisId() == null ? null : analysisService.findById(task.getAnalysisId());
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("task", task);
        data.put("analysis", analysis);
        data.put("reviewGovernance", governanceTraceService.extractGovernanceSnapshot(analysis));
        return data;
    }

    public int updateStatus(Integer id, String status, String handler, String handleNote) {
        return riskTaskService.updateStatus(id, status, handler, handleNote);
    }

    public AiRiskHumanReviewResult humanReview(AiRiskHumanReviewRequest request) {
        LitemallAiReviewRiskTask task = riskTaskService.findById(request.getId());
        if (task == null) {
            return null;
        }
        String beforeStatus = task.getStatus();
        String decision = normalizeHumanDecision(request.getHumanDecision());
        String afterStatus = statusForHumanDecision(decision);
        String handler = StringUtils.defaultIfBlank(request.getHandler(), "admin");
        LitemallReviewAiAnalysis analysis = task.getAnalysisId() == null ? null : analysisService.findById(task.getAnalysisId());
        Map<String, Object> governance = governanceTraceService.extractGovernanceSnapshot(analysis);
        String auditNote = buildHumanAuditNote(task, governance, decision, request.getHandleNote());

        AiRiskHumanReviewResult result = new AiRiskHumanReviewResult();
        result.setHumanDecision(decision);
        result.setBeforeStatus(beforeStatus);
        result.setAuditNote(auditNote);

        if (isTerminalStatus(beforeStatus)) {
            result.setAlreadyResolved(true);
            result.setAfterStatus(beforeStatus);
            result.setTask(task);
            return result;
        }

        riskTaskService.updateStatus(task.getId(), afterStatus, handler, trim(auditNote, 512));
        recordHumanReviewLog(task.getId(), beforeStatus, afterStatus, handler, auditNote, decision);
        agentPlatformService.createFeedback(task.getId(), task.getAnalysisId(), task.getSourceType(), task.getSourceId(),
                "human_" + decision, humanDecisionLabel(decision), trim(auditNote, 1024), handler);
        governanceQualityService.recordHumanReview(task, governance, decision, request.getReasonCode());

        LitemallAiReviewRiskTask updated = riskTaskService.findById(task.getId());
        result.setAlreadyResolved(false);
        result.setAfterStatus(afterStatus);
        result.setTask(updated);
        return result;
    }

    public Map<String, Object> summary() {
        syncFromAnalyses();
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("status", riskTaskService.statByStatus());
        data.put("level", riskTaskService.statByLevel());
        return data;
    }

    private int createTask(LitemallReviewAiAnalysis analysis, String riskType, String riskLevel) {
        return createTask(analysis, riskType, riskLevel, null);
    }

    private int createTask(LitemallReviewAiAnalysis analysis, String riskType, String riskLevel, String handleNote) {
        if (riskTaskService.findByAnalysisAndType(analysis.getId(), riskType) != null) {
            return 0;
        }
        LitemallAiReviewRiskTask task = new LitemallAiReviewRiskTask();
        task.setAnalysisId(analysis.getId());
        task.setSourceType(analysis.getSourceType() == null ? "analysis" : analysis.getSourceType());
        task.setSourceId(analysis.getSourceId() == null ? analysis.getId() : analysis.getSourceId());
        task.setReviewId(analysis.getReviewId());
        task.setProductId(analysis.getProductId());
        task.setProductName(analysis.getProductName());
        task.setReviewText(analysis.getReviewText());
        task.setImageUrl(analysis.getImageUrls());
        task.setRiskType(riskType);
        task.setRiskLevel(riskLevel);
        task.setSentimentLabel(analysis.getSentimentLabel());
        task.setConfidence(analysis.getConfidence());
        task.setStatus("pending");
        task.setHandleNote(handleNote);
        riskTaskService.add(task);
        return 1;
    }

    public static boolean isTerminalStatus(String status) {
        return Arrays.asList("closed", "ignored", "replied", "transferred", "processed").contains(status);
    }

    public static String statusForHumanDecision(String humanDecision) {
        if ("no_action".equals(humanDecision)) {
            return "ignored";
        }
        return "closed";
    }

    public static String normalizeHumanDecision(String humanDecision) {
        if ("override".equals(humanDecision) || "no_action".equals(humanDecision)) {
            return humanDecision;
        }
        return "accept_ai_suggestion";
    }

    private void recordHumanReviewLog(Integer riskTaskId, String beforeStatus, String afterStatus, String handler,
                                      String auditNote, String decision) {
        LitemallAiOperationLog log = new LitemallAiOperationLog();
        log.setRiskTaskId(riskTaskId);
        log.setActionType("human_review_" + decision);
        log.setOldStatus(beforeStatus);
        log.setNewStatus(afterStatus);
        log.setOperator(handler);
        log.setNote(trim(auditNote, 512));
        operationLogService.add(log);
    }

    private String buildHumanAuditNote(LitemallAiReviewRiskTask task, Map<String, Object> governance,
                                       String humanDecision, String remark) {
        Map<String, Object> decision = mapValue(governance, "decision");
        String aiDecision = stringValue(decision.get("code"), "-");
        String evidenceStatus = stringValue(governance == null ? null : governance.get("evidenceStatus"), "-");
        String riskTypes = listSummary(governance == null ? null : governance.get("riskTypes"));
        String evidence = evidenceSummary(governance == null ? null : governance.get("evidenceCitations"));
        return trim("人工决定=" + humanDecisionLabel(humanDecision)
                + "；AI建议=" + decisionLabel(aiDecision)
                + "；证据状态=" + evidenceStatusLabel(evidenceStatus)
                + "；风险类型=" + riskTypeListLabel(riskTypes)
                + "；任务风险=" + riskTypeLabel(task.getRiskType())
                + "；依据快照=" + evidence
                + (StringUtils.isBlank(remark) ? "" : "；备注=" + remark), 1024);
    }

    private String evidenceSummary(Object value) {
        if (!(value instanceof List)) {
            return "-";
        }
        StringBuilder builder = new StringBuilder();
        List<?> citations = (List<?>) value;
        for (int i = 0; i < citations.size() && i < 3; i++) {
            Object item = citations.get(i);
            if (!(item instanceof Map)) {
                continue;
            }
            Map<?, ?> citation = (Map<?, ?>) item;
            if (builder.length() > 0) {
                builder.append(" | ");
            }
            builder.append(stringValue(citation.get("id"), "E" + (i + 1)))
                    .append(" ")
                    .append(stringValue(citation.get("sourceName"), "-"))
                    .append(" ")
                    .append(shortHash(stringValue(citation.get("contentHash"), "")));
        }
        return builder.length() == 0 ? "-" : builder.toString();
    }

    private String listSummary(Object value) {
        if (value instanceof List) {
            return StringUtils.join((List<?>) value, ",");
        }
        return stringValue(value, "-");
    }

    public static String decisionLabel(String decision) {
        if ("manual_review".equals(decision)) {
            return "需人工复核";
        }
        if ("suggest_action".equals(decision)) {
            return "建议处理";
        }
        if ("auto_pass".equals(decision)) {
            return "自动通过";
        }
        return StringUtils.defaultIfBlank(decision, "-");
    }

    public static String evidenceStatusLabel(String evidenceStatus) {
        if ("supported".equals(evidenceStatus)) {
            return "证据充分";
        }
        if ("insufficient".equals(evidenceStatus)) {
            return "证据不足";
        }
        if ("mismatch".equals(evidenceStatus)) {
            return "证据不匹配";
        }
        return StringUtils.defaultIfBlank(evidenceStatus, "-");
    }

    public static String riskTypeLabel(String riskType) {
        if ("fake_review".equals(riskType)) {
            return "虚假评价";
        }
        if ("rating_manipulation".equals(riskType)) {
            return "评分操纵";
        }
        if ("paid_review".equals(riskType)) {
            return "有偿评价";
        }
        if ("review_suppression".equals(riskType)) {
            return "压制差评";
        }
        if ("after_sales_risk".equals(riskType)) {
            return "售后争议";
        }
        if ("safety_or_fraud_risk".equals(riskType)) {
            return "安全或欺诈";
        }
        if ("privacy_risk".equals(riskType)) {
            return "隐私风险";
        }
        if ("harassment_or_abuse".equals(riskType)) {
            return "骚扰威胁";
        }
        if ("negative_review".equals(riskType)) {
            return "负向体验";
        }
        if ("normal_review".equals(riskType)) {
            return "普通评价";
        }
        if ("rating_conflict".equals(riskType)) {
            return "评分与内容不一致";
        }
        if ("low_confidence".equals(riskType)) {
            return "低置信度";
        }
        if ("modality_conflict".equals(riskType)) {
            return "图文信息冲突";
        }
        if ("fake_review_suspected".equals(riskType)) {
            return "疑似虚假评价";
        }
        if ("other".equals(riskType)) {
            return "其他风险";
        }
        return StringUtils.defaultIfBlank(riskType, "-");
    }

    public static String riskTypeListLabel(String riskTypes) {
        if (StringUtils.isBlank(riskTypes) || "-".equals(riskTypes)) {
            return "-";
        }
        StringBuilder builder = new StringBuilder();
        String[] parts = riskTypes.split(",");
        for (String part : parts) {
            if (StringUtils.isBlank(part)) {
                continue;
            }
            if (builder.length() > 0) {
                builder.append("、");
            }
            builder.append(riskTypeLabel(part.trim()));
        }
        return builder.length() == 0 ? "-" : builder.toString();
    }

    private Map<String, Object> mapValue(Map<String, Object> source, String key) {
        if (source == null || !(source.get(key) instanceof Map)) {
            return new LinkedHashMap<String, Object>();
        }
        return (Map<String, Object>) source.get(key);
    }

    private String stringValue(Object value, String fallback) {
        return value == null || StringUtils.isBlank(String.valueOf(value)) ? fallback : String.valueOf(value);
    }

    private String shortHash(String hash) {
        if (StringUtils.isBlank(hash)) {
            return "-";
        }
        return hash.length() <= 18 ? hash : hash.substring(0, 18);
    }

    private String humanDecisionLabel(String decision) {
        if ("override".equals(decision)) {
            return "人工改判";
        }
        if ("no_action".equals(decision)) {
            return "无需处置";
        }
        return "接受AI建议";
    }

    private String trim(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength);
    }
}
