package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAiCaseKnowledge;

import java.util.List;
import java.util.Map;

public interface LitemallAiCaseKnowledgeMapper {
    int insertSelective(LitemallAiCaseKnowledge record);

    LitemallAiCaseKnowledge selectByPrimaryKey(Integer id);

    List<LitemallAiCaseKnowledge> querySelective(@Param("keyword") String keyword,
                                                 @Param("riskLevel") String riskLevel,
                                                 @Param("sentimentLabel") String sentimentLabel);

    List<LitemallAiCaseKnowledge> listForRetrieval();

    int buildFromHistory();

    List<Map<String, Object>> statByRiskLevel();

    List<Map<String, Object>> statBySentiment();

    int countActive();
}
