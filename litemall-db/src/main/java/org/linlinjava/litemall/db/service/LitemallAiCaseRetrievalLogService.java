package org.linlinjava.litemall.db.service;

import org.linlinjava.litemall.db.dao.LitemallAiCaseRetrievalLogMapper;
import org.linlinjava.litemall.db.domain.LitemallAiCaseRetrievalLog;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;

@Service
public class LitemallAiCaseRetrievalLogService {
    @Resource
    private LitemallAiCaseRetrievalLogMapper retrievalLogMapper;

    public int add(LitemallAiCaseRetrievalLog log) {
        log.setRetrievalMode(log.getRetrievalMode() == null ? "local_keyword" : log.getRetrievalMode());
        log.setTopK(log.getTopK() == null ? 3 : log.getTopK());
        log.setCreatedTime(LocalDateTime.now());
        log.setDeleted(false);
        return retrievalLogMapper.insertSelective(log);
    }

    public List<LitemallAiCaseRetrievalLog> recent() {
        return retrievalLogMapper.queryRecent();
    }

    public Map<String, Object> statSummary() {
        Map<String, Object> summary = retrievalLogMapper.statSummary();
        return summary == null ? Collections.<String, Object>emptyMap() : summary;
    }
}
