package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagResponseTooLargeException extends AgentRagClientException {
    public AgentRagResponseTooLargeException() {
        super("AGENT_RAG_RESPONSE_TOO_LARGE", "Agent-RAG response exceeded configured limit.");
    }
}
