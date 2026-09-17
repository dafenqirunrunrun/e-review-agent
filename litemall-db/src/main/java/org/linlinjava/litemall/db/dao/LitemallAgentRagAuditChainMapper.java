package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAgentRagAuditChain;

public interface LitemallAgentRagAuditChainMapper {
    int insertSelective(LitemallAgentRagAuditChain record);

    LitemallAgentRagAuditChain selectByTenant(@Param("tenantId") String tenantId);

    LitemallAgentRagAuditChain selectByTenantForUpdate(@Param("tenantId") String tenantId);

    int updateByPrimaryKeySelective(LitemallAgentRagAuditChain record);
}
