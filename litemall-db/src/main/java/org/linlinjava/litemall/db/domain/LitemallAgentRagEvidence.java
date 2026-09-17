package org.linlinjava.litemall.db.domain;

import java.time.LocalDateTime;

public class LitemallAgentRagEvidence {
    private Long id;
    private String evidenceId;
    private Long runId;
    private String requestId;
    private String tenantId;
    private String bundleHash;
    private String boundedJson;
    private Integer citationCount;
    private Integer payloadSizeBytes;
    private Boolean piiRedacted;
    private Boolean evidenceExpired;
    private LocalDateTime expiredAt;
    private String citationSetHash;
    private LocalDateTime createdAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getEvidenceId() { return evidenceId; }
    public void setEvidenceId(String evidenceId) { this.evidenceId = evidenceId; }
    public Long getRunId() { return runId; }
    public void setRunId(Long runId) { this.runId = runId; }
    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }
    public String getBundleHash() { return bundleHash; }
    public void setBundleHash(String bundleHash) { this.bundleHash = bundleHash; }
    public String getBoundedJson() { return boundedJson; }
    public void setBoundedJson(String boundedJson) { this.boundedJson = boundedJson; }
    public Integer getCitationCount() { return citationCount; }
    public void setCitationCount(Integer citationCount) { this.citationCount = citationCount; }
    public Integer getPayloadSizeBytes() { return payloadSizeBytes; }
    public void setPayloadSizeBytes(Integer payloadSizeBytes) { this.payloadSizeBytes = payloadSizeBytes; }
    public Boolean getPiiRedacted() { return piiRedacted; }
    public void setPiiRedacted(Boolean piiRedacted) { this.piiRedacted = piiRedacted; }
    public Boolean getEvidenceExpired() { return evidenceExpired; }
    public void setEvidenceExpired(Boolean evidenceExpired) { this.evidenceExpired = evidenceExpired; }
    public LocalDateTime getExpiredAt() { return expiredAt; }
    public void setExpiredAt(LocalDateTime expiredAt) { this.expiredAt = expiredAt; }
    public String getCitationSetHash() { return citationSetHash; }
    public void setCitationSetHash(String citationSetHash) { this.citationSetHash = citationSetHash; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
