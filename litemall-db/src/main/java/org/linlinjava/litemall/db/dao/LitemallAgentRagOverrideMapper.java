package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAgentRagOverride;

import java.util.List;

public interface LitemallAgentRagOverrideMapper {
    int insertSelective(LitemallAgentRagOverride record);

    List<LitemallAgentRagOverride> selectByRunId(@Param("runId") Long runId,
                                                 @Param("tenantId") String tenantId);

    List<LitemallAgentRagOverride> selectLatestByRunIds(@Param("tenantId") String tenantId,
                                                        @Param("runIds") List<Long> runIds);

    List<java.util.Map<String, Object>> countByRunIds(@Param("tenantId") String tenantId,
                                                      @Param("runIds") List<Long> runIds);

    long countInWindow(@Param("tenantId") String tenantId,
                       @Param("createdFrom") String createdFrom,
                       @Param("createdTo") String createdTo);
}
