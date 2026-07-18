package org.linlinjava.litemall.db.domain;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class LitemallAiReviewRiskTask {
    private Integer id;
    private Integer analysisId;
    private String sourceType;
    private Integer sourceId;
    private String reviewId;
    private Integer productId;
    private String productName;
    private String reviewText;
    private String imageUrl;
    private String riskType;
    private String riskLevel;
    private String sentimentLabel;
    private BigDecimal confidence;
    private BigDecimal conflictScore;
    private String status;
    private String handler;
    private String handleNote;
    private LocalDateTime createdTime;
    private LocalDateTime updatedTime;
    private Boolean deleted;

    public Integer getId() { return id; }
    public void setId(Integer id) { this.id = id; }
    public Integer getAnalysisId() { return analysisId; }
    public void setAnalysisId(Integer analysisId) { this.analysisId = analysisId; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public Integer getSourceId() { return sourceId; }
    public void setSourceId(Integer sourceId) { this.sourceId = sourceId; }
    public String getReviewId() { return reviewId; }
    public void setReviewId(String reviewId) { this.reviewId = reviewId; }
    public Integer getProductId() { return productId; }
    public void setProductId(Integer productId) { this.productId = productId; }
    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName; }
    public String getReviewText() { return reviewText; }
    public void setReviewText(String reviewText) { this.reviewText = reviewText; }
    public String getImageUrl() { return imageUrl; }
    public void setImageUrl(String imageUrl) { this.imageUrl = imageUrl; }
    public String getRiskType() { return riskType; }
    public void setRiskType(String riskType) { this.riskType = riskType; }
    public String getRiskLevel() { return riskLevel; }
    public void setRiskLevel(String riskLevel) { this.riskLevel = riskLevel; }
    public String getSentimentLabel() { return sentimentLabel; }
    public void setSentimentLabel(String sentimentLabel) { this.sentimentLabel = sentimentLabel; }
    public BigDecimal getConfidence() { return confidence; }
    public void setConfidence(BigDecimal confidence) { this.confidence = confidence; }
    public BigDecimal getConflictScore() { return conflictScore; }
    public void setConflictScore(BigDecimal conflictScore) { this.conflictScore = conflictScore; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getHandler() { return handler; }
    public void setHandler(String handler) { this.handler = handler; }
    public String getHandleNote() { return handleNote; }
    public void setHandleNote(String handleNote) { this.handleNote = handleNote; }
    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
    public LocalDateTime getUpdatedTime() { return updatedTime; }
    public void setUpdatedTime(LocalDateTime updatedTime) { this.updatedTime = updatedTime; }
    public Boolean getDeleted() { return deleted; }
    public void setDeleted(Boolean deleted) { this.deleted = deleted; }
}
