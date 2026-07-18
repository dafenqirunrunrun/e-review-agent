package org.linlinjava.litemall.db.service;

import org.linlinjava.litemall.db.dao.LitemallAiOperationLogMapper;
import org.linlinjava.litemall.db.domain.LitemallAiOperationLog;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
public class LitemallAiOperationLogService {
    @Resource
    private LitemallAiOperationLogMapper operationLogMapper;

    public int add(LitemallAiOperationLog log) {
        log.setCreatedTime(LocalDateTime.now());
        return operationLogMapper.insertSelective(log);
    }

    public List<LitemallAiOperationLog> queryByRiskTaskId(Integer riskTaskId) {
        return operationLogMapper.queryByRiskTaskId(riskTaskId);
    }

    public List<LitemallAiOperationLog> latest(Integer limit) {
        return operationLogMapper.queryLatest(limit);
    }

    public List<Map<String, Object>> statByActionType() {
        return operationLogMapper.statByActionType();
    }
}
