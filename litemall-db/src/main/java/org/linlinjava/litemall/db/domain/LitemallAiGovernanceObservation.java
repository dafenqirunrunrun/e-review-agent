package org.linlinjava.litemall.db.domain;

import java.time.LocalDateTime;

public class LitemallAiGovernanceObservation {
    private Long id;
    private String eventType;
    private Integer analysisId;
    private Integer riskTaskId;
    private String reviewId;
    private String route;
    private String decision;
    private String evidenceStatus;
    private String retrievalMode;
    private String riskTypesJson;
    private String workflowVersion;
    private String governanceSchemaVersion;
    private String policyIndexVersion;
    private String embeddingModel;
    private Long latencyMs;
    private String humanDecision;
    private String humanReasonCode;
    private String auditResult;
    private String shadowDecision;
    private Boolean shadowDisagreement;
    private String evidenceRefs;
    private LocalDateTime createdTime;

    public Long getId() { return id; } public void setId(Long id) { this.id = id; }
    public String getEventType() { return eventType; } public void setEventType(String eventType) { this.eventType = eventType; }
    public Integer getAnalysisId() { return analysisId; } public void setAnalysisId(Integer analysisId) { this.analysisId = analysisId; }
    public Integer getRiskTaskId() { return riskTaskId; } public void setRiskTaskId(Integer riskTaskId) { this.riskTaskId = riskTaskId; }
    public String getReviewId() { return reviewId; } public void setReviewId(String reviewId) { this.reviewId = reviewId; }
    public String getRoute() { return route; } public void setRoute(String route) { this.route = route; }
    public String getDecision() { return decision; } public void setDecision(String decision) { this.decision = decision; }
    public String getEvidenceStatus() { return evidenceStatus; } public void setEvidenceStatus(String evidenceStatus) { this.evidenceStatus = evidenceStatus; }
    public String getRetrievalMode() { return retrievalMode; } public void setRetrievalMode(String retrievalMode) { this.retrievalMode = retrievalMode; }
    public String getRiskTypesJson() { return riskTypesJson; } public void setRiskTypesJson(String riskTypesJson) { this.riskTypesJson = riskTypesJson; }
    public String getWorkflowVersion() { return workflowVersion; } public void setWorkflowVersion(String workflowVersion) { this.workflowVersion = workflowVersion; }
    public String getGovernanceSchemaVersion() { return governanceSchemaVersion; } public void setGovernanceSchemaVersion(String governanceSchemaVersion) { this.governanceSchemaVersion = governanceSchemaVersion; }
    public String getPolicyIndexVersion() { return policyIndexVersion; } public void setPolicyIndexVersion(String policyIndexVersion) { this.policyIndexVersion = policyIndexVersion; }
    public String getEmbeddingModel() { return embeddingModel; } public void setEmbeddingModel(String embeddingModel) { this.embeddingModel = embeddingModel; }
    public Long getLatencyMs() { return latencyMs; } public void setLatencyMs(Long latencyMs) { this.latencyMs = latencyMs; }
    public String getHumanDecision() { return humanDecision; } public void setHumanDecision(String humanDecision) { this.humanDecision = humanDecision; }
    public String getHumanReasonCode() { return humanReasonCode; } public void setHumanReasonCode(String humanReasonCode) { this.humanReasonCode = humanReasonCode; }
    public String getAuditResult() { return auditResult; } public void setAuditResult(String auditResult) { this.auditResult = auditResult; }
    public String getShadowDecision() { return shadowDecision; } public void setShadowDecision(String shadowDecision) { this.shadowDecision = shadowDecision; }
    public Boolean getShadowDisagreement() { return shadowDisagreement; } public void setShadowDisagreement(Boolean shadowDisagreement) { this.shadowDisagreement = shadowDisagreement; }
    public String getEvidenceRefs() { return evidenceRefs; } public void setEvidenceRefs(String evidenceRefs) { this.evidenceRefs = evidenceRefs; }
    public LocalDateTime getCreatedTime() { return createdTime; } public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
}
