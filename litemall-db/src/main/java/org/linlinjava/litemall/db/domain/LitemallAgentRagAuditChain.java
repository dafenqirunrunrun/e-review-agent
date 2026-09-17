package org.linlinjava.litemall.db.domain;

import java.time.LocalDateTime;

public class LitemallAgentRagAuditChain {
    private Long id;
    private String tenantId;
    private Long lastRunId;
    private String lastAuditHash;
    private Long chainVersion;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }
    public Long getLastRunId() { return lastRunId; }
    public void setLastRunId(Long lastRunId) { this.lastRunId = lastRunId; }
    public String getLastAuditHash() { return lastAuditHash; }
    public void setLastAuditHash(String lastAuditHash) { this.lastAuditHash = lastAuditHash; }
    public Long getChainVersion() { return chainVersion; }
    public void setChainVersion(Long chainVersion) { this.chainVersion = chainVersion; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
