package org.linlinjava.litemall.admin.web;

import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.service.AiReviewService;
import org.linlinjava.litemall.admin.service.EnterpriseAgentPlatformService;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/admin/ai")
@Validated
public class AdminAiEnterpriseController {
    @Autowired
    private EnterpriseAgentPlatformService enterpriseService;

    @Autowired
    private AiReviewService aiReviewService;

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/enterprise/health")
    public Object enterpriseHealth() {
        return ResponseUtil.ok(aiReviewService.enterpriseHealth());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/enterprise/runtime-status")
    public Object enterpriseRuntimeStatus() {
        return ResponseUtil.ok(aiReviewService.enterpriseRuntimeStatus());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/enterprise/metrics")
    public Object enterpriseMetrics() {
        return ResponseUtil.ok(aiReviewService.enterpriseMetrics());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/enterprise/analyze")
    public Object enterpriseAnalyze(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(aiReviewService.enterpriseAnalyze(body));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/enterprise/analyze-rag")
    public Object enterpriseAnalyzeRag(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(aiReviewService.enterpriseAnalyzeRag(body));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/registry/list")
    public Object toolRegistryList() {
        return ResponseUtil.ok(enterpriseService.toolRegistryList());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/registry/detail")
    public Object toolRegistryDetail(@RequestParam("toolName") String toolName) {
        return ResponseUtil.ok(enterpriseService.toolRegistryDetail(toolName));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/tool/registry/update-enabled")
    public Object updateToolEnabled(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(enterpriseService.updateToolEnabled(String.valueOf(body.get("toolName")), Boolean.valueOf(String.valueOf(body.get("enabled")))));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/manifest/local")
    public Object toolManifestLocal() {
        return ResponseUtil.ok(enterpriseService.toolManifest("local"));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/manifest/openapi")
    public Object toolManifestOpenApi() {
        return ResponseUtil.ok(enterpriseService.toolManifest("openapi"));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/manifest/mcp-like")
    public Object toolManifestMcpLike() {
        return ResponseUtil.ok(enterpriseService.toolManifest("mcp-like"));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/manifest/download")
    public ResponseEntity<String> toolManifestDownload(@RequestParam(value = "format", defaultValue = "local") String format) {
        String json = enterpriseService.toolManifestJson(format);
        String fileName = enterpriseService.toolManifestFileName(format);
        HttpHeaders headers = new HttpHeaders();
        headers.add(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + fileName + "\"");
        return ResponseEntity.ok()
                .headers(headers)
                .contentType(MediaType.APPLICATION_JSON_UTF8)
                .body(json);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/schema/validate")
    public Object validateToolSchema() {
        return ResponseUtil.ok(enterpriseService.validateToolSchemas());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/tool/schema/test")
    public Object testToolSchema() {
        return ResponseUtil.ok(enterpriseService.testToolContracts());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/schema/report")
    public Object toolSchemaReport() {
        return ResponseUtil.ok(enterpriseService.toolSchemaReport());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/policy/list")
    public Object toolPolicyList() {
        return ResponseUtil.ok(enterpriseService.toolPolicyList());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/tool/policy/update")
    public Object updateToolPolicy(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(enterpriseService.updatePolicy(body));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/execution/logs")
    public Object executionLogs(@RequestParam(value = "toolName", required = false) String toolName,
                                @RequestParam(value = "runId", required = false) Integer runId,
                                @RequestParam(value = "status", required = false) String status,
                                @RequestParam(value = "page", defaultValue = "1") Integer page,
                                @RequestParam(value = "limit", defaultValue = "10") Integer limit) {
        return ResponseUtil.ok(enterpriseService.executionLogs(toolName, runId, status, page, limit));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/execution/unregistered")
    public Object unregisteredToolExecutions() {
        return ResponseUtil.ok(enterpriseService.unregisteredToolExecutions());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/execution/summary")
    public Object toolExecutionSummary() {
        return ResponseUtil.ok(enterpriseService.toolExecutionSummary());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/approval/pending")
    public Object pendingApprovals() {
        return ResponseUtil.ok(enterpriseService.pendingApprovals());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/approval/list")
    public Object approvalList(@RequestParam(value = "status", required = false) String status) {
        return ResponseUtil.ok(enterpriseService.approvalList(status));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/approval/detail")
    public Object approvalDetail(@RequestParam("id") String id) {
        return ResponseUtil.ok(enterpriseService.approvalDetail(id));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/tool/approval/approve")
    public Object approve(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(enterpriseService.approve(String.valueOf(body.get("toolName")), String.valueOf(body.get("operator"))));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/tool/approval/reject")
    public Object reject(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(enterpriseService.reject(String.valueOf(body.get("toolName")), String.valueOf(body.get("operator"))));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/tool/approval/mark-executed")
    public Object markApprovalExecuted(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(enterpriseService.markApprovalExecuted(String.valueOf(body.get("id")), String.valueOf(body.get("operator"))));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/tool/approval/mark-reviewed")
    public Object markApprovalReviewed(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(enterpriseService.markApprovalReviewed(String.valueOf(body.get("id")), String.valueOf(body.get("operator"))));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/tool/approval/timeline")
    public Object approvalTimeline(@RequestParam("id") String id) {
        return ResponseUtil.ok(enterpriseService.approvalTimeline(id));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/memory/profile/list")
    public Object memoryProfileList(@RequestParam(value = "entityType", required = false) String entityType,
                                    @RequestParam(value = "page", defaultValue = "1") Integer page,
                                    @RequestParam(value = "limit", defaultValue = "10") Integer limit) {
        return ResponseUtil.ok(enterpriseService.memoryProfiles(entityType, page, limit));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/memory/profile/detail")
    public Object memoryProfileDetail(@RequestParam("entityType") String entityType,
                                      @RequestParam("entityId") String entityId) {
        return ResponseUtil.ok(enterpriseService.memoryDetail(entityType, entityId));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/memory/rebuild")
    public Object rebuildMemory() {
        return ResponseUtil.ok(enterpriseService.rebuildMemory());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/guardrail/events")
    public Object guardrailEvents() {
        return ResponseUtil.ok(enterpriseService.guardrailEvents());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/guardrail/summary")
    public Object guardrailSummary() {
        return ResponseUtil.ok(enterpriseService.guardrailSummary());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/guardrail/test")
    public Object guardrailTest(@RequestBody Map<String, Object> body) {
        return ResponseUtil.ok(enterpriseService.guardrailTest(String.valueOf(body.get("text"))));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/summary")
    public Object agentOpsSummary() {
        return ResponseUtil.ok(enterpriseService.agentOpsSummary());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/trends")
    public Object agentOpsTrends(@RequestParam(value = "range", defaultValue = "7d") String range) {
        return ResponseUtil.ok(enterpriseService.agentOpsTrends(range));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/recent-runs")
    public Object agentOpsRecentRuns(@RequestParam(value = "limit", defaultValue = "20") Integer limit) {
        return ResponseUtil.ok(enterpriseService.agentOpsRecentRuns(limit));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/failure-top")
    public Object agentOpsFailureTop() {
        return ResponseUtil.ok(enterpriseService.agentOpsFailureTop());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/tool-failure-top")
    public Object agentOpsToolFailureTop() {
        return ResponseUtil.ok(enterpriseService.agentOpsToolFailureTop());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/fallback-distribution")
    public Object agentOpsFallbackDistribution() {
        return ResponseUtil.ok(enterpriseService.agentOpsFallbackDistribution());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/guardrail-trend")
    public Object agentOpsGuardrailTrend() {
        return ResponseUtil.ok(enterpriseService.agentOpsGuardrailTrend());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/rag-trend")
    public Object agentOpsRagTrend() {
        return ResponseUtil.ok(enterpriseService.agentOpsRagTrend());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/quality-trend")
    public Object agentOpsQualityTrend() {
        return ResponseUtil.ok(enterpriseService.agentOpsQualityTrend());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agentops/slo")
    public Object agentOpsSlo() {
        return ResponseUtil.ok(enterpriseService.agentOpsSlo());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agent/registry/list")
    public Object agentRegistryList() {
        return ResponseUtil.ok(enterpriseService.agentRegistryList());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/agent/registry/detail")
    public Object agentRegistryDetail(@RequestParam("name") String name) {
        return ResponseUtil.ok(enterpriseService.agentRegistryDetail(name));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/rag/quality/summary")
    public Object ragQualitySummary() {
        return ResponseUtil.ok(enterpriseService.ragQualitySummary());
    }
}
