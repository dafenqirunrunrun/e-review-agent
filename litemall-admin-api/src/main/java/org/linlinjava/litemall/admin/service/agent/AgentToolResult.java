package org.linlinjava.litemall.admin.service.agent;

public class AgentToolResult {
    private boolean success;
    private Object output;
    private String errorMessage;

    public static AgentToolResult success(Object output) {
        AgentToolResult result = new AgentToolResult();
        result.setSuccess(true);
        result.setOutput(output);
        return result;
    }

    public static AgentToolResult failed(String errorMessage) {
        AgentToolResult result = new AgentToolResult();
        result.setSuccess(false);
        result.setErrorMessage(errorMessage);
        return result;
    }

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public Object getOutput() {
        return output;
    }

    public void setOutput(Object output) {
        this.output = output;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }
}
