package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentRagRuntime {
    private String engineType;
    private String modelName;
    private String requestedProviderImpl;
    private String effectiveProviderImpl;
    private String requestedRetrievalMode;
    private String effectiveRetrievalMode;
    private String indexVersion;
    private Boolean fallbackUsed;
    private String fallbackReason;
    private String analyzerVersion;
    private String schemaVersion;
    private String targetMode;
    private String securityGovernanceStatus;
    private Integer piiRedactionCount;
    private Boolean promptInjectionDetected;
    private String promptInjectionAction;
    private String requestedLlmProvider;
    private String effectiveLlmProvider;
    private String requestedAnalysisProvider;
    private String effectiveAnalysisProvider;
    private String llmModelId;
    private String llmRevision;
    private String llmFingerprint;
    private String promptVersion;
    private String promptFingerprint;
    private Integer llmInputTokens;
    private Integer llmOutputTokens;
    private Integer llmDurationMs;
    private Boolean structuredOutputValid;
    private String groundingStatus;
    private Boolean abstained;
    private String uncertaintyReason;
    private Boolean requiresHumanReview;
    private Boolean llmFallbackUsed;
    private String llmFallbackReason;

    public String getEngineType() { return engineType; }
    public void setEngineType(String engineType) { this.engineType = engineType; }
    public String getModelName() { return modelName; }
    public void setModelName(String modelName) { this.modelName = modelName; }
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
    public String getAnalyzerVersion() { return analyzerVersion; }
    public void setAnalyzerVersion(String analyzerVersion) { this.analyzerVersion = analyzerVersion; }
    public String getSchemaVersion() { return schemaVersion; }
    public void setSchemaVersion(String schemaVersion) { this.schemaVersion = schemaVersion; }
    public String getTargetMode() { return targetMode; }
    public void setTargetMode(String targetMode) { this.targetMode = targetMode; }
    public String getSecurityGovernanceStatus() { return securityGovernanceStatus; }
    public void setSecurityGovernanceStatus(String securityGovernanceStatus) { this.securityGovernanceStatus = securityGovernanceStatus; }
    public Integer getPiiRedactionCount() { return piiRedactionCount; }
    public void setPiiRedactionCount(Integer piiRedactionCount) { this.piiRedactionCount = piiRedactionCount; }
    public Boolean getPromptInjectionDetected() { return promptInjectionDetected; }
    public void setPromptInjectionDetected(Boolean promptInjectionDetected) { this.promptInjectionDetected = promptInjectionDetected; }
    public String getPromptInjectionAction() { return promptInjectionAction; }
    public void setPromptInjectionAction(String promptInjectionAction) { this.promptInjectionAction = promptInjectionAction; }
    public String getRequestedLlmProvider() { return requestedLlmProvider; }
    public void setRequestedLlmProvider(String requestedLlmProvider) { this.requestedLlmProvider = requestedLlmProvider; }
    public String getEffectiveLlmProvider() { return effectiveLlmProvider; }
    public void setEffectiveLlmProvider(String effectiveLlmProvider) { this.effectiveLlmProvider = effectiveLlmProvider; }
    public String getRequestedAnalysisProvider() { return requestedAnalysisProvider; }
    public void setRequestedAnalysisProvider(String requestedAnalysisProvider) { this.requestedAnalysisProvider = requestedAnalysisProvider; }
    public String getEffectiveAnalysisProvider() { return effectiveAnalysisProvider; }
    public void setEffectiveAnalysisProvider(String effectiveAnalysisProvider) { this.effectiveAnalysisProvider = effectiveAnalysisProvider; }
    public String getLlmModelId() { return llmModelId; }
    public void setLlmModelId(String llmModelId) { this.llmModelId = llmModelId; }
    public String getLlmRevision() { return llmRevision; }
    public void setLlmRevision(String llmRevision) { this.llmRevision = llmRevision; }
    public String getLlmFingerprint() { return llmFingerprint; }
    public void setLlmFingerprint(String llmFingerprint) { this.llmFingerprint = llmFingerprint; }
    public String getPromptVersion() { return promptVersion; }
    public void setPromptVersion(String promptVersion) { this.promptVersion = promptVersion; }
    public String getPromptFingerprint() { return promptFingerprint; }
    public void setPromptFingerprint(String promptFingerprint) { this.promptFingerprint = promptFingerprint; }
    public Integer getLlmInputTokens() { return llmInputTokens; }
    public void setLlmInputTokens(Integer llmInputTokens) { this.llmInputTokens = llmInputTokens; }
    public Integer getLlmOutputTokens() { return llmOutputTokens; }
    public void setLlmOutputTokens(Integer llmOutputTokens) { this.llmOutputTokens = llmOutputTokens; }
    public Integer getLlmDurationMs() { return llmDurationMs; }
    public void setLlmDurationMs(Integer llmDurationMs) { this.llmDurationMs = llmDurationMs; }
    public Boolean getStructuredOutputValid() { return structuredOutputValid; }
    public void setStructuredOutputValid(Boolean structuredOutputValid) { this.structuredOutputValid = structuredOutputValid; }
    public String getGroundingStatus() { return groundingStatus; }
    public void setGroundingStatus(String groundingStatus) { this.groundingStatus = groundingStatus; }
    public Boolean getAbstained() { return abstained; }
    public void setAbstained(Boolean abstained) { this.abstained = abstained; }
    public String getUncertaintyReason() { return uncertaintyReason; }
    public void setUncertaintyReason(String uncertaintyReason) { this.uncertaintyReason = uncertaintyReason; }
    public Boolean getRequiresHumanReview() { return requiresHumanReview; }
    public void setRequiresHumanReview(Boolean requiresHumanReview) { this.requiresHumanReview = requiresHumanReview; }
    public Boolean getLlmFallbackUsed() { return llmFallbackUsed; }
    public void setLlmFallbackUsed(Boolean llmFallbackUsed) { this.llmFallbackUsed = llmFallbackUsed; }
    public String getLlmFallbackReason() { return llmFallbackReason; }
    public void setLlmFallbackReason(String llmFallbackReason) { this.llmFallbackReason = llmFallbackReason; }
}
