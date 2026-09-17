package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagConfig {
    private boolean enabled = true;
    private String baseUrl = "http://127.0.0.1:8008";
    private String analyzePath = "/api/v1/agent-rag/analyze";
    private String healthPath = "/api/v1/internal/agent-rag/dense/health";
    private int connectTimeoutMs = 2000;
    private int readTimeoutMs = 30000;
    private int totalTimeoutMs = 35000;
    private int maxRetries = 1;
    private int retryBackoffMs = 200;
    private int maxQueryChars = 10000;
    private int maxContextBytes = 65536;
    private int maxResponseBytes = 2097152;
    private int maxEvidenceBytes = 524288;
    private int maxCitations = 20;
    private int maxSnippetChars = 1000;
    private int maxSummaryChars = 4000;
    private String singleTenantId = "__local__";
    private int circuitBreakerFailureThreshold = 5;
    private long circuitBreakerOpenDurationMs = 30000L;
    private int circuitBreakerHalfOpenMaxCalls = 1;

    public void validate() {
        if (!enabled) {
            return;
        }
        if (baseUrl == null || !baseUrl.startsWith("http")) {
            throw new IllegalArgumentException("AGENT_RAG_BASE_URL_INVALID");
        }
        if (connectTimeoutMs <= 0 || readTimeoutMs <= 0 || totalTimeoutMs <= 0) {
            throw new IllegalArgumentException("AGENT_RAG_TIMEOUT_INVALID");
        }
        if (maxRetries < 0 || maxRetries > 3) {
            throw new IllegalArgumentException("AGENT_RAG_MAX_RETRIES_INVALID");
        }
        if (maxResponseBytes <= 0 || maxContextBytes <= 0 || maxCitations <= 0 || maxEvidenceBytes <= 0) {
            throw new IllegalArgumentException("AGENT_RAG_LIMIT_INVALID");
        }
        if (singleTenantId == null || singleTenantId.trim().length() == 0) {
            throw new IllegalArgumentException("AGENT_RAG_SINGLE_TENANT_ID_INVALID");
        }
    }

    public String analyzeUrl() {
        return trim(baseUrl) + normalizePath(analyzePath);
    }

    public String healthUrl() {
        return trim(baseUrl) + normalizePath(healthPath);
    }

    private String trim(String value) {
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private String normalizePath(String value) {
        if (value == null || value.length() == 0) {
            return "/";
        }
        return value.startsWith("/") ? value : "/" + value;
    }

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public String getBaseUrl() { return baseUrl; }
    public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
    public String getAnalyzePath() { return analyzePath; }
    public void setAnalyzePath(String analyzePath) { this.analyzePath = analyzePath; }
    public String getHealthPath() { return healthPath; }
    public void setHealthPath(String healthPath) { this.healthPath = healthPath; }
    public int getConnectTimeoutMs() { return connectTimeoutMs; }
    public void setConnectTimeoutMs(int connectTimeoutMs) { this.connectTimeoutMs = connectTimeoutMs; }
    public int getReadTimeoutMs() { return readTimeoutMs; }
    public void setReadTimeoutMs(int readTimeoutMs) { this.readTimeoutMs = readTimeoutMs; }
    public int getTotalTimeoutMs() { return totalTimeoutMs; }
    public void setTotalTimeoutMs(int totalTimeoutMs) { this.totalTimeoutMs = totalTimeoutMs; }
    public int getMaxRetries() { return maxRetries; }
    public void setMaxRetries(int maxRetries) { this.maxRetries = maxRetries; }
    public int getRetryBackoffMs() { return retryBackoffMs; }
    public void setRetryBackoffMs(int retryBackoffMs) { this.retryBackoffMs = retryBackoffMs; }
    public int getMaxQueryChars() { return maxQueryChars; }
    public void setMaxQueryChars(int maxQueryChars) { this.maxQueryChars = maxQueryChars; }
    public int getMaxContextBytes() { return maxContextBytes; }
    public void setMaxContextBytes(int maxContextBytes) { this.maxContextBytes = maxContextBytes; }
    public int getMaxResponseBytes() { return maxResponseBytes; }
    public void setMaxResponseBytes(int maxResponseBytes) { this.maxResponseBytes = maxResponseBytes; }
    public int getMaxEvidenceBytes() { return maxEvidenceBytes; }
    public void setMaxEvidenceBytes(int maxEvidenceBytes) { this.maxEvidenceBytes = maxEvidenceBytes; }
    public int getMaxCitations() { return maxCitations; }
    public void setMaxCitations(int maxCitations) { this.maxCitations = maxCitations; }
    public int getMaxSnippetChars() { return maxSnippetChars; }
    public void setMaxSnippetChars(int maxSnippetChars) { this.maxSnippetChars = maxSnippetChars; }
    public int getMaxSummaryChars() { return maxSummaryChars; }
    public void setMaxSummaryChars(int maxSummaryChars) { this.maxSummaryChars = maxSummaryChars; }
    public String getSingleTenantId() { return singleTenantId; }
    public void setSingleTenantId(String singleTenantId) { this.singleTenantId = singleTenantId; }
    public int getCircuitBreakerFailureThreshold() { return circuitBreakerFailureThreshold; }
    public void setCircuitBreakerFailureThreshold(int circuitBreakerFailureThreshold) { this.circuitBreakerFailureThreshold = circuitBreakerFailureThreshold; }
    public long getCircuitBreakerOpenDurationMs() { return circuitBreakerOpenDurationMs; }
    public void setCircuitBreakerOpenDurationMs(long circuitBreakerOpenDurationMs) { this.circuitBreakerOpenDurationMs = circuitBreakerOpenDurationMs; }
    public int getCircuitBreakerHalfOpenMaxCalls() { return circuitBreakerHalfOpenMaxCalls; }
    public void setCircuitBreakerHalfOpenMaxCalls(int circuitBreakerHalfOpenMaxCalls) { this.circuitBreakerHalfOpenMaxCalls = circuitBreakerHalfOpenMaxCalls; }
}
