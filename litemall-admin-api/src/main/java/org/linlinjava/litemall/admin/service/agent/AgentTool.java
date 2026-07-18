package org.linlinjava.litemall.admin.service.agent;

public interface AgentTool {
    String name();

    AgentToolResult execute(AgentToolContext context);
}
