package org.linlinjava.litemall.db.domain;

import java.time.LocalDateTime;

public class LitemallAiCaseKnowledge {
    private Integer id;
    private String caseTitle;
    private String sourceType;
    private Integer sourceId;
    private Integer productId;
    private String productName;
    private String commentText;
    private String imageSignal;
    private String sentimentLabel;
    private String riskTypes;
    private String riskLevel;
    private String evidence;
    private String operationResult;
    private String feedbackType;
    private String tags;
    private LocalDateTime createdTime;
    private LocalDateTime updatedTime;
    private Boolean deleted;

    public Integer getId() { return id; }
    public void setId(Integer id) { this.id = id; }
    public String getCaseTitle() { return caseTitle; }
    public void setCaseTitle(String caseTitle) { this.caseTitle = caseTitle; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public Integer getSourceId() { return sourceId; }
    public void setSourceId(Integer sourceId) { this.sourceId = sourceId; }
    public Integer getProductId() { return productId; }
    public void setProductId(Integer productId) { this.productId = productId; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName; }
    public String getCommentText() { return commentText; }
    public void setCommentText(String commentText) { this.commentText = commentText; }
    public String getImageSignal() { return imageSignal; }
    public void setImageSignal(String imageSignal) { this.imageSignal = imageSignal; }
    public String getSentimentLabel() { return sentimentLabel; }
    public void setSentimentLabel(String sentimentLabel) { this.sentimentLabel = sentimentLabel; }
    public String getRiskTypes() { return riskTypes; }
    public void setRiskTypes(String riskTypes) { this.riskTypes = riskTypes; }
    public String getRiskLevel() { return riskLevel; }
    public void setRiskLevel(String riskLevel) { this.riskLevel = riskLevel; }
    public String getEvidence() { return evidence; }
    public void setEvidence(String evidence) { this.evidence = evidence; }
    public String getOperationResult() { return operationResult; }
    public void setOperationResult(String operationResult) { this.operationResult = operationResult; }
    public String getFeedbackType() { return feedbackType; }
    public void setFeedbackType(String feedbackType) { this.feedbackType = feedbackType; }
    public String getTags() { return tags; }
    public void setTags(String tags) { this.tags = tags; }
    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
    public LocalDateTime getUpdatedTime() { return updatedTime; }
    public void setUpdatedTime(LocalDateTime updatedTime) { this.updatedTime = updatedTime; }
    public Boolean getDeleted() { return deleted; }
    public void setDeleted(Boolean deleted) { this.deleted = deleted; }
}
