package org.linlinjava.litemall.admin.service.agentrag;

import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class AgentRagRuntimeMetricsService {
    private final AtomicLong requestsTotal = new AtomicLong();
    private final AtomicLong successTotal = new AtomicLong();
    private final AtomicLong failureTotal = new AtomicLong();
    private final AtomicLong fallbackTotal = new AtomicLong();
    private final AtomicLong idempotencyHitTotal = new AtomicLong();
    private final List<Long> latencyMs = Collections.synchronizedList(new ArrayList<Long>());

    public void recordRequest() {
        requestsTotal.incrementAndGet();
    }

    public void recordIdempotencyHit() {
        idempotencyHitTotal.incrementAndGet();
    }

    public void recordSuccess(boolean fallbackUsed, long durationMs) {
        successTotal.incrementAndGet();
        if (fallbackUsed) {
            fallbackTotal.incrementAndGet();
        }
        recordLatency(durationMs);
    }

    public void recordFailure(long durationMs) {
        failureTotal.incrementAndGet();
        recordLatency(durationMs);
    }

    public Map<String, Object> snapshot() {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("requestsTotal", requestsTotal.get());
        data.put("successTotal", successTotal.get());
        data.put("failureTotal", failureTotal.get());
        data.put("fallbackTotal", fallbackTotal.get());
        data.put("idempotencyHitTotal", idempotencyHitTotal.get());
        data.put("latency", latencySnapshot());
        return data;
    }

    private void recordLatency(long durationMs) {
        if (durationMs < 0) {
            return;
        }
        synchronized (latencyMs) {
            latencyMs.add(durationMs);
            if (latencyMs.size() > 2048) {
                latencyMs.remove(0);
            }
        }
    }

    private Map<String, Object> latencySnapshot() {
        List<Long> copy;
        synchronized (latencyMs) {
            copy = new ArrayList<Long>(latencyMs);
        }
        Collections.sort(copy);
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("count", copy.size());
        data.put("minMs", copy.isEmpty() ? 0L : copy.get(0));
        data.put("maxMs", copy.isEmpty() ? 0L : copy.get(copy.size() - 1));
        data.put("p95Ms", percentile(copy, 0.95));
        return data;
    }

    private long percentile(List<Long> values, double percentile) {
        if (values.isEmpty()) {
            return 0L;
        }
        int index = (int) Math.round((values.size() - 1) * percentile);
        return values.get(Math.max(0, Math.min(index, values.size() - 1)));
    }
}
