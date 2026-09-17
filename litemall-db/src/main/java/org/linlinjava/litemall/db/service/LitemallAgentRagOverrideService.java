package org.linlinjava.litemall.db.service;

import org.linlinjava.litemall.db.dao.LitemallAgentRagOverrideMapper;
import org.linlinjava.litemall.db.domain.LitemallAgentRagOverride;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

@Service
public class LitemallAgentRagOverrideService {
    @Resource
    private LitemallAgentRagOverrideMapper mapper;

    public int create(LitemallAgentRagOverride override) {
        return mapper.insertSelective(override);
    }

    public List<LitemallAgentRagOverride> listByRun(String tenantId, Long runId) {
        return mapper.selectByRunId(runId, tenantId);
    }

    public List<LitemallAgentRagOverride> latestByRuns(String tenantId, List<Long> runIds) {
        if (runIds == null || runIds.isEmpty()) {
            return java.util.Collections.emptyList();
        }
        return mapper.selectLatestByRunIds(tenantId, runIds);
    }

    public List<Map<String, Object>> countByRuns(String tenantId, List<Long> runIds) {
        if (runIds == null || runIds.isEmpty()) {
            return java.util.Collections.emptyList();
        }
        return mapper.countByRunIds(tenantId, runIds);
    }

    public long countInWindow(String tenantId, String createdFrom, String createdTo) {
        return mapper.countInWindow(tenantId, createdFrom, createdTo);
    }
}
