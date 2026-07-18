package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAiDemoReview;

import java.util.List;
import java.util.Map;

public interface LitemallAiDemoReviewMapper {
    int insertSelective(LitemallAiDemoReview record);

    LitemallAiDemoReview selectByPrimaryKey(Integer id);

    List<LitemallAiDemoReview> querySelective(@Param("productId") Integer productId,
                                              @Param("analysisStatus") String analysisStatus);

    List<LitemallAiDemoReview> queryPending(@Param("limit") Integer limit);

    int updateStatus(@Param("id") Integer id, @Param("analysisStatus") String analysisStatus);

    List<Map<String, Object>> statByStatus();
}
