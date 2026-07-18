package org.linlinjava.litemall.db.dao;

import org.linlinjava.litemall.db.domain.LitemallAiCaseRetrievalLog;

import java.util.List;
import java.util.Map;

public interface LitemallAiCaseRetrievalLogMapper {
    int insertSelective(LitemallAiCaseRetrievalLog record);

    List<LitemallAiCaseRetrievalLog> queryRecent();

    Map<String, Object> statSummary();
}
