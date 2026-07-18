package org.linlinjava.litemall.db.dao;

import org.linlinjava.litemall.db.domain.LitemallAiPatrolLog;

import java.util.List;

public interface LitemallAiPatrolLogMapper {
    int insertSelective(LitemallAiPatrolLog record);

    List<LitemallAiPatrolLog> queryLatest();
}
