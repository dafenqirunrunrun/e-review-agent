package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagTenantMismatchException extends AgentRagClientException {
    public AgentRagTenantMismatchException(String message) {
        super("AGENT_RAG_TENANT_MISMATCH", message);
    }
}
