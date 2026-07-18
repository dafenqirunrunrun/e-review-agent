package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;

import java.util.List;
import java.util.Map;

public interface LitemallAiReviewRiskTaskMapper {
    int insertSelective(LitemallAiReviewRiskTask record);

    LitemallAiReviewRiskTask selectByPrimaryKey(Integer id);

    LitemallAiReviewRiskTask findByAnalysisAndType(@Param("analysisId") Integer analysisId, @Param("riskType") String riskType);

    List<LitemallAiReviewRiskTask> querySelective(@Param("riskLevel") String riskLevel,
                                                  @Param("riskType") String riskType,
                                                  @Param("status") String status);

    int updateStatus(@Param("id") Integer id,
                     @Param("status") String status,
                     @Param("handler") String handler,
                     @Param("handleNote") String handleNote);

    List<Map<String, Object>> statByStatus();

    List<Map<String, Object>> statByLevel();
}
