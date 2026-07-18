package org.linlinjava.litemall.admin.util;

import org.slf4j.MDC;

import java.util.UUID;

public final class PublicRequestContext {
    public static final String REQUEST_ID_HEADER = "X-Request-ID";
    public static final String MDC_KEY = "request_id";

    private static final ThreadLocal<String> REQUEST_ID = new ThreadLocal<String>();

    private PublicRequestContext() {
    }

    public static String currentOrCreate() {
        String requestId = REQUEST_ID.get();
        if (isBlank(requestId)) {
            requestId = MDC.get(MDC_KEY);
        }
        if (isBlank(requestId)) {
            requestId = UUID.randomUUID().toString();
            set(requestId);
        }
        return requestId;
    }

    public static void set(String requestId) {
        if (isBlank(requestId)) {
            requestId = UUID.randomUUID().toString();
        }
        REQUEST_ID.set(requestId);
        MDC.put(MDC_KEY, requestId);
    }

    public static void clear() {
        REQUEST_ID.remove();
        MDC.remove(MDC_KEY);
    }

    public static boolean isBlank(String value) {
        return value == null || value.trim().length() == 0;
    }
}
