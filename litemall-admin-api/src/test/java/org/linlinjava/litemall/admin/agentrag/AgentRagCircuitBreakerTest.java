package org.linlinjava.litemall.admin.agentrag;

import org.junit.Test;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagCircuitBreaker;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagCircuitOpenException;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagClock;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.*;

public class AgentRagCircuitBreakerTest {
    @Test
    public void opensAfterFailureThreshold() {
        MutableClock clock = new MutableClock();
        AgentRagCircuitBreaker breaker = new AgentRagCircuitBreaker(2, 1000, 1, clock);
        breaker.recordFailure(true);
        assertEquals(AgentRagCircuitBreaker.State.CLOSED, breaker.getState());
        breaker.recordFailure(true);
        assertEquals(AgentRagCircuitBreaker.State.OPEN, breaker.getState());
        try {
            breaker.beforeCall();
            fail("expected open");
        } catch (AgentRagCircuitOpenException expected) {
            assertEquals("AGENT_RAG_CIRCUIT_OPEN", expected.getErrorCode());
        }
    }

    @Test
    public void halfOpenSuccessCloses() {
        MutableClock clock = new MutableClock();
        AgentRagCircuitBreaker breaker = new AgentRagCircuitBreaker(1, 1000, 1, clock);
        breaker.recordFailure(true);
        clock.advance(1000);
        breaker.beforeCall();
        assertEquals(AgentRagCircuitBreaker.State.HALF_OPEN, breaker.getState());
        breaker.recordSuccess();
        assertEquals(AgentRagCircuitBreaker.State.CLOSED, breaker.getState());
        assertEquals(0, breaker.getFailureCount());
    }

    @Test
    public void halfOpenFailureReopens() {
        MutableClock clock = new MutableClock();
        AgentRagCircuitBreaker breaker = new AgentRagCircuitBreaker(1, 1000, 1, clock);
        breaker.recordFailure(true);
        clock.advance(1000);
        breaker.beforeCall();
        breaker.recordFailure(true);
        assertEquals(AgentRagCircuitBreaker.State.OPEN, breaker.getState());
    }

    @Test
    public void businessFailureDoesNotCount() {
        AgentRagCircuitBreaker breaker = new AgentRagCircuitBreaker(1, 1000, 1, new MutableClock());
        breaker.recordFailure(false);
        assertEquals(AgentRagCircuitBreaker.State.CLOSED, breaker.getState());
    }

    @Test
    public void concurrentBeforeCallWhenOpenIsSafe() throws Exception {
        MutableClock clock = new MutableClock();
        final AgentRagCircuitBreaker breaker = new AgentRagCircuitBreaker(1, 1000, 1, clock);
        breaker.recordFailure(true);
        final AtomicInteger rejected = new AtomicInteger();
        final CountDownLatch latch = new CountDownLatch(8);
        for (int i = 0; i < 8; i++) {
            new Thread(new Runnable() {
                @Override
                public void run() {
                    try {
                        breaker.beforeCall();
                    } catch (AgentRagCircuitOpenException e) {
                        rejected.incrementAndGet();
                    } finally {
                        latch.countDown();
                    }
                }
            }).start();
        }
        latch.await();
        assertEquals(8, rejected.get());
    }

    private static class MutableClock implements AgentRagClock {
        private long now;

        @Override
        public long nowMs() {
            return now;
        }

        void advance(long delta) {
            now += delta;
        }
    }
}
