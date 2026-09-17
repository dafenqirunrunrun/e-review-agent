package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentRagHealthResponse {
    private String status;
    private String targetMode;
    private String requestedProviderImpl;
    private String effectiveProviderImpl;
    private String providerConformance;
    private Boolean modelLoaded;
    private Boolean indexCompatible;
    private String activeIndexVersion;
    private Boolean fallbackUsed;
    private Map<String, Object> raw;

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getTargetMode() { return targetMode; }
    public void setTargetMode(String targetMode) { this.targetMode = targetMode; }
    public String getRequestedProviderImpl() { return requestedProviderImpl; }
    public void setRequestedProviderImpl(String requestedProviderImpl) { this.requestedProviderImpl = requestedProviderImpl; }
    public String getEffectiveProviderImpl() { return effectiveProviderImpl; }
    public void setEffectiveProviderImpl(String effectiveProviderImpl) { this.effectiveProviderImpl = effectiveProviderImpl; }
    public String getProviderConformance() { return providerConformance; }
    public void setProviderConformance(String providerConformance) { this.providerConformance = providerConformance; }
    public Boolean getModelLoaded() { return modelLoaded; }
    public void setModelLoaded(Boolean modelLoaded) { this.modelLoaded = modelLoaded; }
    public Boolean getIndexCompatible() { return indexCompatible; }
    public void setIndexCompatible(Boolean indexCompatible) { this.indexCompatible = indexCompatible; }
    public String getActiveIndexVersion() { return activeIndexVersion; }
    public void setActiveIndexVersion(String activeIndexVersion) { this.activeIndexVersion = activeIndexVersion; }
    public Boolean getFallbackUsed() { return fallbackUsed; }
    public void setFallbackUsed(Boolean fallbackUsed) { this.fallbackUsed = fallbackUsed; }
    public Map<String, Object> getRaw() { return raw; }
    public void setRaw(Map<String, Object> raw) { this.raw = raw; }
}
