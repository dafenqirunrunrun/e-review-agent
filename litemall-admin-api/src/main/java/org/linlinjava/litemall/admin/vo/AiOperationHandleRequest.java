package org.linlinjava.litemall.admin.vo;

public class AiOperationHandleRequest {
    private Integer riskTaskId;
    private String actionType;
    private String newStatus;
    private String operator;
    private String note;
    private String feedbackType;
    private String feedbackNote;

    public Integer getRiskTaskId() { return riskTaskId; }
    public void setRiskTaskId(Integer riskTaskId) { this.riskTaskId = riskTaskId; }
    public String getActionType() { return actionType; }
    public void setActionType(String actionType) { this.actionType = actionType; }
    public String getNewStatus() { return newStatus; }
    public void setNewStatus(String newStatus) { this.newStatus = newStatus; }
    public String getOperator() { return operator; }
    public void setOperator(String operator) { this.operator = operator; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
    public String getFeedbackType() { return feedbackType; }
    public void setFeedbackType(String feedbackType) { this.feedbackType = feedbackType; }
    public String getFeedbackNote() { return feedbackNote; }
    public void setFeedbackNote(String feedbackNote) { this.feedbackNote = feedbackNote; }
}
