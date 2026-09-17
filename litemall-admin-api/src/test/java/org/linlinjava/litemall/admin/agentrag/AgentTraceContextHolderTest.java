package org.linlinjava.litemall.admin.agentrag;

import org.junit.Test;
import org.linlinjava.litemall.admin.agentrag.trace.AgentTraceContext;
import org.linlinjava.litemall.admin.agentrag.trace.AgentTraceContextHolder;
import org.linlinjava.litemall.admin.agentrag.trace.AgentTracePropagationSigner;

import static org.junit.Assert.*;

public class AgentTraceContextHolderTest {
    @Test
    public void contextIsThreadLocalAndClearable() {
        AgentTraceContext context = new AgentTraceContext("req-12345678", "trace-a", "exec-a",
                "agent-trace.v1", "spring-admin", "2026-07-26T00:00:00Z", "sig");
        AgentTraceContextHolder.set(context);
        assertEquals("trace-a", AgentTraceContextHolder.get().getTraceId());
        AgentTraceContextHolder.clear();
        assertNull(AgentTraceContextHolder.get());
    }

    @Test
    public void signerIsStableAndSensitiveToTraceId() {
        AgentTracePropagationSigner signer = new AgentTracePropagationSigner();
        String first = signer.sign("req-12345678", "trace-a", "exec-a", "agent-trace.v1",
                "spring-admin", "2026-07-26T00:00:00Z", "unit-key");
        String second = signer.sign("req-12345678", "trace-a", "exec-a", "agent-trace.v1",
                "spring-admin", "2026-07-26T00:00:00Z", "unit-key");
        String changed = signer.sign("req-12345678", "trace-b", "exec-a", "agent-trace.v1",
                "spring-admin", "2026-07-26T00:00:00Z", "unit-key");
        assertEquals(first, second);
        assertNotEquals(first, changed);
    }
}
