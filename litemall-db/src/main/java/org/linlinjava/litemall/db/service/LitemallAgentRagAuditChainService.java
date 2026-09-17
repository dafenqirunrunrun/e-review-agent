package org.linlinjava.litemall.db.service;

import org.linlinjava.litemall.db.dao.LitemallAgentRagAuditChainMapper;
import org.linlinjava.litemall.db.domain.LitemallAgentRagAuditChain;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;

@Service
public class LitemallAgentRagAuditChainService {
    @Resource
    private LitemallAgentRagAuditChainMapper mapper;

    public int create(LitemallAgentRagAuditChain chain) {
        return mapper.insertSelective(chain);
    }

    public LitemallAgentRagAuditChain findByTenant(String tenantId) {
        return mapper.selectByTenant(tenantId);
    }

    public LitemallAgentRagAuditChain findByTenantForUpdate(String tenantId) {
        return mapper.selectByTenantForUpdate(tenantId);
    }

    public int update(LitemallAgentRagAuditChain chain) {
        return mapper.updateByPrimaryKeySelective(chain);
    }
}
