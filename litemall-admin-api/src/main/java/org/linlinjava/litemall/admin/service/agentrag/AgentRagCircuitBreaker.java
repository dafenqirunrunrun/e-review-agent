package org.linlinjava.litemall.admin.service.agentrag;

import java.util.HashMap;
import java.util.Map;

public class AgentRagCircuitBreaker {
    public enum State {
        CLOSED, OPEN, HALF_OPEN
    }

    private final int failureThreshold;
    private final long openDurationMs;
    private final int halfOpenMaxCalls;
    private final AgentRagClock clock;
    private State state = State.CLOSED;
    private int failureCount = 0;
    private long openedAt = 0L;
    private int halfOpenInFlight = 0;

    public AgentRagCircuitBreaker(AgentRagConfig config) {
        this(config.getCircuitBreakerFailureThreshold(), config.getCircuitBreakerOpenDurationMs(),
                config.getCircuitBreakerHalfOpenMaxCalls(), new SystemAgentRagClock());
    }

    public AgentRagCircuitBreaker(int failureThreshold, long openDurationMs, int halfOpenMaxCalls, AgentRagClock clock) {
        this.failureThreshold = failureThreshold <= 0 ? 5 : failureThreshold;
        this.openDurationMs = openDurationMs <= 0 ? 30000L : openDurationMs;
        this.halfOpenMaxCalls = halfOpenMaxCalls <= 0 ? 1 : halfOpenMaxCalls;
        this.clock = clock;
    }

    public synchronized void beforeCall() {
        long now = clock.nowMs();
        if (state == State.OPEN && now - openedAt >= openDurationMs) {
            state = State.HALF_OPEN;
            halfOpenInFlight = 0;
        }
        if (state == State.OPEN) {
            throw new AgentRagCircuitOpenException();
        }
        if (state == State.HALF_OPEN) {
            if (halfOpenInFlight >= halfOpenMaxCalls) {
                throw new AgentRagCircuitOpenException();
            }
            halfOpenInFlight++;
        }
    }

    public synchronized void recordSuccess() {
        state = State.CLOSED;
        failureCount = 0;
        openedAt = 0L;
        halfOpenInFlight = 0;
    }

    public synchronized void recordFailure(boolean countsForCircuit) {
        if (!countsForCircuit) {
            return;
        }
        if (state == State.HALF_OPEN) {
            open();
            return;
        }
        failureCount++;
        if (failureCount >= failureThreshold) {
            open();
        }
    }

    private void open() {
        state = State.OPEN;
        openedAt = clock.nowMs();
        halfOpenInFlight = 0;
    }

    public synchronized Map<String, Object> snapshot() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("state", state.name());
        data.put("failureCount", failureCount);
        data.put("openedAt", openedAt == 0L ? null : openedAt);
        data.put("nextProbeAt", openedAt == 0L ? null : openedAt + openDurationMs);
        return data;
    }

    public synchronized State getState() { return state; }
    public synchronized int getFailureCount() { return failureCount; }
}
