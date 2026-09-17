package org.linlinjava.litemall.admin.agentrag;

import org.junit.Test;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagRuntimeMetricsService;

import java.util.Map;

import static org.junit.Assert.assertEquals;

public class AgentRagRuntimeMetricsServiceTest {
    @Test
    public void recordsCountersAndLatencySnapshot() {
        AgentRagRuntimeMetricsService metrics = new AgentRagRuntimeMetricsService();

        metrics.recordRequest();
        metrics.recordRequest();
        metrics.recordIdempotencyHit();
        metrics.recordSuccess(true, 25L);
        metrics.recordFailure(50L);

        Map<String, Object> snapshot = metrics.snapshot();
        Map<String, Object> latency = (Map<String, Object>) snapshot.get("latency");

        assertEquals(2L, snapshot.get("requestsTotal"));
        assertEquals(1L, snapshot.get("successTotal"));
        assertEquals(1L, snapshot.get("failureTotal"));
        assertEquals(1L, snapshot.get("fallbackTotal"));
        assertEquals(1L, snapshot.get("idempotencyHitTotal"));
        assertEquals(2, latency.get("count"));
        assertEquals(50L, latency.get("maxMs"));
    }
}
