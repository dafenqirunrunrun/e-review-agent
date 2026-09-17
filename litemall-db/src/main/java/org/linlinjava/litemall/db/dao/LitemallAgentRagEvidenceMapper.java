package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;

import java.time.LocalDateTime;
import java.util.List;

public interface LitemallAgentRagEvidenceMapper {
    int insertSelective(LitemallAgentRagEvidence record);

    LitemallAgentRagEvidence selectByRunId(Long runId);

    LitemallAgentRagEvidence selectByTenantAndEvidenceId(@Param("tenantId") String tenantId,
                                                         @Param("evidenceId") String evidenceId);

    long countExpiredCandidates(@Param("tenantId") String tenantId,
                                @Param("now") LocalDateTime now);

    List<LitemallAgentRagEvidence> selectExpiredCandidates(@Param("tenantId") String tenantId,
                                                           @Param("now") LocalDateTime now,
                                                           @Param("limit") Integer limit);

    int expireEvidencePayload(@Param("tenantId") String tenantId,
                              @Param("runId") Long runId,
                              @Param("boundedJson") String boundedJson,
                              @Param("payloadSizeBytes") Integer payloadSizeBytes,
                              @Param("expiredAt") LocalDateTime expiredAt);
}
