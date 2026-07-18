package org.linlinjava.litemall.db.service;

import org.linlinjava.litemall.db.dao.LitemallAiPatrolLogMapper;
import org.linlinjava.litemall.db.domain.LitemallAiPatrolLog;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class LitemallAiPatrolLogService {
    @Resource
    private LitemallAiPatrolLogMapper patrolLogMapper;

    public int add(LitemallAiPatrolLog log) {
        if (log.getCreatedTime() == null) {
            log.setCreatedTime(LocalDateTime.now());
        }
        return patrolLogMapper.insertSelective(log);
    }

    public List<LitemallAiPatrolLog> latest() {
        return patrolLogMapper.queryLatest();
    }
}
