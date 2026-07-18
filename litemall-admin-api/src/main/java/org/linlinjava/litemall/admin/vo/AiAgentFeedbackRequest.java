package org.linlinjava.litemall.admin.vo;

public class AiAgentFeedbackRequest {
    private Integer riskTaskId;
    private Integer analysisId;
    private String sourceType;
    private Integer sourceId;
    private String feedbackType;
    private String feedbackLabel;
    private String feedbackNote;
    private String operator;

    public Integer getRiskTaskId() { return riskTaskId; }
    public void setRiskTaskId(Integer riskTaskId) { this.riskTaskId = riskTaskId; }
    public Integer getAnalysisId() { return analysisId; }
    public void setAnalysisId(Integer analysisId) { this.analysisId = analysisId; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public Integer getSourceId() { return sourceId; }
    public void setSourceId(Integer sourceId) { this.sourceId = sourceId; }
    public String getFeedbackType() { return feedbackType; }
    public void setFeedbackType(String feedbackType) { this.feedbackType = feedbackType; }
    public String getFeedbackLabel() { return feedbackLabel; }
    public void setFeedbackLabel(String feedbackLabel) { this.feedbackLabel = feedbackLabel; }
    public String getFeedbackNote() { return feedbackNote; }
    public void setFeedbackNote(String feedbackNote) { this.feedbackNote = feedbackNote; }
    public String getOperator() { return operator; }
    public void setOperator(String operator) { this.operator = operator; }
}
