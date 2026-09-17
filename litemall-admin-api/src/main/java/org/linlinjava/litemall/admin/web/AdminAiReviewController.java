package org.linlinjava.litemall.admin.web;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.commons.lang3.StringUtils;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.annotation.RequiresPermissionsDesc;
import org.linlinjava.litemall.admin.service.AiRiskTaskService;
import org.linlinjava.litemall.admin.service.AiReviewService;
import org.linlinjava.litemall.admin.service.ReviewGovernanceTraceService;
import org.linlinjava.litemall.admin.service.GovernanceQualityService;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeRequest;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeResponse;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.core.validator.Order;
import org.linlinjava.litemall.core.validator.Sort;
import org.linlinjava.litemall.db.domain.LitemallReviewAiAnalysis;
import org.linlinjava.litemall.db.service.LitemallReviewAiAnalysisService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/ai/review")
@Validated
public class AdminAiReviewController {
    private static final Logger logger = LoggerFactory.getLogger(AdminAiReviewController.class);

    @Autowired
    private AiReviewService aiReviewService;

    @Autowired
    private LitemallReviewAiAnalysisService reviewAiAnalysisService;

    @Autowired
    private AiRiskTaskService riskTaskService;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ReviewGovernanceTraceService governanceTraceService;

    @Autowired
    private GovernanceQualityService governanceQualityService;

    @RequiresPermissions("admin:ai:review:list")
    @RequiresPermissionsDesc(menu = {"AI评价分析", "分析历史"}, button = "查询")
    @GetMapping("/list")
    public Object list(@RequestParam(value = "productId", required = false) Integer productId,
                       @RequestParam(value = "sentimentLabel", required = false) String sentimentLabel,
                       @RequestParam(value = "page", defaultValue = "1") Integer page,
                       @RequestParam(value = "limit", defaultValue = "10") Integer limit,
                       @Sort @RequestParam(value = "sort", defaultValue = "add_time") String sort,
                       @Order @RequestParam(value = "order", defaultValue = "desc") String order) {
        List<LitemallReviewAiAnalysis> analysisList = reviewAiAnalysisService.querySelective(productId, sentimentLabel, page, limit);
        return ResponseUtil.okList(analysisList);
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @RequiresPermissionsDesc(menu = {"AI评价分析", "评价分析"}, button = "分析")
    @PostMapping("/analyze")
    public Object analyze(@RequestBody AiReviewAnalyzeRequest request) {
        if (request == null) {
            return ResponseUtil.badArgument();
        }
        if (request.getProductId() == null || StringUtils.isBlank(request.getProductName()) || StringUtils.isBlank(request.getReviewText())) {
            return ResponseUtil.badArgumentValue();
        }
        if (StringUtils.isBlank(request.getReviewId())) {
            request.setReviewId("manual-" + System.currentTimeMillis());
        }

        try {
            Source source = resolveSource(request.getReviewId());
            LitemallReviewAiAnalysis existing = reviewAiAnalysisService.findBySource(source.sourceType, source.sourceId);
            if (existing != null) {
                Map<String, Object> data = new HashMap<String, Object>();
                data.put("analysisId", existing.getId());
                data.put("result", responseFromAnalysis(existing));
                data.put("duplicated", true);
                return ResponseUtil.ok(data);
            }
            long started = System.currentTimeMillis();
            AiReviewAnalyzeResponse response = aiReviewService.analyze(request);
            if (response == null) {
                return ResponseUtil.fail(502, "AI服务未返回分析结果");
            }
            logger.info("review_governance_analyze_ok reviewId={} productId={} route={} riskTypes={} evidenceStatus={} latencyMs={}",
                    request.getReviewId(), request.getProductId(), response.getRouteDecision(), response.getRiskTypes(),
                    response.getEvidenceStatus(), System.currentTimeMillis() - started);
            LitemallReviewAiAnalysis analysis = buildAnalysis(request, response);
            analysis.setSourceType(source.sourceType);
            analysis.setSourceId(source.sourceId);
            reviewAiAnalysisService.add(analysis);
            riskTaskService.createTasksForAnalysis(analysis);
            governanceQualityService.recordDecision(analysis.getId(), response, System.currentTimeMillis() - started);
            governanceQualityService.maybeShadowAudit(request, response, aiReviewService);
            Map<String, Object> data = new HashMap<String, Object>();
            data.put("analysisId", analysis.getId());
            data.put("result", response);
            return ResponseUtil.ok(data);
        } catch (AiReviewService.AiReviewServiceException e) {
            logger.warn("review_governance_analyze_degraded reviewId={} productId={} fallbackReason=AI_SERVICE_UNAVAILABLE",
                    request.getReviewId(), request.getProductId());
            return ResponseUtil.fail(502, "AI 服务暂时不可用，可继续人工审核，服务恢复后再补充分析结果。");
        }
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @RequiresPermissionsDesc(menu = {"AI评价分析", "判定依据库"}, button = "证据试查")
    @PostMapping("/policy-playground/query")
    public Object policyPlaygroundQuery(@RequestBody Map<String, Object> request) {
        Object rawQuery = request == null ? null : request.get("query");
        String query = rawQuery == null ? "" : StringUtils.trimToEmpty(String.valueOf(rawQuery));
        if (query.length() < 1 || query.length() > 2000) {
            return ResponseUtil.badArgumentValue();
        }
        try {
            return ResponseUtil.ok(aiReviewService.policyPlaygroundQuery(request));
        } catch (AiReviewService.AiReviewServiceException e) {
            logger.warn("policy_playground_degraded fallbackReason=AI_SERVICE_UNAVAILABLE");
            return ResponseUtil.fail(502, "政策证据试查暂时不可用，请稍后重试。");
        }
    }

    private LitemallReviewAiAnalysis buildAnalysis(AiReviewAnalyzeRequest request, AiReviewAnalyzeResponse response) {
        LitemallReviewAiAnalysis analysis = new LitemallReviewAiAnalysis();
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
        analysis.setWorkflowTraceJson(writeJson(governanceTraceService.workflowTraceWithGovernance(response)));
        return analysis;
    }

    private Source resolveSource(String reviewId) {
        if (reviewId != null && reviewId.startsWith("comment-")) {
            return new Source("litemall_comment", parseSourceId(reviewId, "comment-"));
        }
        if (reviewId != null && reviewId.startsWith("demo-")) {
            return new Source("demo_review", parseSourceId(reviewId, "demo-"));
        }
        return new Source("manual_input", null);
    }

    private Integer parseSourceId(String value, String prefix) {
        try {
            return Integer.valueOf(value.substring(prefix.length()));
        } catch (Exception e) {
            return null;
        }
    }

    private AiReviewAnalyzeResponse responseFromAnalysis(LitemallReviewAiAnalysis analysis) {
        AiReviewAnalyzeResponse response = new AiReviewAnalyzeResponse();
        response.setReviewId(analysis.getReviewId());
        response.setSentimentLabel(analysis.getSentimentLabel());
        response.setConfidence(analysis.getConfidence() == null ? null : analysis.getConfidence().doubleValue());
        Map<String, Double> scores = new HashMap<String, Double>();
        scores.put("positive", toDouble(analysis.getPositiveScore()));
        scores.put("neutral", toDouble(analysis.getNeutralScore()));
        scores.put("negative", toDouble(analysis.getNegativeScore()));
        response.setScores(scores);
        response.setEvidence(readStringList(analysis.getEvidenceJson()));
        response.setSimilarCases(readMapList(analysis.getSimilarCasesJson()));
        response.setAgentSuggestion(readMap(analysis.getAgentSuggestionJson()));
        response.setWorkflowTrace(readMapList(analysis.getWorkflowTraceJson()));
        response.setReviewGovernance(governanceTraceService.extractGovernanceSnapshot(analysis));
        Map<String, Object> governance = response.getReviewGovernance();
        if (governance != null) {
            response.setRiskTypes(readStringList(governance.get("riskTypes")));
            response.setEvidenceStatus(stringValue(governance.get("evidenceStatus")));
            response.setReflectionReason(stringValue(governance.get("reflectionReason")));
            response.setRequiresHumanReview(Boolean.TRUE.equals(governance.get("requiresHumanReview")));
            response.setNeedHumanReview(response.getRequiresHumanReview());
            Map<String, Object> decision = castMap(governance.get("decision"));
            response.setRiskLevel(stringValue(decision.get("riskLevel")));
            response.setRouteDecision(stringValue(decision.get("code")));
            response.setEvidenceSufficient("supported".equals(response.getEvidenceStatus()));
        }
        return response;
    }

    private List<String> readStringList(String value) {
        if (StringUtils.isBlank(value)) {
            return null;
        }
        try {
            return objectMapper.readValue(value, new TypeReference<List<String>>() {
            });
        } catch (Exception e) {
            return null;
        }
    }

    private List<String> readStringList(Object value) {
        if (!(value instanceof List)) {
            return null;
        }
        List<String> result = new java.util.ArrayList<String>();
        for (Object item : (List<?>) value) {
            if (item != null) {
                result.add(String.valueOf(item));
            }
        }
        return result;
    }

    private List<Map<String, Object>> readMapList(String value) {
        if (StringUtils.isBlank(value)) {
            return null;
        }
        try {
            return objectMapper.readValue(value, new TypeReference<List<Map<String, Object>>>() {
            });
        } catch (Exception e) {
            return null;
        }
    }

    private Map<String, Object> readMap(String value) {
        if (StringUtils.isBlank(value)) {
            return null;
        }
        try {
            return objectMapper.readValue(value, new TypeReference<Map<String, Object>>() {
            });
        } catch (Exception e) {
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> castMap(Object value) {
        if (value instanceof Map) {
            return (Map<String, Object>) value;
        }
        return new HashMap<String, Object>();
    }

    private static class Source {
        private final String sourceType;
        private final Integer sourceId;

        private Source(String sourceType, Integer sourceId) {
            this.sourceType = sourceType;
            this.sourceId = sourceId;
        }
    }

    private BigDecimal toDecimal(Double value) {
        if (value == null) {
            return null;
        }
        return BigDecimal.valueOf(value);
    }

    private Double toDouble(BigDecimal value) {
        return value == null ? null : value.doubleValue();
    }

    private String stringValue(Object value) {
        return value == null ? null : String.valueOf(value);
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
}
