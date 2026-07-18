package org.linlinjava.litemall.admin.vo;

public class AiRiskStatusRequest {
    private Integer id;
    private String status;
    private String handler;
    private String handleNote;

    public Integer getId() { return id; }
    public void setId(Integer id) { this.id = id; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getHandler() { return handler; }
    public void setHandler(String handler) { this.handler = handler; }
    public String getHandleNote() { return handleNote; }
    public void setHandleNote(String handleNote) { this.handleNote = handleNote; }
}
