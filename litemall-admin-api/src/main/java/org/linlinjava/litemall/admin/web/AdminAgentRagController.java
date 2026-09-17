package org.linlinjava.litemall.admin.web;

import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagAnalyzeRequest;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagClient;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagCircuitBreaker;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagClientException;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagOverrideRequest;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagRetentionExportService;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagRuntimeMetricsService;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagWorkflowResult;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagWorkflowService;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.linlinjava.litemall.db.domain.LitemallAgentRagOverride;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;
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
import java.util.List;
import java.util.Map;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@RestController
@RequestMapping("/admin/agent-rag")
@Validated
public class AdminAgentRagController {
    private static final DateTimeFormatter SQL_TIME = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final int OVERVIEW_MAX_SAMPLE_SIZE = 10000;
    @Autowired
    private AgentRagClient agentRagClient;

    @Autowired
    private AgentRagCircuitBreaker circuitBreaker;

    @Autowired
    private AgentRagWorkflowService workflowService;

    @Autowired
    private AgentRagRuntimeMetricsService metricsService;

    @Autowired
    private AgentRagRetentionExportService retentionExportService;

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/health")
    public Object health() {
        try {
            Map<String, Object> data = new HashMap<String, Object>();
            data.put("runtime", agentRagClient.health());
            data.put("circuitBreaker", circuitBreaker.snapshot());
            data.put("metrics", metricsService.snapshot());
            return ResponseUtil.ok(data);
        } catch (AgentRagClientException e) {
            return ResponseUtil.fail(502, e.getErrorCode() + ": " + e.getMessage());
        }
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/runtime/live")
    public Object live() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("status", "live");
        data.put("service", "admin-agent-rag");
        return ResponseUtil.ok(data);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/runtime/ready")
    public Object ready() {
        Map<String, Object> data = new HashMap<String, Object>();
        try {
            Object runtime = agentRagClient.health();
            data.put("status", "ready");
            data.put("runtime", runtime);
            data.put("circuitBreaker", circuitBreaker.snapshot());
            data.put("metrics", metricsService.snapshot());
            return ResponseUtil.ok(data);
        } catch (AgentRagClientException e) {
            data.put("status", "degraded");
            data.put("reason", e.getErrorCode());
            data.put("circuitBreaker", circuitBreaker.snapshot());
            data.put("metrics", metricsService.snapshot());
            return ResponseUtil.ok(data);
        }
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/runtime/metrics")
    public Object metrics() {
        return ResponseUtil.ok(metricsService.snapshot());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/analyze")
    public Object analyze(@RequestBody AgentRagAnalyzeRequest request) {
        if (request == null) {
            return ResponseUtil.badArgument();
        }
        try {
            return ResponseUtil.ok(toResponse(workflowService.analyze(request)));
        } catch (AgentRagClientException e) {
            return ResponseUtil.fail(502, e.getErrorCode() + ": " + e.getMessage());
        }
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/overview")
    public Object overview(@RequestParam(value = "from", required = false) String from,
                           @RequestParam(value = "to", required = false) String to) {
        try {
            TimeWindow window = timeWindow(from, to, 31);
            return ResponseUtil.ok(workflowService.overview(window.from, window.to, OVERVIEW_MAX_SAMPLE_SIZE));
        } catch (IllegalArgumentException e) {
            return ResponseUtil.badArgumentValue();
        }
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/runs")
    public Object runs(@RequestParam(value = "status", required = false) String status,
                       @RequestParam(value = "limit", defaultValue = "20") Integer limit,
                       @RequestParam(value = "page", defaultValue = "1") Integer page,
                       @RequestParam(value = "subjectType", required = false) String subjectType,
                       @RequestParam(value = "subjectId", required = false) String subjectId,
                       @RequestParam(value = "requestId", required = false) String requestId,
                       @RequestParam(value = "riskLevel", required = false) String riskLevel,
                       @RequestParam(value = "providerImpl", required = false) String providerImpl,
                       @RequestParam(value = "fallbackUsed", required = false) Boolean fallbackUsed,
                       @RequestParam(value = "requiresHumanReview", required = false) Boolean requiresHumanReview,
                       @RequestParam(value = "createdFrom", required = false) String createdFrom,
                       @RequestParam(value = "createdTo", required = false) String createdTo) {
        try {
            TimeWindow window = nullableWindow(createdFrom, createdTo, 31);
            Map<String, Object> data = workflowService.listRuns(subjectType, subjectId, requestId, status, riskLevel,
                    providerImpl, fallbackUsed, requiresHumanReview, window.from, window.to, page, limit);
            return ResponseUtil.ok(data);
        } catch (IllegalArgumentException e) {
            return ResponseUtil.badArgumentValue();
        }
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/runs/{id}")
    public Object runDetail(@PathVariable("id") Long id) {
        try {
            Map<String, Object> data = new HashMap<String, Object>();
            LitemallAgentRagRun run = workflowService.findRun(id);
            data.put("run", run);
            data.put("evidence", workflowService.findEvidence(id));
            data.put("overrideHistory", workflowService.overrideHistory(id));
            data.put("originalDecision", originalDecision(run));
            data.put("effectiveDecision", effectiveDecision(run, workflowService.overrideHistory(id)));
            return ResponseUtil.ok(data);
        } catch (AgentRagClientException e) {
            return ResponseUtil.fail(402, e.getErrorCode() + ": " + e.getMessage());
        }
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/runs/{id}/evidence")
    public Object evidence(@PathVariable("id") Long id) {
        LitemallAgentRagEvidence evidence = workflowService.findEvidence(id);
        if (evidence == null) {
            return ResponseUtil.fail(402, "AGENT_RAG_EVIDENCE_NOT_FOUND");
        }
        return ResponseUtil.ok(evidence);
    }

    @RequiresPermissions("admin:agentRag:security")
    @GetMapping("/runs/{id}/integrity")
    public Object integrity(@PathVariable("id") Long id) {
        try {
            return ResponseUtil.ok(workflowService.verifyIntegrity(id));
        } catch (AgentRagClientException e) {
            return ResponseUtil.fail(402, e.getErrorCode() + ": " + e.getMessage());
        }
    }

    @RequiresPermissions("admin:agentRag:security")
    @GetMapping("/security/status")
    public Object securityStatus() {
        return ResponseUtil.ok(workflowService.securityStatus());
    }

    @RequiresPermissions("admin:agentRag:retention")
    @GetMapping("/security/retention/status")
    public Object retentionStatus() {
        return ResponseUtil.ok(retentionExportService.retentionStatus());
    }

    @RequiresPermissions("admin:agentRag:retention")
    @PostMapping("/security/retention/preview")
    public Object retentionPreview(@RequestBody(required = false) Map<String, Object> request) {
        return ResponseUtil.ok(retentionExportService.previewRetention(integerValue(request, "limit")));
    }

    @RequiresPermissions("admin:agentRag:retention")
    @PostMapping("/security/retention/execute")
    public Object retentionExecute(@RequestBody(required = false) Map<String, Object> request) {
        return ResponseUtil.ok(retentionExportService.executeRetention(integerValue(request, "limit")));
    }

    @RequiresPermissions("admin:agentRag:export")
    @PostMapping("/runs/{id}/export")
    public Object secureExport(@PathVariable("id") Long id) {
        try {
            return ResponseUtil.ok(retentionExportService.secureExport(id));
        } catch (AgentRagClientException e) {
            return ResponseUtil.fail(402, e.getErrorCode() + ": " + e.getMessage());
        }
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/runs/{id}/compare/{otherRunId}")
    public Object compare(@PathVariable("id") Long id, @PathVariable("otherRunId") Long otherRunId) {
        try {
            return ResponseUtil.ok(workflowService.compareRuns(id, otherRunId));
        } catch (AgentRagClientException e) {
            return ResponseUtil.fail(402, e.getErrorCode() + ": " + e.getMessage());
        }
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/runs/{id}/replay")
    public Object replay(@PathVariable("id") Long id) {
        try {
            return ResponseUtil.ok(toResponse(workflowService.replay(id)));
        } catch (AgentRagClientException e) {
            return ResponseUtil.fail(502, e.getErrorCode() + ": " + e.getMessage());
        }
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/override")
    public Object override(@RequestBody AgentRagOverrideRequest request) {
        if (request == null) {
            return ResponseUtil.badArgument();
        }
        try {
            LitemallAgentRagOverride override = workflowService.appendOverride(request);
            return ResponseUtil.ok(override);
        } catch (AgentRagClientException e) {
            return ResponseUtil.fail(402, e.getErrorCode() + ": " + e.getMessage());
        }
    }

    private Map<String, Object> toResponse(AgentRagWorkflowResult result) {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("run", result.getRun());
        data.put("evidence", result.getEvidence());
        data.put("response", result.getResponse());
        data.put("idempotentReplay", result.isIdempotentReplay());
        return data;
    }

    private Map<String, Object> originalDecision(LitemallAgentRagRun run) {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("riskLevel", run.getRiskLevel());
        data.put("action", run.getAction());
        data.put("requiresHumanReview", run.getRequiresHumanReview());
        data.put("confidence", run.getConfidence());
        return data;
    }

    private Map<String, Object> effectiveDecision(LitemallAgentRagRun run, List<LitemallAgentRagOverride> overrides) {
        Map<String, Object> data = originalDecision(run);
        if (overrides != null && !overrides.isEmpty()) {
            LitemallAgentRagOverride latest = overrides.get(0);
            data.put("riskLevel", latest.getNewRiskLevel());
            data.put("action", latest.getNewAction());
            data.put("overrideId", latest.getId());
            data.put("overridden", true);
        } else {
            data.put("overridden", false);
        }
        return data;
    }

    private TimeWindow timeWindow(String from, String to, int maxDays) {
        LocalDateTime end = parseTime(to, LocalDateTime.now());
        LocalDateTime start = parseTime(from, end.toLocalDate().atStartOfDay());
        if (start.isAfter(end) || start.plusDays(maxDays).isBefore(end)) {
            throw new IllegalArgumentException("time window invalid");
        }
        return new TimeWindow(SQL_TIME.format(start), SQL_TIME.format(end));
    }

    private TimeWindow nullableWindow(String from, String to, int maxDays) {
        if ((from == null || from.trim().length() == 0) && (to == null || to.trim().length() == 0)) {
            LocalDateTime end = LocalDateTime.now();
            return new TimeWindow(SQL_TIME.format(end.minusDays(7)), SQL_TIME.format(end));
        }
        return timeWindow(from, to, maxDays);
    }

    private LocalDateTime parseTime(String value, LocalDateTime fallback) {
        if (value == null || value.trim().length() == 0) {
            return fallback;
        }
        String normalized = value.trim().replace("T", " ");
        if (normalized.length() == 10) {
            normalized = normalized + " 00:00:00";
        }
        if (normalized.length() > 19) {
            normalized = normalized.substring(0, 19);
        }
        return LocalDateTime.parse(normalized, SQL_TIME);
    }

    private Integer integerValue(Map<String, Object> request, String key) {
        if (request == null || !request.containsKey(key) || request.get(key) == null) {
            return null;
        }
        Object value = request.get(key);
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        try {
            return Integer.valueOf(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static class TimeWindow {
        private final String from;
        private final String to;

        private TimeWindow(String from, String to) {
            this.from = from;
            this.to = to;
        }
    }
}
