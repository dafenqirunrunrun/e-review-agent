package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagClientException extends RuntimeException {
    private final String errorCode;
    private final int retryCount;
    private final long durationMs;

    public AgentRagClientException(String errorCode, String message) {
        this(errorCode, message, null, 0, 0L);
    }

    public AgentRagClientException(String errorCode, String message, Throwable cause) {
        this(errorCode, message, cause, 0, 0L);
    }

    public AgentRagClientException(String errorCode, String message, Throwable cause, int retryCount, long durationMs) {
        super(message, cause);
        this.errorCode = errorCode;
        this.retryCount = retryCount;
        this.durationMs = durationMs;
    }

    public String getErrorCode() { return errorCode; }
    public int getRetryCount() { return retryCount; }
    public long getDurationMs() { return durationMs; }
}
