package org.linlinjava.litemall.db.service;

import org.linlinjava.litemall.db.dao.LitemallAiGovernanceObservationMapper;
import org.linlinjava.litemall.db.domain.LitemallAiGovernanceObservation;
import org.springframework.stereotype.Service;
import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class LitemallAiGovernanceObservationService {
    @Resource private LitemallAiGovernanceObservationMapper mapper;
    public int add(LitemallAiGovernanceObservation record) { record.setCreatedTime(LocalDateTime.now()); return mapper.insertSelective(record); }
    public List<LitemallAiGovernanceObservation> querySince(LocalDateTime since) { return mapper.querySince(since); }
    public List<LitemallAiGovernanceObservation> pendingQa(Integer limit) { return mapper.queryPendingQa(limit); }
    public int updateAuditResult(Long id, String result) { return mapper.updateAuditResult(id, result); }
}
