package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAiOperationLog;

import java.util.List;
import java.util.Map;

public interface LitemallAiOperationLogMapper {
    int insertSelective(LitemallAiOperationLog record);

    List<LitemallAiOperationLog> queryByRiskTaskId(@Param("riskTaskId") Integer riskTaskId);

    List<LitemallAiOperationLog> queryLatest(@Param("limit") Integer limit);

    List<Map<String, Object>> statByActionType();
}
