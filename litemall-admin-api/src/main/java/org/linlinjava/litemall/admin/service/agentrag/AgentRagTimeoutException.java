package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagTimeoutException extends AgentRagClientException {
    public AgentRagTimeoutException(String errorCode, String message, Throwable cause, int retryCount, long durationMs) {
        super(errorCode, message, cause, retryCount, durationMs);
    }
}
