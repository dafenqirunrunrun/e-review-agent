package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagTenantResolver {
    private final AgentRagConfig config;

    public AgentRagTenantResolver(AgentRagConfig config) {
        this.config = config;
    }

    public String resolveCurrentTenant() {
        String tenantId = config.getSingleTenantId();
        if (tenantId == null || tenantId.trim().length() == 0) {
            throw new AgentRagClientException("AGENT_RAG_TENANT_MISSING", "Tenant is not configured.");
        }
        return tenantId.trim();
    }

    public void applyTrustedTenant(AgentRagAnalyzeRequest request) {
        request.setTenantId(resolveCurrentTenant());
    }
}
