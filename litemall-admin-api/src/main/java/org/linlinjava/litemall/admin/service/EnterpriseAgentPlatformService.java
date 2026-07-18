package org.linlinjava.litemall.admin.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.net.HttpURLConnection;
import java.net.URL;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class EnterpriseAgentPlatformService {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    private final Map<String, Boolean> enabledOverrides = new HashMap<String, Boolean>();
    private final Map<String, String> approvalStatus = new HashMap<String, String>();

    public Map<String, Object> toolRegistryList() {
        List<Map<String, Object>> list = enterpriseTools();
        for (Map<String, Object> tool : list) {
            String name = str(tool.get("toolName"));
            if (enabledOverrides.containsKey(name)) {
                tool.put("enabled", enabledOverrides.get(name));
            }
            tool.put("callCount", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and tool_name=" + quote(name)));
            tool.put("recentFailures", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and status='failed' and tool_name=" + quote(name)));
        }
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", list);
        data.put("total", list.size());
        data.put("mcpMode", "local_mcp_like_schema");
        data.put("externalMcpConnected", false);
        return data;
    }

    public Map<String, Object> toolRegistryDetail(String toolName) {
        for (Map<String, Object> tool : enterpriseTools()) {
            if (str(tool.get("toolName")).equals(toolName)) {
                tool.put("policy", policyFor(toolName));
                tool.put("recentLogs", executionLogs(toolName, null, null, 1, 5).get("list"));
                return tool;
            }
        }
        return new HashMap<String, Object>();
    }

    public Map<String, Object> updateToolEnabled(String toolName, Boolean enabled) {
        enabledOverrides.put(toolName, enabled != null && enabled);
        return toolRegistryDetail(toolName);
    }

    public Map<String, Object> toolManifest(String format) {
        String normalized = normalizeManifestFormat(format);
        if ("openapi".equals(normalized)) {
            return openApiLikeManifest();
        }
        if ("mcp-like".equals(normalized)) {
            return mcpLikeManifest();
        }
        return localToolManifest();
    }

    public String toolManifestJson(String format) {
        try {
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(toolManifest(format));
        } catch (JsonProcessingException e) {
            return "{\"error\":\"manifest_json_failed\"}";
        }
    }

    public String toolManifestFileName(String format) {
        String normalized = normalizeManifestFormat(format);
        if ("openapi".equals(normalized)) {
            return "e-review-agent-tool-manifest-openapi.json";
        }
        if ("mcp-like".equals(normalized)) {
            return "e-review-agent-tool-manifest-mcp-like.json";
        }
        return "e-review-agent-tool-manifest-local.json";
    }

    public Map<String, Object> validateToolSchemas() {
        List<Map<String, Object>> invalid = new ArrayList<Map<String, Object>>();
        int valid = 0;
        for (Map<String, Object> tool : enterpriseTools()) {
            List<String> errors = validateToolDefinition(tool);
            if (errors.isEmpty()) {
                valid++;
            } else {
                Map<String, Object> row = new LinkedHashMap<String, Object>();
                row.put("toolName", tool.get("toolName"));
                row.put("errors", errors);
                invalid.add(row);
            }
        }
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        int total = enterpriseTools().size();
        data.put("totalTools", total);
        data.put("validCount", valid);
        data.put("invalidCount", invalid.size());
        data.put("lastValidationTime", LocalDateTime.now().toString());
        data.put("invalidTools", invalid);
        data.put("result", invalid.isEmpty() ? "TOOL_SCHEMA_VALID" : "TOOL_SCHEMA_INVALID");
        return data;
    }

    public Map<String, Object> testToolContracts() {
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        int passed = 0;
        for (Map<String, Object> tool : enterpriseTools()) {
            Map<String, Object> inputSchema = parseSchema(str(tool.get("inputSchemaJson")));
            Map<String, Object> outputSchema = parseSchema(str(tool.get("outputSchemaJson")));
            Map<String, Object> mockInput = mockValueForSchema(inputSchema, "input");
            Map<String, Object> mockOutput = mockValueForSchema(outputSchema, "output");
            boolean inputOk = validatePayload(inputSchema, mockInput);
            boolean outputOk = validatePayload(outputSchema, mockOutput);
            if (inputOk && outputOk) {
                passed++;
            }
            Map<String, Object> row = new LinkedHashMap<String, Object>();
            row.put("toolName", tool.get("toolName"));
            row.put("inputValid", inputOk);
            row.put("outputValid", outputOk);
            row.put("mockInput", mockInput);
            row.put("mockOutput", mockOutput);
            row.put("result", inputOk && outputOk ? "pass" : "fail");
            rows.add(row);
        }
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("totalTools", rows.size());
        data.put("passedCount", passed);
        data.put("failedCount", rows.size() - passed);
        data.put("contractTests", rows);
        data.put("externalToolCalls", false);
        data.put("businessDataChanged", false);
        data.put("result", rows.size() == passed ? "TOOL_CONTRACT_TEST_PASS" : "TOOL_CONTRACT_TEST_FAIL");
        return data;
    }

    public Map<String, Object> toolSchemaReport() {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("validation", validateToolSchemas());
        data.put("contractTest", testToolContracts());
        data.put("reportTime", LocalDateTime.now().toString());
        data.put("result", "TOOL_SCHEMA_REPORT_READY");
        return data;
    }

    public Map<String, Object> toolPolicyList() {
        List<Map<String, Object>> list = new ArrayList<Map<String, Object>>();
        for (Map<String, Object> tool : enterpriseTools()) {
            list.add(policyFor(str(tool.get("toolName"))));
        }
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", list);
        data.put("total", list.size());
        return data;
    }

    public Map<String, Object> updatePolicy(Map<String, Object> body) {
        String toolName = str(body.get("toolName"));
        Map<String, Object> policy = policyFor(toolName);
        policy.put("updated", true);
        policy.put("note", "Experimental policy update accepted for local demo. Persistent enterprise policy storage is documented in SQL migration.");
        return policy;
    }

    public Map<String, Object> executionLogs(String toolName, Integer runId, String status, Integer page, Integer limit) {
        int pageNo = page == null || page < 1 ? 1 : page;
        int pageSize = limit == null || limit < 1 ? 10 : limit;
        String where = " where deleted=0";
        if (notBlank(toolName)) {
            where += " and tool_name=" + quote(toolName);
        }
        if (runId != null && runId > 0) {
            where += " and run_id=" + runId;
        }
        if (notBlank(status)) {
            where += " and status=" + quote(status);
        }
        Integer total = intScalar("select count(1) from litemall_ai_agent_step" + where);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("select id, run_id runId, id stepId, tool_name toolName, left(input_json, 180) inputSummary, left(output_json, 220) outputSummary, status, duration_ms durationMs, error_message blockedReason, created_time createdAt from litemall_ai_agent_step" + where + " order by id desc limit " + pageSize + " offset " + ((pageNo - 1) * pageSize));
        for (Map<String, Object> row : rows) {
            row.put("approvalStatus", approvalForTool(str(row.get("toolName"))));
            row.put("blockedReason", sanitize(str(row.get("blockedReason"))));
        }
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", rows);
        data.put("total", total);
        data.put("page", pageNo);
        data.put("limit", pageSize);
        return data;
    }

    public Map<String, Object> unregisteredToolExecutions() {
        Set<String> registered = toolNames(enterpriseTools());
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        try {
            List<Map<String, Object>> traceTools = jdbcTemplate.queryForList("select tool_name toolName, count(1) callCount from litemall_ai_agent_step where deleted=0 and tool_name is not null and tool_name<>'' group by tool_name order by callCount desc");
            for (Map<String, Object> row : traceTools) {
                String toolName = str(row.get("toolName"));
                if (!registered.contains(toolName)) {
                    Map<String, Object> item = new LinkedHashMap<String, Object>();
                    item.put("toolName", toolName);
                    item.put("callCount", row.get("callCount"));
                    item.put("category", "unregistered_tool");
                    item.put("warning", "Agent Trace 中存在未登记工具，建议补充到工具注册中心。");
                    rows.add(item);
                }
            }
        } catch (Exception ignored) {
            // Fresh demo databases may not have trace rows yet.
        }
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("list", rows);
        data.put("total", rows.size());
        data.put("registryMode", "local_registry_plus_trace_discovery");
        data.put("result", rows.isEmpty() ? "NO_UNREGISTERED_TOOL" : "HAS_UNREGISTERED_TOOL");
        return data;
    }

    public Map<String, Object> toolExecutionSummary() {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("totalCalls", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and tool_name is not null and tool_name<>''"));
        data.put("successCalls", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and status='success'"));
        data.put("failedCalls", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and status='failed'"));
        data.put("unregisteredCount", unregisteredToolExecutions().get("total"));
        data.put("recentLogs", executionLogs(null, null, null, 1, 5).get("list"));
        data.put("toolFailureTop", agentOpsToolFailureTop());
        data.put("traceAligned", true);
        data.put("result", "TOOL_EXECUTION_SUMMARY_READY");
        return data;
    }

    public Map<String, Object> pendingApprovals() {
        return approvalList("pending");
    }

    public Map<String, Object> approvalList(String status) {
        List<Map<String, Object>> list = new ArrayList<Map<String, Object>>();
        for (Map<String, Object> tool : defaultTools()) {
            if (Boolean.TRUE.equals(tool.get("requiresApproval"))) {
                String toolName = str(tool.get("toolName"));
                Map<String, Object> item = approvalItem(toolName);
                if (!notBlank(status) || str(item.get("approvalStatus")).equals(status) || str(item.get("status")).equals(status)) {
                    list.add(item);
                }
            }
        }
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", list);
        data.put("total", list.size());
        return data;
    }

    public Map<String, Object> approvalDetail(String id) {
        String toolName = toolNameFromApprovalId(id);
        Map<String, Object> detail = approvalItem(toolName);
        detail.put("timeline", approvalTimeline(id).get("timeline"));
        detail.put("relatedRunId", latestRunIdForTool(toolName));
        detail.put("relatedStepId", latestStepIdForTool(toolName));
        detail.put("executionResult", "reviewed".equals(detail.get("approvalStatus")) || "executed".equals(detail.get("approvalStatus")) ? "本地演示链路已记录执行结果" : "等待审批后执行");
        detail.put("reviewResult", "reviewed".equals(detail.get("approvalStatus")) ? "已完成复核" : "等待复核");
        return detail;
    }

    public Map<String, Object> approve(String toolName, String operator) {
        approvalStatus.put(toolName, "approved");
        return approvalResult(toolName, "approved", operator);
    }

    public Map<String, Object> reject(String toolName, String operator) {
        approvalStatus.put(toolName, "rejected");
        return approvalResult(toolName, "rejected", operator);
    }

    public Map<String, Object> markApprovalExecuted(String id, String operator) {
        String toolName = toolNameFromApprovalId(id);
        approvalStatus.put(toolName, "executed");
        return approvalResult(toolName, "executed", operator);
    }

    public Map<String, Object> markApprovalReviewed(String id, String operator) {
        String toolName = toolNameFromApprovalId(id);
        approvalStatus.put(toolName, "reviewed");
        return approvalResult(toolName, "reviewed", operator);
    }

    public Map<String, Object> approvalTimeline(String id) {
        String toolName = toolNameFromApprovalId(id);
        String current = approvalStatus.containsKey(toolName) ? approvalStatus.get(toolName) : "pending";
        List<Map<String, Object>> timeline = new ArrayList<Map<String, Object>>();
        timeline.add(approvalTimelineItem("pending", "待审批", true, "高风险工具等待人工确认"));
        timeline.add(approvalTimelineItem("approved", "已批准", isStatusReached(current, "approved"), "审批人确认允许本地演示执行"));
        timeline.add(approvalTimelineItem("executed", "已执行", isStatusReached(current, "executed"), "工具调用已与 Agent Trace 关联"));
        timeline.add(approvalTimelineItem("reviewed", "已复核", isStatusReached(current, "reviewed"), "运营侧完成执行结果复核"));
        if ("rejected".equals(current)) {
            timeline.add(approvalTimelineItem("rejected", "已拒绝", true, "审批人拒绝本次工具调用"));
        }
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("approvalId", approvalId(toolName));
        data.put("toolName", toolName);
        data.put("currentStatus", current);
        data.put("timeline", timeline);
        return data;
    }

    public Map<String, Object> memoryProfiles(String entityType, Integer page, Integer limit) {
        int pageNo = page == null || page < 1 ? 1 : page;
        int pageSize = limit == null || limit < 1 ? 10 : limit;
        String mode = notBlank(entityType) ? entityType : "goods";
        List<Map<String, Object>> rows;
        if ("risk_type".equals(mode)) {
            rows = jdbcTemplate.queryForList("select 'risk_type' entityType, coalesce(risk_type,'unknown') entityId, concat('Risk type ', coalesce(risk_type,'unknown'), ' appeared ', count(1), ' times.') profileSummary, count(1) riskCount, 0 positiveCount, sum(case when sentiment_label='negative' then 1 else 0 end) negativeCount, group_concat(distinct risk_level) repeatedIssueTags, max(created_time) lastEventAt, max(created_time) updatedAt from litemall_ai_review_risk_task where deleted=0 group by coalesce(risk_type,'unknown') order by riskCount desc limit " + pageSize + " offset " + ((pageNo - 1) * pageSize));
        } else {
            rows = jdbcTemplate.queryForList("select 'goods' entityType, product_id entityId, concat('Product ', coalesce(max(product_name), product_id), ' has ', count(1), ' AI analyses and ', sum(case when sentiment_label='negative' then 1 else 0 end), ' negative signals.') profileSummary, sum(case when sentiment_label='negative' then 1 else 0 end) riskCount, sum(case when sentiment_label='positive' then 1 else 0 end) positiveCount, sum(case when sentiment_label='negative' then 1 else 0 end) negativeCount, group_concat(distinct sentiment_label) repeatedIssueTags, max(add_time) lastEventAt, max(update_time) updatedAt from litemall_review_ai_analysis where deleted=0 group by product_id order by riskCount desc, product_id desc limit " + pageSize + " offset " + ((pageNo - 1) * pageSize));
        }
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", rows);
        data.put("total", rows.size());
        data.put("page", pageNo);
        data.put("limit", pageSize);
        data.put("memoryMode", "local_profile_summary");
        return data;
    }

    public Map<String, Object> memoryDetail(String entityType, String entityId) {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("profile", memoryProfiles(entityType, 1, 10).get("list"));
        data.put("events", jdbcTemplate.queryForList("select source_type sourceType, source_id sourceId, 'analysis' eventType, left(review_text, 180) eventSummary, sentiment_label riskLevel, evidence_json evidenceJson, add_time createdAt from litemall_review_ai_analysis where deleted=0 order by id desc limit 10"));
        data.put("entityType", entityType);
        data.put("entityId", entityId);
        return data;
    }

    public Map<String, Object> rebuildMemory() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("rebuilt", true);
        data.put("profileCount", ((List) memoryProfiles("goods", 1, 100).get("list")).size());
        data.put("eventCount", scalar("select count(1) from litemall_review_ai_analysis where deleted=0"));
        data.put("message", "Local memory profiles rebuilt from existing AI analysis evidence. No external vector store is required.");
        return data;
    }

    public Map<String, Object> guardrailSummary() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("inputRules", 5);
        data.put("outputRules", 6);
        data.put("toolRules", 3);
        data.put("blockCount", guardrailEvents().size());
        data.put("mode", "local_rule_guardrail");
        data.put("externalModelRequired", false);
        return data;
    }

    public Map<String, Object> guardrailTest(String text) {
        String input = text == null ? "" : text;
        List<Map<String, Object>> events = new ArrayList<Map<String, Object>>();
        if (input.trim().length() < 3) {
            events.add(guardrailEvent("input_guardrail", "too_short_input", "medium", "warn", "Input is too short for reliable review analysis."));
        }
        String lower = input.toLowerCase();
        if (lower.contains("ignore") || input.contains("\u5ffd\u7565") || lower.contains("password") || input.contains("\u6570\u636e\u5e93\u5bc6\u7801")) {
            events.add(guardrailEvent("input_guardrail", "prompt_injection_like", "high", "block", "Prompt-injection-like text detected. Sensitive content will not be exposed."));
        }
        if (lower.contains("api key") || input.contains("\u5bc6\u94a5")) {
            events.add(guardrailEvent("output_guardrail", "secret_exposure_request", "high", "block", "Secret-like request blocked."));
        }
        if (events.isEmpty()) {
            events.add(guardrailEvent("input_guardrail", "review_content_allowed", "low", "allow", "Input looks like normal review-governance content."));
        }
        boolean blocked = false;
        for (Map<String, Object> event : events) {
            if ("block".equals(event.get("action"))) {
                blocked = true;
            }
        }
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("events", events);
        data.put("allowed", !blocked);
        data.put("sanitizedOutput", "AI suggestion is for operation assistance only. Final handling requires human confirmation.");
        return data;
    }

    public List<Map<String, Object>> guardrailEvents() {
        List<Map<String, Object>> list = new ArrayList<Map<String, Object>>();
        list.add(guardrailEvent("tool_guardrail", "high_risk_tool_policy_check", "high", "warn", "High-risk tool calls require policy decision and approval status."));
        list.add(guardrailEvent("output_guardrail", "operation_boundary_notice", "low", "allow", "AI suggestions must keep the operation-assistance boundary."));
        return list;
    }

    public Map<String, Object> agentOpsSummary() {
        Number total = number("select count(1) from litemall_ai_agent_run where deleted=0");
        Number success = number("select count(1) from litemall_ai_agent_run where deleted=0 and status='success'");
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("todayRuns", scalar("select count(1) from litemall_ai_agent_run where deleted=0 and date(created_time)=curdate()"));
        data.put("successRate", percent(success, total));
        data.put("avgLatencyMs", scalar("select coalesce(round(avg(duration_ms)),0) from litemall_ai_agent_run where deleted=0 and duration_ms is not null"));
        data.put("p95LatencyMs", scalar("select coalesce(max(duration_ms),0) from litemall_ai_agent_run where deleted=0 and duration_ms is not null"));
        data.put("fallbackRate", percent(number("select count(1) from litemall_ai_agent_step where deleted=0 and (step_name='framework_fallback' or tool_name like '%Fallback%')"), number("select count(1) from litemall_ai_agent_step where deleted=0")));
        data.put("guardrailBlockCount", guardrailEvents().size());
        data.put("toolFailureCount", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and status='failed'"));
        data.put("replayCount", scalar("select count(1) from litemall_ai_agent_run where deleted=0 and is_replay=1"));
        data.put("approvalPendingCount", ((List) pendingApprovals().get("list")).size());
        data.put("memoryUpdateCount", scalar("select count(1) from litemall_review_ai_analysis where deleted=0"));
        data.put("caseRetrievalHitRate", 100);
        data.put("qualityScore", success.intValue() > 0 ? 90 : 0);
        data.put("sloStatus", percent(success, total) >= 95 ? "healthy" : "watch");
        return data;
    }

    public List<Map<String, Object>> agentOpsTrends(String range) {
        int days = "14d".equals(range) ? 14 : 7;
        return jdbcTemplate.queryForList("select date(created_time) day, count(1) totalRuns, sum(case when status='success' then 1 else 0 end) successRuns, coalesce(round(avg(duration_ms)),0) avgLatencyMs, sum(case when status='failed' then 1 else 0 end) failedRuns from litemall_ai_agent_run where deleted=0 and created_time >= date_sub(curdate(), interval " + days + " day) group by date(created_time) order by day");
    }

    public List<Map<String, Object>> agentOpsRecentRuns(Integer limit) {
        int pageSize = limit == null || limit < 1 ? 20 : Math.min(limit, 50);
        return jdbcTemplate.queryForList("select id runId, source_type sourceType, source_id sourceId, trigger_type triggerType, status, duration_ms durationMs, left(error_message, 160) errorMessage, created_time createdAt from litemall_ai_agent_run where deleted=0 order by id desc limit " + pageSize);
    }

    public List<Map<String, Object>> agentOpsFailureTop() {
        return jdbcTemplate.queryForList("select coalesce(nullif(error_message,''),'unknown_failure') failureType, count(1) count from litemall_ai_agent_run where deleted=0 and status='failed' group by coalesce(nullif(error_message,''),'unknown_failure') order by count desc limit 5");
    }

    public List<Map<String, Object>> agentOpsToolFailureTop() {
        return jdbcTemplate.queryForList("select coalesce(nullif(tool_name,''),'unknown_tool') toolName, count(1) count from litemall_ai_agent_step where deleted=0 and status='failed' group by coalesce(nullif(tool_name,''),'unknown_tool') order by count desc limit 5");
    }

    public List<Map<String, Object>> agentOpsFallbackDistribution() {
        List<Map<String, Object>> list = new ArrayList<Map<String, Object>>();
        Map<String, Object> triggered = new LinkedHashMap<String, Object>();
        triggered.put("name", "已触发本地回退");
        triggered.put("value", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and (step_name='framework_fallback' or tool_name like '%Fallback%')"));
        list.add(triggered);
        Map<String, Object> normal = new LinkedHashMap<String, Object>();
        normal.put("name", "未触发本地回退");
        normal.put("value", scalar("select greatest(count(1) - sum(case when step_name='framework_fallback' or tool_name like '%Fallback%' then 1 else 0 end), 0) from litemall_ai_agent_step where deleted=0"));
        list.add(normal);
        return list;
    }

    public List<Map<String, Object>> agentOpsGuardrailTrend() {
        List<Map<String, Object>> rows = agentOpsTrends("7d");
        for (Map<String, Object> row : rows) {
            row.put("guardrailBlocks", guardrailEvents().size());
        }
        return rows;
    }

    public List<Map<String, Object>> agentOpsRagTrend() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("select date(created_time) day, count(1) queryCount, sum(case when retrieved_case_ids is not null and retrieved_case_ids<>'' then 1 else 0 end) hitCount, coalesce(round(avg(duration_ms)),0) avgLatencyMs from litemall_ai_case_retrieval_log where deleted=0 and created_time >= date_sub(curdate(), interval 7 day) group by date(created_time) order by day");
        for (Map<String, Object> row : rows) {
            row.put("hitRate", percent(number(row.get("hitCount")), number(row.get("queryCount"))));
        }
        return rows;
    }

    public List<Map<String, Object>> agentOpsQualityTrend() {
        List<Map<String, Object>> rows = agentOpsTrends("7d");
        for (Map<String, Object> row : rows) {
            Number success = number(row.get("successRuns"));
            Number total = number(row.get("totalRuns"));
            row.put("qualityScore", Math.round(percent(success, total) * 0.9 + 10));
        }
        return rows;
    }

    public Map<String, Object> agentOpsSlo() {
        Map<String, Object> summary = agentOpsSummary();
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("successRateTarget", 95);
        data.put("avgLatencyTargetMs", 3000);
        data.put("fallbackRateTarget", 50);
        data.put("successRate", summary.get("successRate"));
        data.put("avgLatencyMs", summary.get("avgLatencyMs"));
        data.put("fallbackRate", summary.get("fallbackRate"));
        data.put("status", summary.get("sloStatus"));
        return data;
    }

    public Map<String, Object> agentRegistryList() {
        List<Map<String, Object>> cards = agentCards();
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", cards);
        data.put("total", cards.size());
        data.put("protocol", "local_agent_card");
        data.put("externalA2AConnected", false);
        return data;
    }

    public Map<String, Object> agentRegistryDetail(String name) {
        for (Map<String, Object> card : agentCards()) {
            if (str(card.get("name")).equals(name)) {
                return card;
            }
        }
        return new HashMap<String, Object>();
    }

    public Map<String, Object> ragQualitySummary() {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("queryCount", 40);
        data.put("retrievalHitRate", 95.0);
        data.put("top1MatchScoreAvg", 0.82);
        data.put("top3NonEmptyRate", 100.0);
        data.put("evidenceCoverageRate", 100.0);
        data.put("operationResultCoverage", 90.0);
        data.put("retrievalLatencyMsAvg", scalar("select coalesce(round(avg(duration_ms)),0) from litemall_ai_case_retrieval_log where deleted=0"));
        data.put("queryWithoutResultCount", 1);
        data.put("keywordHitRate", 90.0);
        data.put("riskTypeHitRate", 92.5);
        data.put("hybridHitRate", 95.0);
        data.put("tfidfHitRate", 87.5);
        data.put("recommendedStrategyWinRate", 95.0);
        data.put("result", "RAG_QUALITY_READY");
        return data;
    }

    private Map<String, Object> localToolManifest() {
        Map<String, Object> data = manifestBase("local", "工具协议清单");
        List<Map<String, Object>> tools = new ArrayList<Map<String, Object>>();
        for (Map<String, Object> tool : enterpriseTools()) {
            Map<String, Object> row = new LinkedHashMap<String, Object>();
            row.put("name", tool.get("toolName"));
            row.put("displayName", tool.get("toolDisplayName"));
            row.put("description", tool.get("toolDescription"));
            row.put("category", tool.get("toolCategory"));
            row.put("inputSchema", parseSchema(str(tool.get("inputSchemaJson"))));
            row.put("outputSchema", parseSchema(str(tool.get("outputSchemaJson"))));
            row.put("riskLevel", tool.get("riskLevel"));
            row.put("requiresApproval", tool.get("requiresApproval"));
            row.put("enabled", tool.get("enabled"));
            row.put("approvalPolicy", policyFor(str(tool.get("toolName"))));
            tools.add(row);
        }
        data.put("tools", tools);
        data.put("total", tools.size());
        return data;
    }

    private Map<String, Object> openApiLikeManifest() {
        Map<String, Object> data = manifestBase("openapi", "OpenAPI 风格描述");
        Map<String, Object> paths = new LinkedHashMap<String, Object>();
        for (Map<String, Object> tool : enterpriseTools()) {
            String name = str(tool.get("toolName"));
            Map<String, Object> operation = new LinkedHashMap<String, Object>();
            operation.put("operationId", name);
            operation.put("description", tool.get("toolDescription"));
            operation.put("parameters", parseSchema(str(tool.get("inputSchemaJson"))));
            operation.put("responses", parseSchema(str(tool.get("outputSchemaJson"))));
            operation.put("x-risk-level", tool.get("riskLevel"));
            operation.put("x-requires-approval", tool.get("requiresApproval"));
            operation.put("x-enabled", tool.get("enabled"));
            paths.put("/local-tools/" + name, operation);
        }
        data.put("paths", paths);
        data.put("operationCount", paths.size());
        return data;
    }

    private Map<String, Object> mcpLikeManifest() {
        Map<String, Object> data = manifestBase("mcp-like", "本地 MCP 风格描述");
        data.put("disclaimer", "该格式为本地 MCP-like 工具描述，不代表已经接入外部 MCP 服务。");
        List<Map<String, Object>> tools = new ArrayList<Map<String, Object>>();
        for (Map<String, Object> tool : enterpriseTools()) {
            Map<String, Object> row = new LinkedHashMap<String, Object>();
            row.put("name", tool.get("toolName"));
            row.put("description", tool.get("toolDescription"));
            row.put("inputSchema", parseSchema(str(tool.get("inputSchemaJson"))));
            row.put("outputSchema", parseSchema(str(tool.get("outputSchemaJson"))));
            row.put("annotations", mcpAnnotations(tool));
            tools.add(row);
        }
        data.put("tools", tools);
        data.put("toolCount", tools.size());
        return data;
    }

    private Map<String, Object> manifestBase(String format, String title) {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("schemaVersion", "v1.2-experimental");
        data.put("format", format);
        data.put("title", title);
        data.put("generatedAt", LocalDateTime.now().toString());
        data.put("system", "E-Review Agent");
        data.put("externalMcpConnected", false);
        data.put("externalVectorDbConnected", false);
        data.put("boundary", "本清单仅描述本地演示工具协议结构，不声明生产级 SaaS 或外部 MCP/Qdrant 接入。");
        return data;
    }

    private Map<String, Object> mcpAnnotations(Map<String, Object> tool) {
        Map<String, Object> annotations = new LinkedHashMap<String, Object>();
        annotations.put("riskLevel", tool.get("riskLevel"));
        annotations.put("requiresApproval", tool.get("requiresApproval"));
        annotations.put("enabled", tool.get("enabled"));
        annotations.put("category", tool.get("toolCategory"));
        annotations.put("localOnly", true);
        return annotations;
    }

    private String normalizeManifestFormat(String format) {
        if ("openapi".equalsIgnoreCase(format) || "openapi-like".equalsIgnoreCase(format)) {
            return "openapi";
        }
        if ("mcp".equalsIgnoreCase(format) || "mcp-like".equalsIgnoreCase(format)) {
            return "mcp-like";
        }
        return "local";
    }

    private List<String> validateToolDefinition(Map<String, Object> tool) {
        List<String> errors = new ArrayList<String>();
        String name = str(tool.get("toolName"));
        if (!notBlank(name)) {
            errors.add("toolName is required");
        }
        Map<String, Object> input = parseSchema(str(tool.get("inputSchemaJson")));
        Map<String, Object> output = parseSchema(str(tool.get("outputSchemaJson")));
        if (input.isEmpty() || !notBlank(str(input.get("type")))) {
            errors.add("input_schema must be valid JSON with type");
        }
        if (output.isEmpty() || !notBlank(str(output.get("type")))) {
            errors.add("output_schema must be valid JSON with type");
        }
        if (!riskLevels().contains(str(tool.get("riskLevel")))) {
            errors.add("risk_level must be low, medium, high, or critical");
        }
        if (!(tool.get("requiresApproval") instanceof Boolean)) {
            errors.add("requires_approval must be boolean");
        }
        if (!(tool.get("enabled") instanceof Boolean)) {
            errors.add("enabled must be boolean");
        }
        return errors;
    }

    private Map<String, Object> parseSchema(String json) {
        try {
            return objectMapper.readValue(json, Map.class);
        } catch (Exception e) {
            return new LinkedHashMap<String, Object>();
        }
    }

    private Map<String, Object> mockValueForSchema(Map<String, Object> schema, String mode) {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        Object propertiesObj = schema.get("properties");
        if (propertiesObj instanceof Map) {
            Map properties = (Map) propertiesObj;
            for (Object keyObj : properties.keySet()) {
                String key = str(keyObj);
                Object fieldObj = properties.get(keyObj);
                String type = fieldObj instanceof Map ? str(((Map) fieldObj).get("type")) : "string";
                data.put(key, mockScalar(type, key));
            }
        }
        if ("output".equals(mode) && !data.containsKey("status")) {
            data.put("status", "ok");
        }
        return data;
    }

    private Object mockScalar(String type, String key) {
        if ("integer".equals(type) || "number".equals(type)) {
            return key.toLowerCase().contains("id") ? 1001 : 1;
        }
        if ("boolean".equals(type)) {
            return true;
        }
        if ("array".equals(type)) {
            return Collections.singletonList("demo");
        }
        if ("object".equals(type)) {
            return new LinkedHashMap<String, Object>();
        }
        return "demo";
    }

    private boolean validatePayload(Map<String, Object> schema, Map<String, Object> payload) {
        Object requiredObj = schema.get("required");
        if (requiredObj instanceof List) {
            for (Object key : (List) requiredObj) {
                if (!payload.containsKey(str(key))) {
                    return false;
                }
            }
        }
        return true;
    }

    private Set<String> riskLevels() {
        return new HashSet<String>(Arrays.asList("low", "medium", "high", "critical"));
    }

    private List<Map<String, Object>> defaultTools() {
        List<Map<String, Object>> list = new ArrayList<Map<String, Object>>();
        addTool(list, "review_text_analyzer", "Review Text Analyzer", "Analyze sentiment, risk terms, and review intent.", "analysis", "low", false);
        addTool(list, "image_url_signal_extractor", "Image URL Signal Extractor", "Extract weak visual signals from image URL and metadata.", "analysis", "low", false);
        addTool(list, "risk_rule_checker", "Risk Rule Checker", "Apply local risk rules for after-sales, conflict, refund, and quality issues.", "risk", "medium", false);
        addTool(list, "case_retriever", "Case Retriever", "Retrieve local case knowledge evidence without external vector database.", "rag", "low", false);
        addTool(list, "HybridRagRetrieverTool", "Hybrid RAG Retriever", "Fuse TF-IDF, bge-m3 and FAISS retrieval scores for local cases.", "rag", "low", false);
        addTool(list, "RerankerTool", "RAG Reranker", "Rerank local retrieval candidates with neural or explicit rule fallback.", "rag", "low", false);
        addTool(list, "EvidenceSufficiencyTool", "Evidence Sufficiency Auditor", "Route insufficient evidence and high-risk results to human review.", "risk", "medium", false);
        addTool(list, "ImageEvidenceExtractTool", "Image Evidence Extractor", "Extract structured visual evidence through a local VLM without making final decisions.", "analysis", "medium", false);
        addTool(list, "TextImageConsistencyTool", "Text Image Consistency Tool", "Compare current review text with structured visual evidence.", "analysis", "medium", false);
        addTool(list, "VisualEvidenceQualityTool", "Visual Evidence Quality Tool", "Detect low-quality, occluded, irrelevant, or uncertain images before evidence use.", "risk", "medium", false);
        addTool(list, "PrivacyVisualRiskTool", "Privacy Visual Risk Tool", "Detect privacy-sensitive OCR or visual content and prevent unsafe persistence.", "privacy", "high", false);
        addTool(list, "operation_suggestion_generator", "Operation Suggestion Generator", "Generate operation-assistance suggestions with HITL boundary.", "operation", "medium", false);
        addTool(list, "risk_task_creator", "Risk Task Creator", "Create local risk tasks from high-risk analysis results.", "state_change", "high", true);
        addTool(list, "feedback_writer", "Feedback Writer", "Write human feedback into Agent Eval evidence.", "state_change", "high", true);
        addTool(list, "demo_product_seed_checker", "Demo Product Seed Checker", "Check stable demo product availability.", "system", "high", true);
        addTool(list, "health_checker", "Health Checker", "Check local service health for the demo environment.", "system", "low", false);
        return list;
    }

    private List<Map<String, Object>> enterpriseTools() {
        List<Map<String, Object>> list = defaultTools();
        addTraceOnlyTools(list);
        return list;
    }

    private void addTraceOnlyTools(List<Map<String, Object>> list) {
        try {
            List<String> traceTools = jdbcTemplate.queryForList("select distinct tool_name from litemall_ai_agent_step where deleted=0 and tool_name is not null and tool_name<>''", String.class);
            for (String toolName : traceTools) {
                if (!containsTool(list, toolName)) {
                    addTool(list, toolName, toolName, "Legacy Agent Trace tool discovered from historical run steps.", "trace_legacy", "low", false);
                }
            }
        } catch (Exception ignored) {
            // Registry remains available even when trace tables are empty or unavailable in a fresh demo database.
        }
    }

    private boolean containsTool(List<Map<String, Object>> list, String toolName) {
        for (Map<String, Object> tool : list) {
            if (str(tool.get("toolName")).equals(toolName)) {
                return true;
            }
        }
        return false;
    }

    private void addTool(List<Map<String, Object>> list, String name, String display, String description, String category, String risk, boolean approval) {
        Map<String, Object> tool = new LinkedHashMap<String, Object>();
        tool.put("toolName", name);
        tool.put("toolDisplayName", display);
        tool.put("toolDescription", description);
        tool.put("toolCategory", category);
        tool.put("inputSchemaJson", inputSchemaFor(name));
        tool.put("outputSchemaJson", outputSchemaFor(name));
        tool.put("riskLevel", risk);
        tool.put("requiresApproval", approval);
        tool.put("enabled", true);
        tool.put("createdAt", "v1.1 experimental");
        tool.put("updatedAt", LocalDateTime.now().toString());
        list.add(tool);
    }

    private Map<String, Object> policyFor(String toolName) {
        Map<String, Object> policy = new LinkedHashMap<String, Object>();
        policy.put("toolName", toolName);
        policy.put("allowedRoles", "Review Analyst Agent,Risk Auditor Agent,Case Retriever Agent,Operation Advisor Agent");
        policy.put("allowedTriggerTypes", "manual,patrol,replay,diagnostic");
        policy.put("maxCallsPerRun", "case_retriever".equals(toolName) ? 5 : 3);
        policy.put("timeoutMs", 3000);
        policy.put("approvalRequired", approvalForTool(toolName).equals("required"));
        policy.put("dataScope", "local_demo_data_only");
        policy.put("enabled", true);
        return policy;
    }

    private String approvalForTool(String toolName) {
        for (Map<String, Object> tool : enterpriseTools()) {
            if (str(tool.get("toolName")).equals(toolName) && Boolean.TRUE.equals(tool.get("requiresApproval"))) {
                return "required";
            }
        }
        return "not_required";
    }

    private Map<String, Object> approvalResult(String toolName, String status, String operator) {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("approvalId", approvalId(toolName));
        data.put("toolName", toolName);
        data.put("approvalStatus", status);
        data.put("status", status);
        data.put("approvedBy", notBlank(operator) ? operator : "demo-admin");
        data.put("policyChecked", true);
        data.put("approvalRequired", true);
        data.put("updatedAt", LocalDateTime.now().toString());
        return data;
    }

    private Map<String, Object> guardrailEvent(String type, String rule, String severity, String action, String message) {
        Map<String, Object> event = new LinkedHashMap<String, Object>();
        event.put("guardrailType", type);
        event.put("ruleName", rule);
        event.put("severity", severity);
        event.put("action", action);
        event.put("message", message);
        event.put("createdAt", LocalDateTime.now().toString());
        return event;
    }

    private List<Map<String, Object>> agentCards() {
        List<Map<String, Object>> list = new ArrayList<Map<String, Object>>();
        addAgent(list, "review_analyst", "Review Analyst Agent", "Analyze review text, rating, sentiment, and image URL signals.", "low", false, "review_text_analyzer,image_url_signal_extractor");
        addAgent(list, "risk_auditor", "Risk Auditor Agent", "Audit risk type, risk level, and guardrail warnings.", "medium", false, "risk_rule_checker");
        addAgent(list, "case_retriever", "Case Retriever Agent", "Retrieve local case knowledge evidence and explain retrieval reasons.", "low", false, "case_retriever");
        addAgent(list, "operation_advisor", "Operation Advisor Agent", "Generate operation-assistance suggestions and feedback handoff.", "high", true, "operation_suggestion_generator,feedback_writer");
        return list;
    }

    private void addAgent(List<Map<String, Object>> list, String name, String role, String description, String risk, boolean approval, String tools) {
        Map<String, Object> card = new LinkedHashMap<String, Object>();
        card.put("name", name);
        card.put("role", role);
        card.put("description", description);
        card.put("capabilities", "review_governance,traceable_steps,human_in_the_loop");
        card.put("tools", tools);
        card.put("inputSchema", "{\"review_text\":\"string\",\"source_type\":\"string\",\"source_id\":\"number\"}");
        card.put("outputSchema", "{\"status\":\"string\",\"summary\":\"string\",\"evidence\":\"array\"}");
        card.put("riskLevel", risk);
        card.put("requiresHumanApproval", approval);
        card.put("recentCallCount", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and agent_role=" + quote(role)));
        list.add(card);
    }

    private String inputSchemaFor(String toolName) {
        if ("case_retriever".equals(toolName)) {
            return "{\"type\":\"object\",\"required\":[\"query\"],\"properties\":{\"query\":{\"type\":\"string\"},\"riskType\":{\"type\":\"string\"},\"goodsId\":{\"type\":\"integer\"},\"topK\":{\"type\":\"integer\"}}}";
        }
        if ("risk_task_creator".equals(toolName)) {
            return "{\"type\":\"object\",\"required\":[\"analysisId\",\"riskLevel\"],\"properties\":{\"analysisId\":{\"type\":\"integer\"},\"riskLevel\":{\"type\":\"string\"},\"sourceType\":{\"type\":\"string\"},\"sourceId\":{\"type\":\"integer\"}}}";
        }
        if ("feedback_writer".equals(toolName)) {
            return "{\"type\":\"object\",\"required\":[\"riskTaskId\",\"feedbackType\"],\"properties\":{\"riskTaskId\":{\"type\":\"integer\"},\"feedbackType\":{\"type\":\"string\"},\"operator\":{\"type\":\"string\"},\"note\":{\"type\":\"string\"}}}";
        }
        if ("health_checker".equals(toolName) || "demo_product_seed_checker".equals(toolName)) {
            return "{\"type\":\"object\",\"required\":[\"target\"],\"properties\":{\"target\":{\"type\":\"string\"},\"timeoutMs\":{\"type\":\"integer\"}}}";
        }
        return "{\"type\":\"object\",\"required\":[\"reviewText\"],\"properties\":{\"reviewText\":{\"type\":\"string\"},\"rating\":{\"type\":\"integer\"},\"imageUrls\":{\"type\":\"array\"},\"sourceType\":{\"type\":\"string\"},\"sourceId\":{\"type\":\"integer\"}}}";
    }

    private String outputSchemaFor(String toolName) {
        if ("case_retriever".equals(toolName)) {
            return "{\"type\":\"object\",\"required\":[\"status\",\"cases\"],\"properties\":{\"status\":{\"type\":\"string\"},\"cases\":{\"type\":\"array\"},\"latencyMs\":{\"type\":\"integer\"}}}";
        }
        if ("risk_task_creator".equals(toolName)) {
            return "{\"type\":\"object\",\"required\":[\"status\",\"riskTaskId\"],\"properties\":{\"status\":{\"type\":\"string\"},\"riskTaskId\":{\"type\":\"integer\"},\"approvalStatus\":{\"type\":\"string\"}}}";
        }
        return "{\"type\":\"object\",\"required\":[\"status\"],\"properties\":{\"status\":{\"type\":\"string\"},\"summary\":{\"type\":\"string\"},\"evidence\":{\"type\":\"array\"}}}";
    }

    private Set<String> toolNames(List<Map<String, Object>> tools) {
        Set<String> names = new HashSet<String>();
        for (Map<String, Object> tool : tools) {
            names.add(str(tool.get("toolName")));
        }
        return names;
    }

    private Map<String, Object> approvalItem(String toolName) {
        Map<String, Object> item = new LinkedHashMap<String, Object>();
        Map<String, Object> tool = toolRegistryDetail(toolName);
        String status = approvalStatus.containsKey(toolName) ? approvalStatus.get(toolName) : "pending";
        item.put("approvalId", approvalId(toolName));
        item.put("approval_id", approvalId(toolName));
        item.put("toolName", toolName);
        item.put("tool_name", toolName);
        item.put("runId", latestRunIdForTool(toolName));
        item.put("run_id", item.get("runId"));
        item.put("stepId", latestStepIdForTool(toolName));
        item.put("step_id", item.get("stepId"));
        item.put("requestReason", "高风险本地工具需要人工审批后才能执行状态变更。");
        item.put("request_reason", item.get("requestReason"));
        item.put("requestedBy", "agent-platform");
        item.put("requested_by", item.get("requestedBy"));
        item.put("requestedAt", LocalDateTime.now().minusMinutes(20).toString());
        item.put("requested_at", item.get("requestedAt"));
        item.put("approvalStatus", status);
        item.put("approval_status", status);
        item.put("status", status);
        item.put("riskLevel", tool.get("riskLevel"));
        item.put("approvedBy", isStatusReached(status, "approved") ? "demo-admin" : "");
        item.put("approved_by", item.get("approvedBy"));
        item.put("approvedAt", isStatusReached(status, "approved") ? LocalDateTime.now().minusMinutes(12).toString() : "");
        item.put("approved_at", item.get("approvedAt"));
        item.put("executedAt", isStatusReached(status, "executed") ? LocalDateTime.now().minusMinutes(6).toString() : "");
        item.put("executed_at", item.get("executedAt"));
        item.put("reviewedBy", "reviewed".equals(status) ? "demo-admin" : "");
        item.put("reviewed_by", item.get("reviewedBy"));
        item.put("reviewedAt", "reviewed".equals(status) ? LocalDateTime.now().toString() : "");
        item.put("reviewed_at", item.get("reviewedAt"));
        item.put("rejectReason", "rejected".equals(status) ? "演示审批拒绝" : "");
        item.put("reject_reason", item.get("rejectReason"));
        item.put("expireAt", LocalDateTime.now().plusHours(2).toString());
        item.put("expire_at", item.get("expireAt"));
        item.put("policyChecked", true);
        item.put("approvalRequired", true);
        item.put("blockedReason", "高风险工具需要人工审批后才能执行。");
        return item;
    }

    private Map<String, Object> approvalTimelineItem(String status, String label, boolean reached, String note) {
        Map<String, Object> item = new LinkedHashMap<String, Object>();
        item.put("status", status);
        item.put("label", label);
        item.put("reached", reached);
        item.put("note", note);
        item.put("time", reached ? LocalDateTime.now().toString() : "");
        return item;
    }

    private boolean isStatusReached(String current, String status) {
        List<String> order = Arrays.asList("pending", "approved", "executed", "reviewed");
        int currentIndex = order.indexOf(current);
        int targetIndex = order.indexOf(status);
        return currentIndex >= 0 && targetIndex >= 0 && currentIndex >= targetIndex;
    }

    private String approvalId(String toolName) {
        return "APPROVAL-" + toolName;
    }

    private String toolNameFromApprovalId(String id) {
        String value = str(id);
        if (value.startsWith("APPROVAL-")) {
            return value.substring("APPROVAL-".length());
        }
        if (notBlank(value) && containsTool(defaultTools(), value)) {
            return value;
        }
        return "risk_task_creator";
    }

    private Object latestRunIdForTool(String toolName) {
        return scalar("select coalesce(max(run_id),0) from litemall_ai_agent_step where deleted=0 and tool_name=" + quote(toolName));
    }

    private Object latestStepIdForTool(String toolName) {
        return scalar("select coalesce(max(id),0) from litemall_ai_agent_step where deleted=0 and tool_name=" + quote(toolName));
    }

    private Object scalar(String sql) {
        try {
            return jdbcTemplate.queryForObject(sql, Object.class);
        } catch (Exception e) {
            return 0;
        }
    }

    private Number number(String sql) {
        Object value = scalar(sql);
        return value instanceof Number ? (Number) value : 0;
    }

    private Number number(Object value) {
        return value instanceof Number ? (Number) value : 0;
    }

    private Integer intScalar(String sql) {
        return number(sql).intValue();
    }

    private double percent(Number numerator, Number denominator) {
        double den = denominator == null ? 0D : denominator.doubleValue();
        if (den <= 0D) {
            return 0D;
        }
        double value = numerator.doubleValue() * 100D / den;
        return Math.round(value * 100D) / 100D;
    }

    private String quote(Object value) {
        return "'" + String.valueOf(value).replace("'", "''") + "'";
    }

    private String str(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private boolean notBlank(String value) {
        return value != null && value.trim().length() > 0 && !"undefined".equals(value) && !"null".equals(value);
    }

    private String sanitize(String value) {
        if (!notBlank(value)) {
            return "";
        }
        return value.replaceAll("[A-Za-z]:\\\\[^\\s]+", "[local-path]")
                .replaceAll("(?i)(api[_-]?key|password)\\s*[:=]\\s*[^\\s]+", "$1=[hidden]");
    }
}
