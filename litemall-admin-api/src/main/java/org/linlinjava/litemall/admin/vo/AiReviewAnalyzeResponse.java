package org.linlinjava.litemall.admin.vo;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

public class AiReviewAnalyzeResponse {
    @JsonProperty("review_id")
    private String reviewId;

    @JsonProperty("sentiment_label")
    private String sentimentLabel;

    private Double confidence;
    private Map<String, Double> scores;
    private List<String> evidence;

    @JsonProperty("similar_cases")
    private List<Map<String, Object>> similarCases;

    @JsonProperty("agent_suggestion")
    private Map<String, Object> agentSuggestion;

    @JsonProperty("workflow_trace")
    private List<Map<String, Object>> workflowTrace;

    private String framework;

    @JsonProperty("fallback_used")
    private Boolean fallbackUsed;

    @JsonProperty("llm_provider")
    private String llmProvider;

    @JsonProperty("model_name")
    private String modelName;

    @JsonProperty("prompt_template")
    private String promptTemplate;

    @JsonProperty("schema_valid")
    private Boolean schemaValid;

    @JsonProperty("schema_error")
    private String schemaError;

    @JsonProperty("repair_used")
    private Boolean repairUsed;

    @JsonProperty("token_usage_input")
    private Integer tokenUsageInput;

    @JsonProperty("token_usage_output")
    private Integer tokenUsageOutput;

    @JsonProperty("latency_ms")
    private Long latencyMs;

    @JsonProperty("need_human_review")
    private Boolean needHumanReview;

    @JsonProperty("missing_information")
    private List<String> missingInformation;

    @JsonProperty("rag_enabled")
    private Boolean ragEnabled;
    @JsonProperty("rag_strategy")
    private String ragStrategy;
    @JsonProperty("retrieval_hit_count")
    private Integer retrievalHitCount;
    @JsonProperty("retrieval_top_score")
    private Double retrievalTopScore;
    @JsonProperty("retrieval_latency_ms")
    private Long retrievalLatencyMs;
    @JsonProperty("embedding_provider")
    private String embeddingProvider;
    @JsonProperty("reranker_provider")
    private String rerankerProvider;
    @JsonProperty("retrieved_case_ids")
    private List<String> retrievedCaseIds;
    @JsonProperty("route_decision")
    private String routeDecision;
    @JsonProperty("route_reason")
    private String routeReason;
    @JsonProperty("evidence_sufficient")
    private Boolean evidenceSufficient;
    @JsonProperty("human_review_trigger")
    private String humanReviewTrigger;

    @JsonProperty("modality_conflict")
    private Map<String, Object> modalityConflict;

    @JsonProperty("dominant_modality")
    private Map<String, Object> dominantModality;

    private Map<String, Object> extra;

    public String getReviewId() {
        return reviewId;
    }

    public void setReviewId(String reviewId) {
        this.reviewId = reviewId;
    }

    public String getSentimentLabel() {
        return sentimentLabel;
    }

    public void setSentimentLabel(String sentimentLabel) {
        this.sentimentLabel = sentimentLabel;
    }

    public Double getConfidence() {
        return confidence;
    }

    public void setConfidence(Double confidence) {
        this.confidence = confidence;
    }

    public Map<String, Double> getScores() {
        return scores;
    }

    public void setScores(Map<String, Double> scores) {
        this.scores = scores;
    }

    public List<String> getEvidence() {
        return evidence;
    }

    public void setEvidence(List<String> evidence) {
        this.evidence = evidence;
    }

    public List<Map<String, Object>> getSimilarCases() {
        return similarCases;
    }

    public void setSimilarCases(List<Map<String, Object>> similarCases) {
        this.similarCases = similarCases;
    }

    public Map<String, Object> getAgentSuggestion() {
        return agentSuggestion;
    }

    public void setAgentSuggestion(Map<String, Object> agentSuggestion) {
        this.agentSuggestion = agentSuggestion;
    }

    public List<Map<String, Object>> getWorkflowTrace() {
        return workflowTrace;
    }

    public void setWorkflowTrace(List<Map<String, Object>> workflowTrace) {
        this.workflowTrace = workflowTrace;
    }

    public String getFramework() {
        return framework;
    }

    public void setFramework(String framework) {
        this.framework = framework;
    }

    public Boolean getFallbackUsed() {
        return fallbackUsed;
    }

    public void setFallbackUsed(Boolean fallbackUsed) {
        this.fallbackUsed = fallbackUsed;
    }

    public String getLlmProvider() { return llmProvider; }
    public void setLlmProvider(String llmProvider) { this.llmProvider = llmProvider; }
    public String getModelName() { return modelName; }
    public void setModelName(String modelName) { this.modelName = modelName; }
    public String getPromptTemplate() { return promptTemplate; }
    public void setPromptTemplate(String promptTemplate) { this.promptTemplate = promptTemplate; }
    public Boolean getSchemaValid() { return schemaValid; }
    public void setSchemaValid(Boolean schemaValid) { this.schemaValid = schemaValid; }
    public String getSchemaError() { return schemaError; }
    public void setSchemaError(String schemaError) { this.schemaError = schemaError; }
    public Boolean getRepairUsed() { return repairUsed; }
    public void setRepairUsed(Boolean repairUsed) { this.repairUsed = repairUsed; }
    public Integer getTokenUsageInput() { return tokenUsageInput; }
    public void setTokenUsageInput(Integer tokenUsageInput) { this.tokenUsageInput = tokenUsageInput; }
    public Integer getTokenUsageOutput() { return tokenUsageOutput; }
    public void setTokenUsageOutput(Integer tokenUsageOutput) { this.tokenUsageOutput = tokenUsageOutput; }
    public Long getLatencyMs() { return latencyMs; }
    public void setLatencyMs(Long latencyMs) { this.latencyMs = latencyMs; }
    public Boolean getNeedHumanReview() { return needHumanReview; }
    public void setNeedHumanReview(Boolean needHumanReview) { this.needHumanReview = needHumanReview; }
    public List<String> getMissingInformation() { return missingInformation; }
    public void setMissingInformation(List<String> missingInformation) { this.missingInformation = missingInformation; }
    public Boolean getRagEnabled() { return ragEnabled; }
    public void setRagEnabled(Boolean ragEnabled) { this.ragEnabled = ragEnabled; }
    public String getRagStrategy() { return ragStrategy; }
    public void setRagStrategy(String ragStrategy) { this.ragStrategy = ragStrategy; }
    public Integer getRetrievalHitCount() { return retrievalHitCount; }
    public void setRetrievalHitCount(Integer retrievalHitCount) { this.retrievalHitCount = retrievalHitCount; }
    public Double getRetrievalTopScore() { return retrievalTopScore; }
    public void setRetrievalTopScore(Double retrievalTopScore) { this.retrievalTopScore = retrievalTopScore; }
    public Long getRetrievalLatencyMs() { return retrievalLatencyMs; }
    public void setRetrievalLatencyMs(Long retrievalLatencyMs) { this.retrievalLatencyMs = retrievalLatencyMs; }
    public String getEmbeddingProvider() { return embeddingProvider; }
    public void setEmbeddingProvider(String embeddingProvider) { this.embeddingProvider = embeddingProvider; }
    public String getRerankerProvider() { return rerankerProvider; }
    public void setRerankerProvider(String rerankerProvider) { this.rerankerProvider = rerankerProvider; }
    public List<String> getRetrievedCaseIds() { return retrievedCaseIds; }
    public void setRetrievedCaseIds(List<String> retrievedCaseIds) { this.retrievedCaseIds = retrievedCaseIds; }
    public String getRouteDecision() { return routeDecision; }
    public void setRouteDecision(String routeDecision) { this.routeDecision = routeDecision; }
    public String getRouteReason() { return routeReason; }
    public void setRouteReason(String routeReason) { this.routeReason = routeReason; }
    public Boolean getEvidenceSufficient() { return evidenceSufficient; }
    public void setEvidenceSufficient(Boolean evidenceSufficient) { this.evidenceSufficient = evidenceSufficient; }
    public String getHumanReviewTrigger() { return humanReviewTrigger; }
    public void setHumanReviewTrigger(String humanReviewTrigger) { this.humanReviewTrigger = humanReviewTrigger; }

    public Map<String, Object> getModalityConflict() {
        return modalityConflict;
    }

    public void setModalityConflict(Map<String, Object> modalityConflict) {
        this.modalityConflict = modalityConflict;
    }

    public Map<String, Object> getDominantModality() {
        return dominantModality;
    }

    public void setDominantModality(Map<String, Object> dominantModality) {
        this.dominantModality = dominantModality;
    }

    public Map<String, Object> getExtra() {
        return extra;
    }

    public void setExtra(Map<String, Object> extra) {
        this.extra = extra;
    }
}
