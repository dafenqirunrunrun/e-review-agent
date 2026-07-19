package org.linlinjava.litemall.admin.util;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

public final class PublicRuntimeMetrics {
    private static final AtomicLong HTTP_REQUEST_TOTAL = new AtomicLong();
    private static final AtomicLong HTTP_ERROR_TOTAL = new AtomicLong();
    private static final AtomicLong HTTP_DURATION_MS_TOTAL = new AtomicLong();
    private static final AtomicLong AI_ANALYSIS_TOTAL = new AtomicLong();
    private static final AtomicLong AI_ANALYSIS_FAILURE_TOTAL = new AtomicLong();

    private PublicRuntimeMetrics() {
    }

    public static void recordHttp(long durationMs, int status) {
        HTTP_REQUEST_TOTAL.incrementAndGet();
        HTTP_DURATION_MS_TOTAL.addAndGet(Math.max(0L, durationMs));
        if (status >= 500) {
            HTTP_ERROR_TOTAL.incrementAndGet();
        }
    }

    public static void recordAiAnalysis(boolean success) {
        AI_ANALYSIS_TOTAL.incrementAndGet();
        if (!success) {
            AI_ANALYSIS_FAILURE_TOTAL.incrementAndGet();
        }
    }

    public static Map<String, Object> snapshot() {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("httpRequestTotal", HTTP_REQUEST_TOTAL.get());
        data.put("httpErrorTotal", HTTP_ERROR_TOTAL.get());
        data.put("httpDurationMsTotal", HTTP_DURATION_MS_TOTAL.get());
        data.put("aiAnalysisTotal", AI_ANALYSIS_TOTAL.get());
        data.put("aiAnalysisFailureTotal", AI_ANALYSIS_FAILURE_TOTAL.get());
        return data;
    }
}
