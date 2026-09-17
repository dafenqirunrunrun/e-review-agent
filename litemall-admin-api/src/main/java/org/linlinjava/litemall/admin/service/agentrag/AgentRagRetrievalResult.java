package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.ArrayList;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentRagRetrievalResult {
    private Boolean used;
    private Boolean empty;
    private Boolean retrievalEmpty;
    private String query;
    private Integer topK;
    private Integer returned;
    private String denseProvider;
    private String requestedRetrievalMode;
    private String effectiveRetrievalMode;
    private String indexVersion;
    private String modelFingerprint;
    private Integer embeddingDimension;
    private String faissIndexType;
    private String faissMetric;
    private Integer embeddingDurationMs;
    private Integer faissSearchDurationMs;
    private Boolean denseFallbackUsed;
    private String denseFallbackReason;
    private String requestedRerankerType;
    private String effectiveRerankerType;
    private String rerankerModelId;
    private String rerankerRevision;
    private String rerankerModelName;
    private String rerankerFingerprint;
    private Integer rerankerInputCount;
    private Integer rerankerOutputCount;
    private Integer rerankerDurationMs;
    private Boolean rerankerFallbackUsed;
    private String rerankerFallbackReason;
    private List<AgentRagCitation> citations = new ArrayList<AgentRagCitation>();

    public Boolean getUsed() { return used; }
    public void setUsed(Boolean used) { this.used = used; }
    public Boolean getEmpty() { return empty == null ? retrievalEmpty : empty; }
    public void setEmpty(Boolean empty) { this.empty = empty; }
    public Boolean getRetrievalEmpty() { return retrievalEmpty; }
    public void setRetrievalEmpty(Boolean retrievalEmpty) { this.retrievalEmpty = retrievalEmpty; }
    public String getQuery() { return query; }
    public void setQuery(String query) { this.query = query; }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public Integer getReturned() { return returned; }
    public void setReturned(Integer returned) { this.returned = returned; }
    public String getDenseProvider() { return denseProvider; }
    public void setDenseProvider(String denseProvider) { this.denseProvider = denseProvider; }
    public String getRequestedRetrievalMode() { return requestedRetrievalMode; }
    public void setRequestedRetrievalMode(String requestedRetrievalMode) { this.requestedRetrievalMode = requestedRetrievalMode; }
    public String getEffectiveRetrievalMode() { return effectiveRetrievalMode; }
    public void setEffectiveRetrievalMode(String effectiveRetrievalMode) { this.effectiveRetrievalMode = effectiveRetrievalMode; }
    public String getIndexVersion() { return indexVersion; }
    public void setIndexVersion(String indexVersion) { this.indexVersion = indexVersion; }
    public String getModelFingerprint() { return modelFingerprint; }
    public void setModelFingerprint(String modelFingerprint) { this.modelFingerprint = modelFingerprint; }
    public Integer getEmbeddingDimension() { return embeddingDimension; }
    public void setEmbeddingDimension(Integer embeddingDimension) { this.embeddingDimension = embeddingDimension; }
    public String getFaissIndexType() { return faissIndexType; }
    public void setFaissIndexType(String faissIndexType) { this.faissIndexType = faissIndexType; }
    public String getFaissMetric() { return faissMetric; }
    public void setFaissMetric(String faissMetric) { this.faissMetric = faissMetric; }
    public Integer getEmbeddingDurationMs() { return embeddingDurationMs; }
    public void setEmbeddingDurationMs(Integer embeddingDurationMs) { this.embeddingDurationMs = embeddingDurationMs; }
    public Integer getFaissSearchDurationMs() { return faissSearchDurationMs; }
    public void setFaissSearchDurationMs(Integer faissSearchDurationMs) { this.faissSearchDurationMs = faissSearchDurationMs; }
    public Boolean getDenseFallbackUsed() { return denseFallbackUsed; }
    public void setDenseFallbackUsed(Boolean denseFallbackUsed) { this.denseFallbackUsed = denseFallbackUsed; }
    public String getDenseFallbackReason() { return denseFallbackReason; }
    public void setDenseFallbackReason(String denseFallbackReason) { this.denseFallbackReason = denseFallbackReason; }
    public String getRequestedRerankerType() { return requestedRerankerType; }
    public void setRequestedRerankerType(String requestedRerankerType) { this.requestedRerankerType = requestedRerankerType; }
    public String getEffectiveRerankerType() { return effectiveRerankerType; }
    public void setEffectiveRerankerType(String effectiveRerankerType) { this.effectiveRerankerType = effectiveRerankerType; }
    public String getRerankerModelId() { return rerankerModelId; }
    public void setRerankerModelId(String rerankerModelId) { this.rerankerModelId = rerankerModelId; }
    public String getRerankerRevision() { return rerankerRevision; }
    public void setRerankerRevision(String rerankerRevision) { this.rerankerRevision = rerankerRevision; }
    public String getRerankerModelName() { return rerankerModelName; }
    public void setRerankerModelName(String rerankerModelName) { this.rerankerModelName = rerankerModelName; }
    public String getRerankerFingerprint() { return rerankerFingerprint; }
    public void setRerankerFingerprint(String rerankerFingerprint) { this.rerankerFingerprint = rerankerFingerprint; }
    public Integer getRerankerInputCount() { return rerankerInputCount; }
    public void setRerankerInputCount(Integer rerankerInputCount) { this.rerankerInputCount = rerankerInputCount; }
    public Integer getRerankerOutputCount() { return rerankerOutputCount; }
    public void setRerankerOutputCount(Integer rerankerOutputCount) { this.rerankerOutputCount = rerankerOutputCount; }
    public Integer getRerankerDurationMs() { return rerankerDurationMs; }
    public void setRerankerDurationMs(Integer rerankerDurationMs) { this.rerankerDurationMs = rerankerDurationMs; }
    public Boolean getRerankerFallbackUsed() { return rerankerFallbackUsed; }
    public void setRerankerFallbackUsed(Boolean rerankerFallbackUsed) { this.rerankerFallbackUsed = rerankerFallbackUsed; }
    public String getRerankerFallbackReason() { return rerankerFallbackReason; }
    public void setRerankerFallbackReason(String rerankerFallbackReason) { this.rerankerFallbackReason = rerankerFallbackReason; }
    public List<AgentRagCitation> getCitations() { return citations; }
    public void setCitations(List<AgentRagCitation> citations) { this.citations = citations; }
}
