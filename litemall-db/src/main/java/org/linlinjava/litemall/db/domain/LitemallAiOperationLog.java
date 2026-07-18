package org.linlinjava.litemall.db.domain;

import java.time.LocalDateTime;

public class LitemallAiOperationLog {
    private Integer id;
    private Integer riskTaskId;
    private String actionType;
    private String oldStatus;
    private String newStatus;
    private String operator;
    private String note;
    private LocalDateTime createdTime;

    public Integer getId() { return id; }
    public void setId(Integer id) { this.id = id; }
    public Integer getRiskTaskId() { return riskTaskId; }
    public void setRiskTaskId(Integer riskTaskId) { this.riskTaskId = riskTaskId; }
    public String getActionType() { return actionType; }
    public void setActionType(String actionType) { this.actionType = actionType; }
    public String getOldStatus() { return oldStatus; }
    public void setOldStatus(String oldStatus) { this.oldStatus = oldStatus; }
    public String getNewStatus() { return newStatus; }
    public void setNewStatus(String newStatus) { this.newStatus = newStatus; }
    public String getOperator() { return operator; }
    public void setOperator(String operator) { this.operator = operator; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
}
