package org.linlinjava.litemall.admin.service.agentrag;

public class AgentRagOverrideRequest {
    private Long runId;
    private String newRiskLevel;
    private String newAction;
    private String reason;
    private Long operatorId;

    public Long getRunId() {
        return runId;
    }

    public void setRunId(Long runId) {
        this.runId = runId;
    }

    public String getNewRiskLevel() {
        return newRiskLevel;
    }

    public void setNewRiskLevel(String newRiskLevel) {
        this.newRiskLevel = newRiskLevel;
    }

    public String getNewAction() {
        return newAction;
    }

    public void setNewAction(String newAction) {
        this.newAction = newAction;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public Long getOperatorId() {
        return operatorId;
    }

    public void setOperatorId(Long operatorId) {
        this.operatorId = operatorId;
    }
}
