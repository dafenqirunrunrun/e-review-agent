package org.linlinjava.litemall.admin.service;

import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;
import org.linlinjava.litemall.db.domain.LitemallReviewAiAnalysis;
import org.linlinjava.litemall.db.service.LitemallAiReviewRiskTaskService;
import org.linlinjava.litemall.db.service.LitemallReviewAiAnalysisService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.HashMap;
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
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("task", task);
        data.put("analysis", task == null || task.getAnalysisId() == null ? null : analysisService.findById(task.getAnalysisId()));
        return data;
    }

    public int updateStatus(Integer id, String status, String handler, String handleNote) {
        return riskTaskService.updateStatus(id, status, handler, handleNote);
    }

    public Map<String, Object> summary() {
        syncFromAnalyses();
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("status", riskTaskService.statByStatus());
        data.put("level", riskTaskService.statByLevel());
        return data;
    }

    private int createTask(LitemallReviewAiAnalysis analysis, String riskType, String riskLevel) {
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
        riskTaskService.add(task);
        return 1;
    }
}
