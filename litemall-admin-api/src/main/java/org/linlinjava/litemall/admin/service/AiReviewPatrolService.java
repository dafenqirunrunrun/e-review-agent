package org.linlinjava.litemall.admin.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeRequest;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeResponse;
import org.linlinjava.litemall.db.domain.LitemallAiDemoReview;
import org.linlinjava.litemall.db.domain.LitemallAiPatrolLog;
import org.linlinjava.litemall.db.domain.LitemallComment;
import org.linlinjava.litemall.db.domain.LitemallGoods;
import org.linlinjava.litemall.db.domain.LitemallReviewAiAnalysis;
import org.linlinjava.litemall.db.service.LitemallAiDemoReviewService;
import org.linlinjava.litemall.db.service.LitemallAiCaseKnowledgeService;
import org.linlinjava.litemall.db.service.LitemallAiPatrolLogService;
import org.linlinjava.litemall.db.service.LitemallCommentService;
import org.linlinjava.litemall.db.service.LitemallGoodsService;
import org.linlinjava.litemall.db.service.LitemallReviewAiAnalysisService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

@Service
public class AiReviewPatrolService {
    @Autowired
    private LitemallAiDemoReviewService demoReviewService;

    @Autowired
    private LitemallAiPatrolLogService patrolLogService;

    @Autowired
    private LitemallReviewAiAnalysisService reviewAiAnalysisService;

    @Autowired
    private LitemallCommentService commentService;

    @Autowired
    private LitemallGoodsService goodsService;

    @Autowired
    private LitemallAiCaseKnowledgeService caseKnowledgeService;

    @Autowired
    private AiReviewService aiReviewService;

    @Autowired
    private AiRiskTaskService riskTaskService;

    @Autowired
    private AgentPlatformService agentPlatformService;

    @Autowired
    private ObjectMapper objectMapper;

    @Value("${ai.patrol.enabled:true}")
    private Boolean configuredEnabled;

    @Value("${ai.patrol.batch-size:20}")
    private Integer batchSize;

    @Value("${ai.patrol.scan-demo-review:true}")
    private Boolean scanDemoReview;

    @Value("${ai.patrol.scan-litemall-comment:true}")
    private Boolean scanLitemallComment;

    @Value("${ai.patrol.fixed-delay:30000}")
    private Long fixedDelay;

    @Value("${ai.agent-framework.prefer-framework-trace:true}")
    private Boolean preferFrameworkTrace;

    private final AtomicBoolean running = new AtomicBoolean(false);
    private volatile Boolean runtimeEnabled = null;

    public Map<String, Object> status() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("enabled", isEnabled());
        data.put("running", running.get());
        data.put("fixedDelay", fixedDelay);
        data.put("batchSize", batchSize);
        data.put("scanDemoReview", Boolean.TRUE.equals(scanDemoReview));
        data.put("scanLitemallComment", Boolean.TRUE.equals(scanLitemallComment));
        data.put("pendingCount", pendingCount());
        data.put("logs", patrolLogService.latest());
        return data;
    }

    public void enable() {
        runtimeEnabled = true;
    }

    public void disable() {
        runtimeEnabled = false;
    }

    public boolean isEnabled() {
        return runtimeEnabled == null ? Boolean.TRUE.equals(configuredEnabled) : Boolean.TRUE.equals(runtimeEnabled);
    }

    public Map<String, Object> runOnce() {
        if (!running.compareAndSet(false, true)) {
            Map<String, Object> data = new HashMap<String, Object>();
            data.put("status", "running");
            data.put("message", "Agent patrol is already running.");
            return data;
        }

        LocalDateTime startTime = LocalDateTime.now();
        LitemallAiPatrolLog log = new LitemallAiPatrolLog();
        log.setTaskBatchNo("PATROL-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16));
        log.setStartTime(startTime);
        log.setStatus("running");
        log.setScanCount(0);
        log.setSuccessCount(0);
        log.setFailedCount(0);
        log.setHighRiskCount(0);
        log.setCreatedTime(startTime);

        int scanCount = 0;
        int successCount = 0;
        int failedCount = 0;
        int highRiskCount = 0;

        try {
            int limit = batchSize == null ? 20 : batchSize;
            if (Boolean.TRUE.equals(scanDemoReview)) {
                List<LitemallAiDemoReview> pending = demoReviewService.queryPending(limit);
                scanCount += pending.size();
                for (LitemallAiDemoReview review : pending) {
                    Integer runId = agentPlatformService.startRun("manual_run_once", "demo_review", review.getId(), trim(review.getReviewText(), 240));
                    demoReviewService.updateStatus(review.getId(), LitemallAiDemoReviewService.STATUS_ANALYZING);
                    try {
                        agentPlatformService.recordStep(runId, "scan_comment", 1, "CommentScannerTool", "success",
                                singleton("sourceId", review.getId()), singleton("status", "analyzing"), null, 0L);
                        AiReviewAnalyzeRequest request = buildRequest(review);
                        agentPlatformService.recordStep(runId, "load_context", 2, "CommentContextLoaderTool", "success",
                                singleton("sourceType", "demo_review"), request, null, 0L);
                        AiReviewAnalyzeResponse response = aiReviewService.analyze(request);
                        agentPlatformService.recordStep(runId, "analyze_sentiment", 3, "SentimentAnalyzeTool", "success",
                                request, response, null, 0L);
                        recordFrameworkTraceSteps(runId, response, 20);
                        agentPlatformService.recordLlmObservability(runId, response);
                        List<Map<String, Object>> ragCases = retrieveAndAttachCases(runId, request, response, "demo_review", review.getId());
                        LitemallReviewAiAnalysis analysis = buildAnalysis(request, response, "demo_review", review.getId());
                        reviewAiAnalysisService.add(analysis);
                        agentPlatformService.recordStep(runId, "write_result", 8, "AnalysisPersistTool", "success",
                                singleton("sourceId", review.getId()), singleton("analysisId", analysis.getId()), null, 0L);
                        int riskCreated = riskTaskService.createTasksForAnalysis(analysis);
                        agentPlatformService.recordStep(runId, "detect_risk", 4, "RiskDetectTool", "success",
                                response, singleton("riskCreated", riskCreated), null, 0L);
                        agentPlatformService.recordStep(runId, "retrieve_cases", 5, "SimilarCaseRetrieveTool", "success",
                                singleton("reviewId", request.getReviewId()), ragCases, null, 0L);
                        agentPlatformService.recordStep(runId, "generate_suggestion", 6, "OperationSuggestTool", "success",
                                singleton("reviewId", request.getReviewId()), response.getAgentSuggestion(), null, 0L);
                        agentPlatformService.recordStep(runId, "create_risk_task", 7, "RiskTaskCreateTool", "success",
                                singleton("analysisId", analysis.getId()), singleton("riskCreated", riskCreated), null, 0L);
                        demoReviewService.updateStatus(review.getId(), LitemallAiDemoReviewService.STATUS_ANALYZED);
                        agentPlatformService.finishRun(runId, "success", "analysisId=" + analysis.getId() + ", riskCreated=" + riskCreated, null);
                        successCount++;
                        if (isHighRisk(response, review.getRating())) {
                            highRiskCount++;
                        }
                    } catch (Exception e) {
                        agentPlatformService.recordStep(runId, "write_result", 8, "AnalysisPersistTool", "failed",
                                singleton("sourceId", review.getId()), null, e.getMessage(), 0L);
                        agentPlatformService.finishRun(runId, "failed", null, e.getMessage());
                        demoReviewService.updateStatus(review.getId(), LitemallAiDemoReviewService.STATUS_FAILED);
                        failedCount++;
                    }
                }
            }

            if (Boolean.TRUE.equals(scanLitemallComment)) {
                List<LitemallComment> comments = queryPendingComments(limit);
                scanCount += comments.size();
                for (LitemallComment comment : comments) {
                    Integer runId = agentPlatformService.startRun("manual_run_once", "litemall_comment", comment.getId(), trim(comment.getContent(), 240));
                    try {
                        agentPlatformService.recordStep(runId, "scan_comment", 1, "CommentScannerTool", "success",
                                singleton("sourceId", comment.getId()), singleton("status", "pending"), null, 0L);
                        AiReviewAnalyzeRequest request = buildRequest(comment);
                        agentPlatformService.recordStep(runId, "load_context", 2, "CommentContextLoaderTool", "success",
                                singleton("sourceType", "litemall_comment"), request, null, 0L);
                        AiReviewAnalyzeResponse response = aiReviewService.analyze(request);
                        agentPlatformService.recordStep(runId, "analyze_sentiment", 3, "SentimentAnalyzeTool", "success",
                                request, response, null, 0L);
                        recordFrameworkTraceSteps(runId, response, 20);
                        agentPlatformService.recordLlmObservability(runId, response);
                        List<Map<String, Object>> ragCases = retrieveAndAttachCases(runId, request, response, "litemall_comment", comment.getId());
                        LitemallReviewAiAnalysis analysis = buildAnalysis(request, response, "litemall_comment", comment.getId());
                        reviewAiAnalysisService.add(analysis);
                        agentPlatformService.recordStep(runId, "write_result", 8, "AnalysisPersistTool", "success",
                                singleton("sourceId", comment.getId()), singleton("analysisId", analysis.getId()), null, 0L);
                        int riskCreated = riskTaskService.createTasksForAnalysis(analysis);
                        agentPlatformService.recordStep(runId, "detect_risk", 4, "RiskDetectTool", "success",
                                response, singleton("riskCreated", riskCreated), null, 0L);
                        agentPlatformService.recordStep(runId, "retrieve_cases", 5, "SimilarCaseRetrieveTool", "success",
                                singleton("reviewId", request.getReviewId()), ragCases, null, 0L);
                        agentPlatformService.recordStep(runId, "generate_suggestion", 6, "OperationSuggestTool", "success",
                                singleton("reviewId", request.getReviewId()), response.getAgentSuggestion(), null, 0L);
                        agentPlatformService.recordStep(runId, "create_risk_task", 7, "RiskTaskCreateTool", "success",
                                singleton("analysisId", analysis.getId()), singleton("riskCreated", riskCreated), null, 0L);
                        agentPlatformService.finishRun(runId, "success", "analysisId=" + analysis.getId() + ", riskCreated=" + riskCreated, null);
                        successCount++;
                        if (isHighRisk(response, comment.getStar() == null ? null : comment.getStar().intValue())) {
                            highRiskCount++;
                        }
                    } catch (Exception e) {
                        agentPlatformService.recordStep(runId, "write_result", 8, "AnalysisPersistTool", "failed",
                                singleton("sourceId", comment.getId()), null, e.getMessage(), 0L);
                        agentPlatformService.finishRun(runId, "failed", null, e.getMessage());
                        failedCount++;
                    }
                }
            }
            log.setStatus("success");
        } catch (Exception e) {
            log.setStatus("failed");
            log.setErrorMessage(e.getMessage());
        } finally {
            log.setEndTime(LocalDateTime.now());
            log.setScanCount(scanCount);
            log.setSuccessCount(successCount);
            log.setFailedCount(failedCount);
            log.setHighRiskCount(highRiskCount);
            patrolLogService.add(log);
            running.set(false);
        }

        Map<String, Object> data = new HashMap<String, Object>();
        data.put("batchNo", log.getTaskBatchNo());
        data.put("status", log.getStatus());
        data.put("scanCount", scanCount);
        data.put("successCount", successCount);
        data.put("failedCount", failedCount);
        data.put("highRiskCount", highRiskCount);
        return data;
    }

    public List<LitemallAiPatrolLog> logs() {
        return patrolLogService.latest();
    }

    private int pendingCount() {
        int count = 0;
        if (Boolean.TRUE.equals(scanDemoReview)) {
            count += demoReviewService.queryPending(10000).size();
        }
        if (Boolean.TRUE.equals(scanLitemallComment)) {
            count += queryPendingComments(10000).size();
        }
        return count;
    }

    private List<LitemallComment> queryPendingComments(int limit) {
        List<LitemallComment> latest = commentService.queryLatestGoodsComments(Math.max(limit * 5, limit));
        List<LitemallComment> pending = new ArrayList<LitemallComment>();
        for (LitemallComment comment : latest) {
            if (comment == null || comment.getId() == null) {
                continue;
            }
            if (reviewAiAnalysisService.findBySource("litemall_comment", comment.getId()) != null) {
                continue;
            }
            pending.add(comment);
            if (pending.size() >= limit) {
                break;
            }
        }
        return pending;
    }

    private AiReviewAnalyzeRequest buildRequest(LitemallAiDemoReview review) {
        AiReviewAnalyzeRequest request = new AiReviewAnalyzeRequest();
        request.setReviewId("demo-" + review.getId());
        request.setProductId(review.getProductId());
        request.setProductName(review.getProductName());
        request.setCategory(review.getCategoryName());
        request.setRating(review.getRating());
        request.setReviewText(review.getReviewText());
        request.setImageUrls(review.getImageUrl() == null || review.getImageUrl().length() == 0
                ? Collections.<String>emptyList()
                : Collections.singletonList(review.getImageUrl()));
        return request;
    }

    private AiReviewAnalyzeRequest buildRequest(LitemallComment comment) {
        AiReviewAnalyzeRequest request = new AiReviewAnalyzeRequest();
        request.setReviewId("comment-" + comment.getId());
        request.setProductId(comment.getValueId());
        LitemallGoods goods = comment.getValueId() == null ? null : goodsService.findById(comment.getValueId());
        request.setProductName(goods == null ? "商品 " + comment.getValueId() : goods.getName());
        request.setRating(comment.getStar() == null ? null : comment.getStar().intValue());
        request.setReviewText(comment.getContent());
        request.setImageUrls(comment.getPicUrls() == null
                ? Collections.<String>emptyList()
                : Arrays.asList(comment.getPicUrls()));
        return request;
    }

    private LitemallReviewAiAnalysis buildAnalysis(AiReviewAnalyzeRequest request, AiReviewAnalyzeResponse response, String sourceType, Integer sourceId) {
        LitemallReviewAiAnalysis analysis = new LitemallReviewAiAnalysis();
        analysis.setSourceType(sourceType);
        analysis.setSourceId(sourceId);
        analysis.setReviewId(response.getReviewId());
        analysis.setProductId(request.getProductId());
        analysis.setProductName(request.getProductName());
        analysis.setReviewText(request.getReviewText());
        analysis.setRating(request.getRating());
        analysis.setImageUrls(writeJson(request.getImageUrls()));
        analysis.setSentimentLabel(response.getSentimentLabel());
        analysis.setConfidence(toDecimal(response.getConfidence()));
        if (response.getScores() != null) {
            analysis.setPositiveScore(toDecimal(response.getScores().get("positive")));
            analysis.setNeutralScore(toDecimal(response.getScores().get("neutral")));
            analysis.setNegativeScore(toDecimal(response.getScores().get("negative")));
        }
        analysis.setEvidenceJson(writeJson(response.getEvidence()));
        analysis.setSimilarCasesJson(writeJson(response.getSimilarCases()));
        analysis.setAgentSuggestionJson(writeJson(response.getAgentSuggestion()));
        analysis.setWorkflowTraceJson(writeJson(response.getWorkflowTrace()));
        return analysis;
    }

    private List<Map<String, Object>> retrieveAndAttachCases(Integer runId, AiReviewAnalyzeRequest request,
                                                             AiReviewAnalyzeResponse response,
                                                             String sourceType, Integer sourceId) {
        String riskTypes = "";
        if (response != null && response.getExtra() != null && response.getExtra().get("risk_types") != null) {
            riskTypes = String.valueOf(response.getExtra().get("risk_types")).replace("[", "").replace("]", "");
        }
        List<Map<String, Object>> cases = caseKnowledgeService.retrieveSimilarCases(
                request.getReviewText(), request.getProductId(), riskTypes,
                response == null ? null : response.getSentimentLabel(), 3, runId, sourceType, sourceId);
        if (response != null) {
            response.setSimilarCases(cases);
            List<Map<String, Object>> trace = response.getWorkflowTrace();
            if (trace == null) {
                trace = new ArrayList<Map<String, Object>>();
                response.setWorkflowTrace(trace);
            }
            Map<String, Object> output = new HashMap<String, Object>();
            output.put("retrieved_case_ids", cases == null ? Collections.emptyList() : cases);
            output.put("case_titles", caseTitles(cases));
            output.put("match_scores", matchScores(cases));
            output.put("evidence_snippets", evidenceSnippets(cases));
            output.put("retrieval_mode", "local_keyword");
            output.put("empty_retrieval", cases == null || cases.isEmpty());
            Map<String, Object> step = new HashMap<String, Object>();
            step.put("node", "similar_case_retrieve");
            step.put("step", "similar_case_retrieve");
            step.put("agent", "JavaRagCaseRetriever");
            step.put("tool_name", "CaseRetrieverTool");
            step.put("framework", "local_keyword_rag");
            step.put("status", "success");
            step.put("message", (cases == null || cases.isEmpty()) ? "No similar cases found." : "Retrieved " + cases.size() + " similar cases.");
            step.put("input_summary", trim(request.getReviewText(), 120));
            step.put("output_summary", step.get("message"));
            step.put("output", output);
            step.put("duration_ms", 0L);
            trace.add(step);
        }
        return cases;
    }

    private List<Object> caseTitles(List<Map<String, Object>> cases) {
        List<Object> values = new ArrayList<Object>();
        if (cases != null) {
            for (Map<String, Object> item : cases) {
                values.add(item.get("caseTitle"));
            }
        }
        return values;
    }

    private List<Object> matchScores(List<Map<String, Object>> cases) {
        List<Object> values = new ArrayList<Object>();
        if (cases != null) {
            for (Map<String, Object> item : cases) {
                values.add(item.get("matchScore"));
            }
        }
        return values;
    }

    private List<Object> evidenceSnippets(List<Map<String, Object>> cases) {
        List<Object> values = new ArrayList<Object>();
        if (cases != null) {
            for (Map<String, Object> item : cases) {
                values.add(item.get("evidence"));
            }
        }
        return values;
    }

    private boolean isHighRisk(AiReviewAnalyzeResponse response, Integer rating) {
        if (response == null) {
            return false;
        }
        if ("negative".equals(response.getSentimentLabel())) {
            return true;
        }
        if (response.getConfidence() != null && response.getConfidence() < 0.6) {
            return true;
        }
        if (response.getScores() != null && response.getScores().get("negative") != null && response.getScores().get("negative") >= 0.65) {
            return true;
        }
        return rating != null && rating <= 2;
    }

    private int recordFrameworkTraceSteps(Integer runId, AiReviewAnalyzeResponse response, int startOrder) {
        if (!Boolean.TRUE.equals(preferFrameworkTrace) || response == null || response.getWorkflowTrace() == null) {
            return 0;
        }
        int order = startOrder;
        if (Boolean.TRUE.equals(response.getFallbackUsed())) {
            agentPlatformService.recordStep(runId, "framework_fallback", order++, "AgentFrameworkFallback", "success",
                    singleton("framework", response.getFramework()), singleton("fallbackUsed", true), null, 0L);
        }
        for (Map<String, Object> item : response.getWorkflowTrace()) {
            if (item == null) {
                continue;
            }
            String stepName = stringValue(item.get("node"));
            if (stepName == null) {
                stepName = stringValue(item.get("step"));
            }
            if (stepName == null) {
                stepName = "framework_node";
            }
            String toolName = stringValue(item.get("tool_name"));
            if (toolName == null) {
                toolName = stringValue(item.get("agent"));
            }
            if (toolName == null) {
                toolName = "AgentFrameworkNode";
            }
            String status = stringValue(item.get("status"));
            if (status == null) {
                status = "success";
            }
            agentPlatformService.recordStep(runId, stepName, order++, toolName, status,
                    item, item, stringValue(item.get("error")), longValue(item.get("duration_ms")));
        }
        return order - startOrder;
    }

    private BigDecimal toDecimal(Double value) {
        return value == null ? null : BigDecimal.valueOf(value);
    }

    private String writeJson(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            return String.valueOf(value);
        }
    }

    private Map<String, Object> singleton(String key, Object value) {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put(key, value);
        return data;
    }

    private String stringValue(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private Long longValue(Object value) {
        if (value == null) {
            return 0L;
        }
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        try {
            return Long.valueOf(String.valueOf(value));
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    private String trim(String value, int max) {
        if (value == null) {
            return null;
        }
        return value.length() <= max ? value : value.substring(0, max);
    }
}
