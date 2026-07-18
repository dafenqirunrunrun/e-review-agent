package org.linlinjava.litemall.admin.service;

import org.linlinjava.litemall.admin.vo.AiOperationHandleRequest;
import org.linlinjava.litemall.db.domain.LitemallAiOperationLog;
import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;
import org.linlinjava.litemall.db.service.LitemallAiOperationLogService;
import org.linlinjava.litemall.db.service.LitemallAiReviewRiskTaskService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class AiOperationService {
    @Autowired
    private AiRiskTaskService riskTaskSyncService;

    @Autowired
    private LitemallAiReviewRiskTaskService riskTaskService;

    @Autowired
    private LitemallAiOperationLogService operationLogService;

    @Autowired
    private AgentPlatformService agentPlatformService;

    public List<LitemallAiReviewRiskTask> list(String status, Integer page, Integer limit) {
        riskTaskSyncService.syncFromAnalyses();
        return riskTaskService.querySelective(null, null, status, page, limit);
    }

    public Map<String, Object> detail(Integer id) {
        Map<String, Object> data = riskTaskSyncService.detail(id);
        data.put("logs", operationLogService.queryByRiskTaskId(id));
        return data;
    }

    public void handle(AiOperationHandleRequest request) {
        LitemallAiReviewRiskTask task = riskTaskService.findById(request.getRiskTaskId());
        String oldStatus = task == null ? null : task.getStatus();
        riskTaskService.updateStatus(request.getRiskTaskId(), request.getNewStatus(), request.getOperator(), request.getNote());
        LitemallAiOperationLog log = new LitemallAiOperationLog();
        log.setRiskTaskId(request.getRiskTaskId());
        log.setActionType(request.getActionType());
        log.setOldStatus(oldStatus);
        log.setNewStatus(request.getNewStatus());
        log.setOperator(request.getOperator());
        log.setNote(request.getNote());
        operationLogService.add(log);
        agentPlatformService.createFeedback(request.getRiskTaskId(), task == null ? null : task.getAnalysisId(),
                task == null ? null : task.getSourceType(), task == null ? null : task.getSourceId(),
                request.getFeedbackType() == null ? "accept" : request.getFeedbackType(),
                request.getFeedbackType() == null ? "Accepted by operation" : request.getFeedbackType(),
                request.getFeedbackNote() == null ? request.getNote() : request.getFeedbackNote(),
                request.getOperator());
    }

    public List<LitemallAiOperationLog> logs(Integer riskTaskId) {
        return operationLogService.queryByRiskTaskId(riskTaskId);
    }

    public Map<String, Object> summary() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("status", riskTaskService.statByStatus());
        return data;
    }
}
