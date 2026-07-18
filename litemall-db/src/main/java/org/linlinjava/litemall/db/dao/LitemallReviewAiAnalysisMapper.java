package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallReviewAiAnalysis;

import java.util.List;
import java.util.Map;

public interface LitemallReviewAiAnalysisMapper {
    int insertSelective(LitemallReviewAiAnalysis record);

    LitemallReviewAiAnalysis selectByPrimaryKey(Integer id);

    List<LitemallReviewAiAnalysis> querySelective(@Param("productId") Integer productId,
                                                  @Param("sentimentLabel") String sentimentLabel);

    LitemallReviewAiAnalysis findBySource(@Param("sourceType") String sourceType,
                                          @Param("sourceId") Integer sourceId);

    Map<String, Object> statSummary();

    List<Map<String, Object>> statSentimentDistribution();

    List<Map<String, Object>> statRiskTrend();

    List<Map<String, Object>> statRiskTypeDistribution();

    List<Map<String, Object>> statTopRiskProducts();
}
