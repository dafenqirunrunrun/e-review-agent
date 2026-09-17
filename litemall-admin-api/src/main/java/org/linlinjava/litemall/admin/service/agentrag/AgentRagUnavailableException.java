package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagUnavailableException extends AgentRagClientException {
    public AgentRagUnavailableException(String errorCode, String message, Throwable cause, int retryCount, long durationMs) {
        super(errorCode, message, cause, retryCount, durationMs);
    }
}
