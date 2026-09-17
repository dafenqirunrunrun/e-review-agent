package org.linlinjava.litemall.admin.service.agentrag;

public class SystemAgentRagClock implements AgentRagClock {
    @Override
    public long nowMs() {
        return System.currentTimeMillis();
    }
}
