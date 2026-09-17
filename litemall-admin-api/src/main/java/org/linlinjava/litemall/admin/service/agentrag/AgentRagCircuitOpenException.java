package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagCircuitOpenException extends AgentRagClientException {
    public AgentRagCircuitOpenException() {
        super("AGENT_RAG_CIRCUIT_OPEN", "Agent-RAG circuit breaker is open.");
    }
}
