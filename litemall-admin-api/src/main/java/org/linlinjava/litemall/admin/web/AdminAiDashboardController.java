package org.linlinjava.litemall.admin.web;

import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.annotation.RequiresPermissionsDesc;
import org.linlinjava.litemall.admin.service.AiRiskTaskService;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.LitemallAiPatrolLog;
import org.linlinjava.litemall.db.service.LitemallAiDemoReviewService;
import org.linlinjava.litemall.db.service.LitemallAiOperationLogService;
import org.linlinjava.litemall.db.service.LitemallAiPatrolLogService;
import org.linlinjava.litemall.db.service.LitemallAiReviewRiskTaskService;
import org.linlinjava.litemall.db.service.LitemallReviewAiAnalysisService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/ai/dashboard")
@Validated
public class AdminAiDashboardController {
    @Autowired
    private LitemallReviewAiAnalysisService reviewAiAnalysisService;
    @Autowired
    private LitemallAiDemoReviewService demoReviewService;
    @Autowired
    private LitemallAiPatrolLogService patrolLogService;
    @Autowired
    private LitemallAiReviewRiskTaskService riskTaskService;
    @Autowired
    private LitemallAiOperationLogService operationLogService;
    @Autowired
    private AiRiskTaskService riskTaskSyncService;

    @Value("${ai.patrol.enabled:false}")
    private Boolean patrolEnabled;

    @RequiresPermissions("admin:ai:review:list")
    @RequiresPermissionsDesc(menu = {"AI工作台", "总览看板"}, button = "查询")
    @GetMapping("/summary")
    public Object summary() {
        riskTaskSyncService.syncFromAnalyses();
        Map<String, Object> summary = new HashMap<String, Object>(reviewAiAnalysisService.statSummary());
        List<LitemallAiPatrolLog> patrolLogs = patrolLogService.latest();
        LitemallAiPatrolLog latestPatrol = patrolLogs.isEmpty() ? null : patrolLogs.get(0);
        summary.put("agentStatus", patrolEnabled ? "running" : "standby");
        summary.put("patrolEnabled", patrolEnabled);
        summary.put("lastPatrolTime", latestPatrol == null ? summary.get("lastAnalysisTime") : latestPatrol.getEndTime());
        summary.put("pendingDemoReviews", countByName(demoReviewService.statByStatus(), "pending"));
        summary.put("pendingRiskTasks", countByName(riskTaskService.statByStatus(), "pending"));
        summary.put("openRiskTasks", countOpenTasks(riskTaskService.statByStatus()));
        summary.put("handledOperationLogs", operationLogService.latest(1000).size());
        return ResponseUtil.ok(summary);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping({"/sentiment-distribution", "/risk-distribution"})
    public Object sentimentDistribution() {
        return ResponseUtil.ok(reviewAiAnalysisService.statSentimentDistribution());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping({"/risk-trend", "/trend"})
    public Object riskTrend() {
        return ResponseUtil.ok(reviewAiAnalysisService.statRiskTrend());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping({"/risk-type-distribution"})
    public Object riskTypeDistribution() {
        return ResponseUtil.ok(reviewAiAnalysisService.statRiskTypeDistribution());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping({"/top-risk-products", "/top-products"})
    public Object topRiskProducts() {
        return ResponseUtil.ok(reviewAiAnalysisService.statTopRiskProducts());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/patrol-summary")
    public Object patrolSummary() {
        Map<String, Object> data = new HashMap<String, Object>();
        List<LitemallAiPatrolLog> logs = patrolLogService.latest();
        LitemallAiPatrolLog latest = logs.isEmpty() ? null : logs.get(0);
        data.put("enabled", patrolEnabled);
        data.put("status", patrolEnabled ? "running" : "standby");
        data.put("lastPatrolTime", latest == null ? reviewAiAnalysisService.statSummary().get("lastAnalysisTime") : latest.getEndTime());
        data.put("latest", latest);
        data.put("recentLogs", logs);
        data.put("message", patrolEnabled ? "Agent patrol is enabled." : "Agent patrol is disabled.");
        return ResponseUtil.ok(data);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/operation-overview")
    public Object operationOverview() {
        riskTaskSyncService.syncFromAnalyses();
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("demoReviewStatus", demoReviewService.statByStatus());
        data.put("riskTaskStatus", riskTaskService.statByStatus());
        data.put("riskTaskLevel", riskTaskService.statByLevel());
        data.put("operationActions", operationLogService.statByActionType());
        data.put("latestOperations", operationLogService.latest(8));
        data.put("latestPatrolLogs", patrolLogService.latest());
        return ResponseUtil.ok(data);
    }

    private Object countByName(List<Map<String, Object>> rows, String name) {
        for (Map<String, Object> row : rows) {
            if (name.equals(row.get("name"))) {
                return row.get("value");
            }
        }
        return 0;
    }

    private int countOpenTasks(List<Map<String, Object>> rows) {
        int count = 0;
        for (Map<String, Object> row : rows) {
            Object name = row.get("name");
            if (!"closed".equals(name) && !"ignored".equals(name)) {
                Object value = row.get("value");
                if (value instanceof Number) {
                    count += ((Number) value).intValue();
                }
            }
        }
        return count;
    }
}
