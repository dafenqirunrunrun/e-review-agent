package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagProtocolException extends AgentRagClientException {
    public AgentRagProtocolException(String errorCode, String message) {
        super(errorCode, message);
    }

    public AgentRagProtocolException(String errorCode, String message, Throwable cause) {
        super(errorCode, message, cause);
    }
}
