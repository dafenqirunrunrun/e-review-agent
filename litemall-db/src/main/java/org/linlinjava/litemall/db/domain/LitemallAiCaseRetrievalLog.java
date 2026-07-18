package org.linlinjava.litemall.db.domain;

import java.time.LocalDateTime;

public class LitemallAiCaseRetrievalLog {
    private Integer id;
    private Integer runId;
    private String sourceType;
    private Integer sourceId;
    private String queryText;
    private String retrievedCaseIds;
    private Integer topK;
    private String retrievalMode;
    private Long durationMs;
    private LocalDateTime createdTime;
    private Boolean deleted;

    public Integer getId() { return id; }
    public void setId(Integer id) { this.id = id; }
    public Integer getRunId() { return runId; }
    public void setRunId(Integer runId) { this.runId = runId; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public Integer getSourceId() { return sourceId; }
    public void setSourceId(Integer sourceId) { this.sourceId = sourceId; }
    public String getQueryText() { return queryText; }
    public void setQueryText(String queryText) { this.queryText = queryText; }
    public String getRetrievedCaseIds() { return retrievedCaseIds; }
    public void setRetrievedCaseIds(String retrievedCaseIds) { this.retrievedCaseIds = retrievedCaseIds; }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public String getRetrievalMode() { return retrievalMode; }
    public void setRetrievalMode(String retrievalMode) { this.retrievalMode = retrievalMode; }
    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }
    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
    public Boolean getDeleted() { return deleted; }
    public void setDeleted(Boolean deleted) { this.deleted = deleted; }
}
