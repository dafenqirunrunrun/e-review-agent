package org.linlinjava.litemall.db.domain;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class LitemallReviewAiAnalysis {
    private Integer id;
    private String sourceType;
    private Integer sourceId;
    private String reviewId;
    private Integer productId;
    private String productName;
    private String reviewText;
    private Integer rating;
    private String imageUrls;
    private String sentimentLabel;
    private BigDecimal confidence;
    private BigDecimal positiveScore;
    private BigDecimal neutralScore;
    private BigDecimal negativeScore;
    private String evidenceJson;
    private String similarCasesJson;
    private String agentSuggestionJson;
    private String workflowTraceJson;
    private LocalDateTime addTime;
    private LocalDateTime updateTime;
    private Boolean deleted;

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public String getSourceType() {
        return sourceType;
    }

    public void setSourceType(String sourceType) {
        this.sourceType = sourceType;
    }

    public Integer getSourceId() {
        return sourceId;
    }

    public void setSourceId(Integer sourceId) {
        this.sourceId = sourceId;
    }

    public String getReviewId() {
        return reviewId;
    }

    public void setReviewId(String reviewId) {
        this.reviewId = reviewId;
    }

    public Integer getProductId() {
        return productId;
    }

    public void setProductId(Integer productId) {
        this.productId = productId;
    }

    public String getProductName() {
        return productName;
    }

    public void setProductName(String productName) {
        this.productName = productName;
    }

    public String getReviewText() {
        return reviewText;
    }

    public void setReviewText(String reviewText) {
        this.reviewText = reviewText;
    }

    public Integer getRating() {
        return rating;
    }

    public void setRating(Integer rating) {
        this.rating = rating;
    }

    public String getImageUrls() {
        return imageUrls;
    }

    public void setImageUrls(String imageUrls) {
        this.imageUrls = imageUrls;
    }

    public String getSentimentLabel() {
        return sentimentLabel;
    }

    public void setSentimentLabel(String sentimentLabel) {
        this.sentimentLabel = sentimentLabel;
    }

    public BigDecimal getConfidence() {
        return confidence;
    }

    public void setConfidence(BigDecimal confidence) {
        this.confidence = confidence;
    }

    public BigDecimal getPositiveScore() {
        return positiveScore;
    }

    public void setPositiveScore(BigDecimal positiveScore) {
        this.positiveScore = positiveScore;
    }

    public BigDecimal getNeutralScore() {
        return neutralScore;
    }

    public void setNeutralScore(BigDecimal neutralScore) {
        this.neutralScore = neutralScore;
    }

    public BigDecimal getNegativeScore() {
        return negativeScore;
    }

    public void setNegativeScore(BigDecimal negativeScore) {
        this.negativeScore = negativeScore;
    }

    public String getEvidenceJson() {
        return evidenceJson;
    }

    public void setEvidenceJson(String evidenceJson) {
        this.evidenceJson = evidenceJson;
    }

    public String getSimilarCasesJson() {
        return similarCasesJson;
    }

    public void setSimilarCasesJson(String similarCasesJson) {
        this.similarCasesJson = similarCasesJson;
    }

    public String getAgentSuggestionJson() {
        return agentSuggestionJson;
    }

    public void setAgentSuggestionJson(String agentSuggestionJson) {
        this.agentSuggestionJson = agentSuggestionJson;
    }

    public String getWorkflowTraceJson() {
        return workflowTraceJson;
    }

    public void setWorkflowTraceJson(String workflowTraceJson) {
        this.workflowTraceJson = workflowTraceJson;
    }

    public LocalDateTime getAddTime() {
        return addTime;
    }

    public void setAddTime(LocalDateTime addTime) {
        this.addTime = addTime;
    }

    public LocalDateTime getUpdateTime() {
        return updateTime;
    }

    public void setUpdateTime(LocalDateTime updateTime) {
        this.updateTime = updateTime;
    }

    public Boolean getDeleted() {
        return deleted;
    }

    public void setDeleted(Boolean deleted) {
        this.deleted = deleted;
    }
}
