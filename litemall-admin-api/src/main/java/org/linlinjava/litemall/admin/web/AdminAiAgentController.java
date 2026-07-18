package org.linlinjava.litemall.admin.web;

import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.service.AgentPlatformService;
import org.linlinjava.litemall.admin.service.AiReviewService;
import org.linlinjava.litemall.admin.vo.AiAgentFeedbackRequest;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/admin/ai/agent")
@Validated
public class AdminAiAgentController {
    @Autowired
    private AgentPlatformService agentPlatformService;

    @Autowired
    private AiReviewService aiReviewService;

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/run/list")
    public Object runList(@RequestParam(value = "status", required = false) String status,
                          @RequestParam(value = "sourceType", required = false) String sourceType,
                          @RequestParam(value = "triggerType", required = false) String triggerType,
                          @RequestParam(value = "page", defaultValue = "1") Integer page,
                          @RequestParam(value = "limit", defaultValue = "10") Integer limit) {
        return ResponseUtil.ok(agentPlatformService.listRuns(status, sourceType, triggerType, page, limit));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/run/detail/{id}")
    public Object runDetail(@PathVariable("id") Integer id) {
        return ResponseUtil.ok(agentPlatformService.detail(id));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/run/steps/{runId}")
    public Object runSteps(@PathVariable("runId") Integer runId) {
        return ResponseUtil.ok(agentPlatformService.steps(runId));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/run/state/{runId}")
    public Object runState(@PathVariable("runId") Integer runId) {
        return ResponseUtil.ok(agentPlatformService.state(runId));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/run/replay-preview/{runId}")
    public Object replayPreview(@PathVariable("runId") Integer runId) {
        return ResponseUtil.ok(agentPlatformService.replayPreview(runId));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/run/replay/{runId}")
    public Object replay(@PathVariable("runId") Integer runId) {
        return ResponseUtil.ok(agentPlatformService.replay(runId));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/run/replay-compare/{runId}")
    public Object replayCompare(@PathVariable("runId") Integer runId) {
        return ResponseUtil.ok(agentPlatformService.replayCompare(runId));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/run/compare")
    public Object compareRuns(@RequestParam("leftRunId") Integer leftRunId,
                              @RequestParam("rightRunId") Integer rightRunId) {
        return ResponseUtil.ok(agentPlatformService.compareRuns(leftRunId, rightRunId));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/feedback/create")
    public Object createFeedback(@RequestBody AiAgentFeedbackRequest request) {
        if (request == null) {
            return ResponseUtil.badArgumentValue();
        }
        agentPlatformService.createFeedback(request.getRiskTaskId(), request.getAnalysisId(), request.getSourceType(),
                request.getSourceId(), request.getFeedbackType(), request.getFeedbackLabel(), request.getFeedbackNote(), request.getOperator());
        return ResponseUtil.ok();
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/feedback/list")
    public Object feedbackList(@RequestParam(value = "feedbackType", required = false) String feedbackType,
                               @RequestParam(value = "page", defaultValue = "1") Integer page,
                               @RequestParam(value = "limit", defaultValue = "10") Integer limit) {
        return ResponseUtil.ok(agentPlatformService.listFeedback(feedbackType, page, limit));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/feedback/stats")
    public Object feedbackStats() {
        return ResponseUtil.ok(agentPlatformService.feedbackStats());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/eval/summary")
    public Object evalSummary() {
        Map<String, Object> data = new HashMap<String, Object>(agentPlatformService.evalSummary());
        data.put("recentFailedRuns", agentPlatformService.recentFailedRuns());
        return ResponseUtil.ok(data);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/eval/trend")
    public Object evalTrend() {
        return ResponseUtil.ok(agentPlatformService.evalTrend());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/eval/tool-stats")
    public Object toolStats() {
        return ResponseUtil.ok(agentPlatformService.toolStats());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/eval/feedback-stats")
    public Object evalFeedbackStats() {
        return ResponseUtil.ok(agentPlatformService.feedbackStats());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/quality/summary")
    public Object qualitySummary() {
        return ResponseUtil.ok(agentPlatformService.qualitySummary());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/diagnostics/summary")
    public Object diagnosticsSummary() {
        return ResponseUtil.ok(agentPlatformService.diagnosticsSummary());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/diagnostics/recent-failures")
    public Object diagnosticsRecentFailures() {
        return ResponseUtil.ok(agentPlatformService.recentFailures());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/diagnostics/failure-groups")
    public Object diagnosticsFailureGroups() {
        return ResponseUtil.ok(agentPlatformService.failureGroups());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/diagnostics/health")
    public Object diagnosticsHealth() {
        return ResponseUtil.ok(agentPlatformService.health());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/framework/status")
    public Object frameworkStatus() {
        try {
            return ResponseUtil.ok(aiReviewService.frameworkStatus());
        } catch (AiReviewService.AiReviewServiceException e) {
            Map<String, Object> data = new HashMap<String, Object>();
            data.put("available", false);
            data.put("currentMode", "unavailable");
            data.put("error", "AI Agent Framework status is temporarily unavailable. Please check the AI service.");
            return ResponseUtil.ok(data);
        }
    }
}
