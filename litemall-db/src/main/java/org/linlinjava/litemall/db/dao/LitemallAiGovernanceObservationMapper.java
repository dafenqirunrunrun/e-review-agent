package org.linlinjava.litemall.db.dao;

import org.apache.ibatis.annotations.Param;
import org.linlinjava.litemall.db.domain.LitemallAiGovernanceObservation;
import java.time.LocalDateTime;
import java.util.List;

public interface LitemallAiGovernanceObservationMapper {
    int insertSelective(LitemallAiGovernanceObservation record);
    List<LitemallAiGovernanceObservation> querySince(@Param("since") LocalDateTime since);
    List<LitemallAiGovernanceObservation> queryPendingQa(@Param("limit") Integer limit);
    int updateAuditResult(@Param("id") Long id, @Param("auditResult") String auditResult);
}
