package org.linlinjava.litemall.db.service;

import com.github.pagehelper.PageHelper;
import org.linlinjava.litemall.db.dao.LitemallReviewAiAnalysisMapper;
import org.linlinjava.litemall.db.domain.LitemallReviewAiAnalysis;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;

@Service
public class LitemallReviewAiAnalysisService {
    @Resource
    private LitemallReviewAiAnalysisMapper reviewAiAnalysisMapper;

    public int add(LitemallReviewAiAnalysis analysis) {
        LocalDateTime now = LocalDateTime.now();
        analysis.setAddTime(now);
        analysis.setUpdateTime(now);
        analysis.setDeleted(false);
        return reviewAiAnalysisMapper.insertSelective(analysis);
    }

    public LitemallReviewAiAnalysis findById(Integer id) {
        return reviewAiAnalysisMapper.selectByPrimaryKey(id);
    }

    public LitemallReviewAiAnalysis findBySource(String sourceType, Integer sourceId) {
        if (sourceType == null || sourceId == null) {
            return null;
        }
        return reviewAiAnalysisMapper.findBySource(sourceType, sourceId);
    }

    public List<LitemallReviewAiAnalysis> querySelective(Integer productId, String sentimentLabel, Integer page, Integer limit) {
        PageHelper.startPage(page, limit);
        return reviewAiAnalysisMapper.querySelective(productId, sentimentLabel);
    }

    public Map<String, Object> statSummary() {
        Map<String, Object> summary = reviewAiAnalysisMapper.statSummary();
        return summary == null ? Collections.emptyMap() : summary;
    }

    public List<Map<String, Object>> statSentimentDistribution() {
        return reviewAiAnalysisMapper.statSentimentDistribution();
    }

    public List<Map<String, Object>> statRiskTrend() {
        return reviewAiAnalysisMapper.statRiskTrend();
    }

    public List<Map<String, Object>> statRiskTypeDistribution() {
        return reviewAiAnalysisMapper.statRiskTypeDistribution();
    }

    public List<Map<String, Object>> statTopRiskProducts() {
        return reviewAiAnalysisMapper.statTopRiskProducts();
    }
}
