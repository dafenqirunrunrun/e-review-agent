package org.linlinjava.litemall.admin.agentrag.trace;

public final class AgentTraceHeaders {
    public static final String REQUEST_ID = "X-EReview-Request-Id";
    public static final String TRACE_ID = "X-EReview-Trace-Id";
    public static final String EXECUTION_ID = "X-EReview-Execution-Id";
    public static final String TRACE_SCHEMA = "X-EReview-Trace-Schema";
    public static final String ISSUED_AT = "X-EReview-Trace-Issued-At";
    public static final String CALLER = "X-EReview-Trace-Caller";
    public static final String SIGNATURE = "X-EReview-Trace-Signature";

    private AgentTraceHeaders() {
    }
}
