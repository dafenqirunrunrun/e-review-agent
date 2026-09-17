package org.linlinjava.litemall.admin.vo;

public class AiRiskHumanReviewRequest {
    private Integer id;
    private String humanDecision;
    private String handler;
    private String handleNote;
    private String reasonCode;

    public Integer getId() { return id; }
    public void setId(Integer id) { this.id = id; }
    public String getHumanDecision() { return humanDecision; }
    public void setHumanDecision(String humanDecision) { this.humanDecision = humanDecision; }
    public String getHandler() { return handler; }
    public void setHandler(String handler) { this.handler = handler; }
    public String getHandleNote() { return handleNote; }
    public void setHandleNote(String handleNote) { this.handleNote = handleNote; }
    public String getReasonCode() { return reasonCode; }
    public void setReasonCode(String reasonCode) { this.reasonCode = reasonCode; }
}
