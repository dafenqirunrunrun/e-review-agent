package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;

import java.util.List;

public interface LitemallAgentRagRunMapper {
    int insertSelective(LitemallAgentRagRun record);

    LitemallAgentRagRun selectByPrimaryKey(Long id);

    LitemallAgentRagRun selectByTenantAndRequest(@Param("tenantId") String tenantId,
                                                 @Param("requestId") String requestId);

    LitemallAgentRagRun selectByIdempotencyKey(String idempotencyKey);

    List<LitemallAgentRagRun> selectRecent(@Param("tenantId") String tenantId,
                                           @Param("status") String status,
                                           @Param("limit") Integer limit);

    List<LitemallAgentRagRun> selectForAdmin(@Param("tenantId") String tenantId,
                                             @Param("subjectType") String subjectType,
                                             @Param("subjectId") String subjectId,
                                             @Param("requestId") String requestId,
                                             @Param("status") String status,
                                             @Param("riskLevel") String riskLevel,
                                             @Param("providerImpl") String providerImpl,
                                             @Param("fallbackUsed") Boolean fallbackUsed,
                                             @Param("requiresHumanReview") Boolean requiresHumanReview,
                                             @Param("createdFrom") String createdFrom,
                                             @Param("createdTo") String createdTo,
                                             @Param("offset") Integer offset,
                                             @Param("limit") Integer limit);

    long countForAdmin(@Param("tenantId") String tenantId,
                       @Param("subjectType") String subjectType,
                       @Param("subjectId") String subjectId,
                       @Param("requestId") String requestId,
                       @Param("status") String status,
                       @Param("riskLevel") String riskLevel,
                       @Param("providerImpl") String providerImpl,
                       @Param("fallbackUsed") Boolean fallbackUsed,
                       @Param("requiresHumanReview") Boolean requiresHumanReview,
                       @Param("createdFrom") String createdFrom,
                       @Param("createdTo") String createdTo);

    List<LitemallAgentRagRun> selectOverviewWindow(@Param("tenantId") String tenantId,
                                                   @Param("createdFrom") String createdFrom,
                                                   @Param("createdTo") String createdTo,
                                                   @Param("limit") Integer limit);

    int updateByPrimaryKeySelective(LitemallAgentRagRun record);
}
