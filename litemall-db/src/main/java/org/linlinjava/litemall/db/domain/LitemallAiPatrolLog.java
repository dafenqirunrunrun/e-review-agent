package org.linlinjava.litemall.db.domain;

import java.time.LocalDateTime;

public class LitemallAiPatrolLog {
    private Integer id;
    private String taskBatchNo;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private Integer scanCount;
    private Integer successCount;
    private Integer failedCount;
    private Integer highRiskCount;
    private String status;
    private String errorMessage;
    private LocalDateTime createdTime;

    public Integer getId() { return id; }
    public void setId(Integer id) { this.id = id; }
    public String getTaskBatchNo() { return taskBatchNo; }
    public void setTaskBatchNo(String taskBatchNo) { this.taskBatchNo = taskBatchNo; }
    public LocalDateTime getStartTime() { return startTime; }
    public void setStartTime(LocalDateTime startTime) { this.startTime = startTime; }
    public LocalDateTime getEndTime() { return endTime; }
    public void setEndTime(LocalDateTime endTime) { this.endTime = endTime; }
    public Integer getScanCount() { return scanCount; }
    public void setScanCount(Integer scanCount) { this.scanCount = scanCount; }
    public Integer getSuccessCount() { return successCount; }
    public void setSuccessCount(Integer successCount) { this.successCount = successCount; }
    public Integer getFailedCount() { return failedCount; }
    public void setFailedCount(Integer failedCount) { this.failedCount = failedCount; }
    public Integer getHighRiskCount() { return highRiskCount; }
    public void setHighRiskCount(Integer highRiskCount) { this.highRiskCount = highRiskCount; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
}
