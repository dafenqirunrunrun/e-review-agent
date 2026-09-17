package org.linlinjava.litemall.db.service;

import org.linlinjava.litemall.db.dao.LitemallAgentRagEvidenceMapper;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class LitemallAgentRagEvidenceService {
    @Resource
    private LitemallAgentRagEvidenceMapper mapper;

    public int create(LitemallAgentRagEvidence evidence) {
        return mapper.insertSelective(evidence);
    }

    public LitemallAgentRagEvidence findByRunId(Long runId) {
        return mapper.selectByRunId(runId);
    }

    public LitemallAgentRagEvidence findByTenantAndEvidenceId(String tenantId, String evidenceId) {
        return mapper.selectByTenantAndEvidenceId(tenantId, evidenceId);
    }

    public long countExpiredCandidates(String tenantId, LocalDateTime now) {
        return mapper.countExpiredCandidates(tenantId, now);
    }

    public List<LitemallAgentRagEvidence> expiredCandidates(String tenantId, LocalDateTime now, Integer limit) {
        int safeLimit = limit == null || limit <= 0 || limit > 100 ? 50 : limit;
        return mapper.selectExpiredCandidates(tenantId, now, safeLimit);
    }

    public int expirePayload(String tenantId, Long runId, String boundedJson, Integer payloadSizeBytes, LocalDateTime expiredAt) {
        return mapper.expireEvidencePayload(tenantId, runId, boundedJson, payloadSizeBytes, expiredAt);
    }
}
