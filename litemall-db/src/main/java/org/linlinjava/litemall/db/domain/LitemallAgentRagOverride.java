package org.linlinjava.litemall.db.domain;

import java.time.LocalDateTime;

public class LitemallAgentRagOverride {
    private Long id;
    private Long runId;
    private String tenantId;
    private String previousRiskLevel;
    private String newRiskLevel;
    private String previousAction;
    private String newAction;
    private String reason;
    private Long operatorId;
    private String previousOverrideHash;
    private String overrideHash;
    private String effectiveDecisionHash;
    private LocalDateTime createdAt;
    private Boolean deleted;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getRunId() { return runId; }
    public void setRunId(Long runId) { this.runId = runId; }
    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }
    public String getPreviousRiskLevel() { return previousRiskLevel; }
    public void setPreviousRiskLevel(String previousRiskLevel) { this.previousRiskLevel = previousRiskLevel; }
    public String getNewRiskLevel() { return newRiskLevel; }
    public void setNewRiskLevel(String newRiskLevel) { this.newRiskLevel = newRiskLevel; }
    public String getPreviousAction() { return previousAction; }
    public void setPreviousAction(String previousAction) { this.previousAction = previousAction; }
    public String getNewAction() { return newAction; }
    public void setNewAction(String newAction) { this.newAction = newAction; }
    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }
    public Long getOperatorId() { return operatorId; }
    public void setOperatorId(Long operatorId) { this.operatorId = operatorId; }
    public String getPreviousOverrideHash() { return previousOverrideHash; }
    public void setPreviousOverrideHash(String previousOverrideHash) { this.previousOverrideHash = previousOverrideHash; }
    public String getOverrideHash() { return overrideHash; }
    public void setOverrideHash(String overrideHash) { this.overrideHash = overrideHash; }
    public String getEffectiveDecisionHash() { return effectiveDecisionHash; }
    public void setEffectiveDecisionHash(String effectiveDecisionHash) { this.effectiveDecisionHash = effectiveDecisionHash; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public Boolean getDeleted() { return deleted; }
    public void setDeleted(Boolean deleted) { this.deleted = deleted; }
}
