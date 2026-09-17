package org.linlinjava.litemall.admin.service.agentrag;

public interface AgentRagClient {
    AgentRagAnalyzeResponse analyze(AgentRagAnalyzeRequest request);

    AgentRagHealthResponse health();
}
