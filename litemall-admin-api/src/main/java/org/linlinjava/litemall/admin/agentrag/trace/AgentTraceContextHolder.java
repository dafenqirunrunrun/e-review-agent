package org.linlinjava.litemall.admin.agentrag.trace;

public final class AgentTraceContextHolder {
    private static final ThreadLocal<AgentTraceContext> CURRENT = new ThreadLocal<AgentTraceContext>();

    private AgentTraceContextHolder() {
    }

    public static void set(AgentTraceContext context) {
        CURRENT.set(context);
    }

    public static AgentTraceContext get() {
        return CURRENT.get();
    }

    public static void clear() {
        CURRENT.remove();
    }
}
