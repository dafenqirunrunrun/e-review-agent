package org.linlinjava.litemall.db.domain;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class LitemallAgentRagRun {
    private Long id;
    private String requestId;
    private String idempotencyKey;
    private String tenantId;
    private String subjectType;
    private String subjectId;
    private Long parentRunId;
    private Long replayOfRunId;
    private String status;
    private String riskLevel;
    private String riskTypesJson;
    private String action;
    private BigDecimal confidence;
    private Boolean requiresHumanReview;
    private String runtimeMode;
    private String targetMode;
    private String requestedProviderImpl;
    private String effectiveProviderImpl;
    private String requestedRetrievalMode;
    private String effectiveRetrievalMode;
    private String indexVersion;
    private Boolean fallbackUsed;
    private String fallbackReason;
    private String schemaVersion;
    private String analyzerVersion;
    private String evidenceId;
    private String securityPolicyVersion;
    private Boolean piiDetected;
    private String piiTypesJson;
    private Integer piiCount;
    private Boolean modelInputRedacted;
    private Boolean auditRedacted;
    private Boolean uiRedacted;
    private Boolean promptInjectionDetected;
    private String promptInjectionRiskLevel;
    private String promptInjectionSignalsJson;
    private Boolean promptInjectionExecutionSuppressed;
    private String citationSetHash;
    private String runtimeConfigHash;
    private String effectiveDecisionHash;
    private String previousAuditHash;
    private String auditHash;
    private String auditIntegrityStatus;
    private LocalDateTime evidenceExpiresAt;
    private LocalDateTime rawInputExpiresAt;
    private Integer retryCount;
    private String errorCode;
    private String errorMessage;
    private LocalDateTime startedAt;
    private LocalDateTime finishedAt;
    private Long durationMs;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private Boolean deleted;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public String getIdempotencyKey() { return idempotencyKey; }
    public void setIdempotencyKey(String idempotencyKey) { this.idempotencyKey = idempotencyKey; }
    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }
    public String getSubjectType() { return subjectType; }
    public void setSubjectType(String subjectType) { this.subjectType = subjectType; }
    public String getSubjectId() { return subjectId; }
    public void setSubjectId(String subjectId) { this.subjectId = subjectId; }
    public Long getParentRunId() { return parentRunId; }
    public void setParentRunId(Long parentRunId) { this.parentRunId = parentRunId; }
    public Long getReplayOfRunId() { return replayOfRunId; }
    public void setReplayOfRunId(Long replayOfRunId) { this.replayOfRunId = replayOfRunId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getRiskLevel() { return riskLevel; }
    public void setRiskLevel(String riskLevel) { this.riskLevel = riskLevel; }
    public String getRiskTypesJson() { return riskTypesJson; }
    public void setRiskTypesJson(String riskTypesJson) { this.riskTypesJson = riskTypesJson; }
    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }
    public BigDecimal getConfidence() { return confidence; }
    public void setConfidence(BigDecimal confidence) { this.confidence = confidence; }
    public Boolean getRequiresHumanReview() { return requiresHumanReview; }
    public void setRequiresHumanReview(Boolean requiresHumanReview) { this.requiresHumanReview = requiresHumanReview; }
    public String getRuntimeMode() { return runtimeMode; }
    public void setRuntimeMode(String runtimeMode) { this.runtimeMode = runtimeMode; }
    public String getTargetMode() { return targetMode; }
    public void setTargetMode(String targetMode) { this.targetMode = targetMode; }
    public String getRequestedProviderImpl() { return requestedProviderImpl; }
    public void setRequestedProviderImpl(String requestedProviderImpl) { this.requestedProviderImpl = requestedProviderImpl; }
    public String getEffectiveProviderImpl() { return effectiveProviderImpl; }
    public void setEffectiveProviderImpl(String effectiveProviderImpl) { this.effectiveProviderImpl = effectiveProviderImpl; }
    public String getRequestedRetrievalMode() { return requestedRetrievalMode; }
    public void setRequestedRetrievalMode(String requestedRetrievalMode) { this.requestedRetrievalMode = requestedRetrievalMode; }
    public String getEffectiveRetrievalMode() { return effectiveRetrievalMode; }
    public void setEffectiveRetrievalMode(String effectiveRetrievalMode) { this.effectiveRetrievalMode = effectiveRetrievalMode; }
    public String getIndexVersion() { return indexVersion; }
    public void setIndexVersion(String indexVersion) { this.indexVersion = indexVersion; }
    public Boolean getFallbackUsed() { return fallbackUsed; }
    public void setFallbackUsed(Boolean fallbackUsed) { this.fallbackUsed = fallbackUsed; }
    public String getFallbackReason() { return fallbackReason; }
    public void setFallbackReason(String fallbackReason) { this.fallbackReason = fallbackReason; }
    public String getSchemaVersion() { return schemaVersion; }
    public void setSchemaVersion(String schemaVersion) { this.schemaVersion = schemaVersion; }
    public String getAnalyzerVersion() { return analyzerVersion; }
    public void setAnalyzerVersion(String analyzerVersion) { this.analyzerVersion = analyzerVersion; }
    public String getEvidenceId() { return evidenceId; }
    public void setEvidenceId(String evidenceId) { this.evidenceId = evidenceId; }
    public String getSecurityPolicyVersion() { return securityPolicyVersion; }
    public void setSecurityPolicyVersion(String securityPolicyVersion) { this.securityPolicyVersion = securityPolicyVersion; }
    public Boolean getPiiDetected() { return piiDetected; }
    public void setPiiDetected(Boolean piiDetected) { this.piiDetected = piiDetected; }
    public String getPiiTypesJson() { return piiTypesJson; }
    public void setPiiTypesJson(String piiTypesJson) { this.piiTypesJson = piiTypesJson; }
    public Integer getPiiCount() { return piiCount; }
    public void setPiiCount(Integer piiCount) { this.piiCount = piiCount; }
    public Boolean getModelInputRedacted() { return modelInputRedacted; }
    public void setModelInputRedacted(Boolean modelInputRedacted) { this.modelInputRedacted = modelInputRedacted; }
    public Boolean getAuditRedacted() { return auditRedacted; }
    public void setAuditRedacted(Boolean auditRedacted) { this.auditRedacted = auditRedacted; }
    public Boolean getUiRedacted() { return uiRedacted; }
    public void setUiRedacted(Boolean uiRedacted) { this.uiRedacted = uiRedacted; }
    public Boolean getPromptInjectionDetected() { return promptInjectionDetected; }
    public void setPromptInjectionDetected(Boolean promptInjectionDetected) { this.promptInjectionDetected = promptInjectionDetected; }
    public String getPromptInjectionRiskLevel() { return promptInjectionRiskLevel; }
    public void setPromptInjectionRiskLevel(String promptInjectionRiskLevel) { this.promptInjectionRiskLevel = promptInjectionRiskLevel; }
    public String getPromptInjectionSignalsJson() { return promptInjectionSignalsJson; }
    public void setPromptInjectionSignalsJson(String promptInjectionSignalsJson) { this.promptInjectionSignalsJson = promptInjectionSignalsJson; }
    public Boolean getPromptInjectionExecutionSuppressed() { return promptInjectionExecutionSuppressed; }
    public void setPromptInjectionExecutionSuppressed(Boolean promptInjectionExecutionSuppressed) { this.promptInjectionExecutionSuppressed = promptInjectionExecutionSuppressed; }
    public String getCitationSetHash() { return citationSetHash; }
    public void setCitationSetHash(String citationSetHash) { this.citationSetHash = citationSetHash; }
    public String getRuntimeConfigHash() { return runtimeConfigHash; }
    public void setRuntimeConfigHash(String runtimeConfigHash) { this.runtimeConfigHash = runtimeConfigHash; }
    public String getEffectiveDecisionHash() { return effectiveDecisionHash; }
    public void setEffectiveDecisionHash(String effectiveDecisionHash) { this.effectiveDecisionHash = effectiveDecisionHash; }
    public String getPreviousAuditHash() { return previousAuditHash; }
    public void setPreviousAuditHash(String previousAuditHash) { this.previousAuditHash = previousAuditHash; }
    public String getAuditHash() { return auditHash; }
    public void setAuditHash(String auditHash) { this.auditHash = auditHash; }
    public String getAuditIntegrityStatus() { return auditIntegrityStatus; }
    public void setAuditIntegrityStatus(String auditIntegrityStatus) { this.auditIntegrityStatus = auditIntegrityStatus; }
    public LocalDateTime getEvidenceExpiresAt() { return evidenceExpiresAt; }
    public void setEvidenceExpiresAt(LocalDateTime evidenceExpiresAt) { this.evidenceExpiresAt = evidenceExpiresAt; }
    public LocalDateTime getRawInputExpiresAt() { return rawInputExpiresAt; }
    public void setRawInputExpiresAt(LocalDateTime rawInputExpiresAt) { this.rawInputExpiresAt = rawInputExpiresAt; }
    public Integer getRetryCount() { return retryCount; }
    public void setRetryCount(Integer retryCount) { this.retryCount = retryCount; }
    public String getErrorCode() { return errorCode; }
    public void setErrorCode(String errorCode) { this.errorCode = errorCode; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public LocalDateTime getStartedAt() { return startedAt; }
    public void setStartedAt(LocalDateTime startedAt) { this.startedAt = startedAt; }
    public LocalDateTime getFinishedAt() { return finishedAt; }
    public void setFinishedAt(LocalDateTime finishedAt) { this.finishedAt = finishedAt; }
    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
    public Boolean getDeleted() { return deleted; }
    public void setDeleted(Boolean deleted) { this.deleted = deleted; }
}
