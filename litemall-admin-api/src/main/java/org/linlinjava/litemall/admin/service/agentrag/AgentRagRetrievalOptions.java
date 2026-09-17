package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentRagRetrievalOptions {
    private Boolean enabled = true;
    private Integer topK = 8;
    private Integer rerankTopK = 4;
    private String requestedMode = "bm25-first-semantic-hybrid";
    private Boolean publicTenantEnabled = true;

    public Boolean getEnabled() { return enabled; }
    public void setEnabled(Boolean enabled) { this.enabled = enabled; }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer topK) { this.topK = topK; }
    public Integer getRerankTopK() { return rerankTopK; }
    public void setRerankTopK(Integer rerankTopK) { this.rerankTopK = rerankTopK; }
    public String getRequestedMode() { return requestedMode; }
    public void setRequestedMode(String requestedMode) { this.requestedMode = requestedMode; }
    public Boolean getPublicTenantEnabled() { return publicTenantEnabled; }
    public void setPublicTenantEnabled(Boolean publicTenantEnabled) { this.publicTenantEnabled = publicTenantEnabled; }
}
