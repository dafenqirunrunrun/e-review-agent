package org.linlinjava.litemall.admin.vo;

import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;

public class AiRiskHumanReviewResult {
    private Boolean alreadyResolved;
    private String humanDecision;
    private String beforeStatus;
    private String afterStatus;
    private String auditNote;
    private LitemallAiReviewRiskTask task;

    public Boolean getAlreadyResolved() { return alreadyResolved; }
    public void setAlreadyResolved(Boolean alreadyResolved) { this.alreadyResolved = alreadyResolved; }
    public String getHumanDecision() { return humanDecision; }
    public void setHumanDecision(String humanDecision) { this.humanDecision = humanDecision; }
    public String getBeforeStatus() { return beforeStatus; }
    public void setBeforeStatus(String beforeStatus) { this.beforeStatus = beforeStatus; }
    public String getAfterStatus() { return afterStatus; }
    public void setAfterStatus(String afterStatus) { this.afterStatus = afterStatus; }
    public String getAuditNote() { return auditNote; }
    public void setAuditNote(String auditNote) { this.auditNote = auditNote; }
    public LitemallAiReviewRiskTask getTask() { return task; }
    public void setTask(LitemallAiReviewRiskTask task) { this.task = task; }
}
