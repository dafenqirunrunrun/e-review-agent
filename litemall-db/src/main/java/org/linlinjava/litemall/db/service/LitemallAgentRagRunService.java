package org.linlinjava.litemall.db.service;

import org.linlinjava.litemall.db.dao.LitemallAgentRagRunMapper;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.List;

@Service
public class LitemallAgentRagRunService {
    @Resource
    private LitemallAgentRagRunMapper mapper;

    public int create(LitemallAgentRagRun run) {
        return mapper.insertSelective(run);
    }

    public int update(LitemallAgentRagRun run) {
        return mapper.updateByPrimaryKeySelective(run);
    }

    public LitemallAgentRagRun findById(Long id) {
        return mapper.selectByPrimaryKey(id);
    }

    public LitemallAgentRagRun findByTenantAndRequest(String tenantId, String requestId) {
        return mapper.selectByTenantAndRequest(tenantId, requestId);
    }

    public LitemallAgentRagRun findByIdempotencyKey(String idempotencyKey) {
        return mapper.selectByIdempotencyKey(idempotencyKey);
    }

    public List<LitemallAgentRagRun> recent(String tenantId, String status, Integer limit) {
        int safeLimit = limit == null || limit <= 0 || limit > 200 ? 50 : limit;
        return mapper.selectRecent(tenantId, status, safeLimit);
    }

    public List<LitemallAgentRagRun> listForAdmin(String tenantId, String subjectType, String subjectId,
                                                  String requestId, String status, String riskLevel,
                                                  String providerImpl, Boolean fallbackUsed,
                                                  Boolean requiresHumanReview, String createdFrom,
                                                  String createdTo, Integer page, Integer limit) {
        int safeLimit = limit == null || limit <= 0 || limit > 100 ? 20 : limit;
        int safePage = page == null || page <= 0 ? 1 : page;
        int offset = (safePage - 1) * safeLimit;
        return mapper.selectForAdmin(tenantId, subjectType, subjectId, requestId, status, riskLevel,
                providerImpl, fallbackUsed, requiresHumanReview, createdFrom, createdTo, offset, safeLimit);
    }

    public long countForAdmin(String tenantId, String subjectType, String subjectId, String requestId,
                              String status, String riskLevel, String providerImpl, Boolean fallbackUsed,
                              Boolean requiresHumanReview, String createdFrom, String createdTo) {
        return mapper.countForAdmin(tenantId, subjectType, subjectId, requestId, status, riskLevel,
                providerImpl, fallbackUsed, requiresHumanReview, createdFrom, createdTo);
    }

    public List<LitemallAgentRagRun> overviewWindow(String tenantId, String createdFrom, String createdTo, Integer limit) {
        int safeLimit = limit == null || limit <= 0 || limit > 10000 ? 10000 : limit;
        return mapper.selectOverviewWindow(tenantId, createdFrom, createdTo, safeLimit);
    }
}
