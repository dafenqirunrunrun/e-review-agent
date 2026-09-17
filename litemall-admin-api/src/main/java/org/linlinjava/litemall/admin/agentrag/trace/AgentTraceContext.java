package org.linlinjava.litemall.admin.agentrag.trace;

public class AgentTraceContext {
    private final String requestId;
    private final String traceId;
    private final String executionId;
    private final String traceSchemaVersion;
    private final String callerService;
    private final String issuedAtUtc;
    private final String signature;

    public AgentTraceContext(String requestId, String traceId, String executionId, String traceSchemaVersion,
                             String callerService, String issuedAtUtc, String signature) {
        this.requestId = requestId;
        this.traceId = traceId;
        this.executionId = executionId;
        this.traceSchemaVersion = traceSchemaVersion;
        this.callerService = callerService;
        this.issuedAtUtc = issuedAtUtc;
        this.signature = signature;
    }

    public String getRequestId() {
        return requestId;
    }

    public String getTraceId() {
        return traceId;
    }

    public String getExecutionId() {
        return executionId;
    }

    public String getTraceSchemaVersion() {
        return traceSchemaVersion;
    }

    public String getCallerService() {
        return callerService;
    }

    public String getIssuedAtUtc() {
        return issuedAtUtc;
    }

    public String getSignature() {
        return signature;
    }
}
