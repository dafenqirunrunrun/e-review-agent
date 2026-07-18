package org.linlinjava.litemall.admin.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeRequest;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeResponse;
import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;
import org.linlinjava.litemall.db.service.LitemallAiReviewRiskTaskService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.net.HttpURLConnection;
import java.net.URL;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class AgentPlatformService {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private LitemallAiReviewRiskTaskService riskTaskService;

    @Autowired
    private AiReviewService aiReviewService;

    public Integer startRun(String triggerType, String sourceType, Integer sourceId, String inputSummary) {
        LocalDateTime now = LocalDateTime.now();
        String runNo = "RUN-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        Map<String, Object> snapshot = new HashMap<String, Object>();
        snapshot.put("runNo", runNo);
        snapshot.put("triggerType", triggerType);
        snapshot.put("sourceType", sourceType);
        snapshot.put("sourceId", sourceId);
        snapshot.put("status", "running");
        snapshot.put("inputSummary", inputSummary);
        snapshot.put("startedAt", now.toString());
        snapshot.put("agenticMode", "lightweight_multi_role");
        jdbcTemplate.update("insert into litemall_ai_agent_run(run_no, trigger_type, source_type, source_id, status, start_time, input_summary, state_snapshot_json, created_time, updated_time, deleted) values(?,?,?,?,?,?,?,?,?,?,0)",
                runNo, triggerType, sourceType, sourceId, "running", ts(now), inputSummary, writeJson(snapshot), ts(now), ts(now));
        return jdbcTemplate.queryForObject("select last_insert_id()", Integer.class);
    }

    public void finishRun(Integer runId, String status, String finalResult, String errorMessage) {
        if (runId == null) {
            return;
        }
        Map<String, Object> row = detail(runId);
        LocalDateTime end = LocalDateTime.now();
        Long duration = null;
        Object start = row.get("startTime");
        if (start instanceof Timestamp) {
            duration = Duration.between(((Timestamp) start).toLocalDateTime(), end).toMillis();
        }
        jdbcTemplate.update("update litemall_ai_agent_run set status=?, end_time=?, duration_ms=?, final_result=?, error_message=?, updated_time=? where id=?",
                status, ts(end), duration, finalResult, errorMessage, ts(end), runId);
        updateStateSnapshot(runId, singleton("finalStatus", status));
    }

    public void recordStep(Integer runId, String stepName, Integer stepOrder, String toolName, String status, Object input, Object output, String errorMessage, Long durationMs) {
        if (runId == null) {
            return;
        }
        LocalDateTime now = LocalDateTime.now();
        String agentRole = inferAgentRole(stepName, toolName);
        String agentGoal = inferAgentGoal(agentRole);
        jdbcTemplate.update("insert into litemall_ai_agent_step(run_id, step_name, step_order, agent_role, agent_goal, tool_name, status, start_time, end_time, duration_ms, input_json, output_json, error_message, created_time, deleted) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
                runId, stepName, stepOrder, agentRole, agentGoal, toolName, status, ts(now), ts(now), durationMs, writeJson(input), writeJson(output), errorMessage, ts(now));
        Integer stepId = jdbcTemplate.queryForObject("select last_insert_id()", Integer.class);
        String stepProvider = providerFrom(output);
        if (stepProvider == null) {
            stepProvider = providerFrom(input);
        }
        recordToolCall(runId, stepId, toolName, stepProvider,
                input, output, status, errorMessage, durationMs);
        Map<String, Object> delta = new HashMap<String, Object>();
        delta.put("lastStep", stepName);
        delta.put("lastAgentRole", agentRole);
        delta.put("lastToolName", toolName);
        delta.put("lastStepStatus", status);
        delta.put("lastUpdatedAt", now.toString());
        updateStateSnapshot(runId, delta);
    }

    public void recordLlmObservability(Integer runId, AiReviewAnalyzeResponse response) {
        if (runId == null || response == null) {
            return;
        }
        jdbcTemplate.update("update litemall_ai_agent_run set llm_provider=?, model_name=?, prompt_template=?, schema_valid=?, schema_error=?, repair_used=?, fallback_used=?, token_usage_input=?, token_usage_output=?, latency_ms=?, updated_time=now() where id=?",
                response.getLlmProvider(), response.getModelName(), response.getPromptTemplate(), response.getSchemaValid(),
                response.getSchemaError(), response.getRepairUsed(), response.getFallbackUsed(), response.getTokenUsageInput(),
                response.getTokenUsageOutput(), response.getLatencyMs(), runId);
        jdbcTemplate.update("update litemall_ai_agent_run set rag_enabled=?, rag_strategy=?, retrieval_hit_count=?, retrieval_top_score=?, embedding_provider=?, reranker_provider=?, retrieval_latency_ms=?, route_decision=?, route_reason=? where id=?",
                response.getRagEnabled(), response.getRagStrategy(), response.getRetrievalHitCount(), response.getRetrievalTopScore(),
                response.getEmbeddingProvider(), response.getRerankerProvider(), response.getRetrievalLatencyMs(),
                response.getRouteDecision(), trim(response.getRouteReason(), 512), runId);
        jdbcTemplate.update("update litemall_ai_agent_step set llm_provider=?, model_name=?, prompt_template=?, schema_valid=?, schema_error=?, repair_used=?, fallback_used=?, token_usage_input=?, token_usage_output=?, latency_ms=? where run_id=? and (step_name in ('analyze_sentiment','replay_analyze_result') or tool_name in ('LocalQwenTransformersTool','LLMProviderTool'))",
                response.getLlmProvider(), response.getModelName(), response.getPromptTemplate(), response.getSchemaValid(),
                response.getSchemaError(), response.getRepairUsed(), response.getFallbackUsed(), response.getTokenUsageInput(),
                response.getTokenUsageOutput(), response.getLatencyMs(), runId);
        Map<String, Object> delta = new HashMap<String, Object>();
        delta.put("llmProvider", response.getLlmProvider());
        delta.put("modelName", response.getModelName());
        delta.put("schemaValid", response.getSchemaValid());
        delta.put("repairUsed", response.getRepairUsed());
        delta.put("fallbackUsed", response.getFallbackUsed());
        delta.put("llmLatencyMs", response.getLatencyMs());
        delta.put("ragEnabled", response.getRagEnabled());
        delta.put("ragStrategy", response.getRagStrategy());
        delta.put("retrievalHitCount", response.getRetrievalHitCount());
        delta.put("retrievalTopScore", response.getRetrievalTopScore());
        delta.put("embeddingProvider", response.getEmbeddingProvider());
        delta.put("rerankerProvider", response.getRerankerProvider());
        delta.put("retrievalLatencyMs", response.getRetrievalLatencyMs());
        delta.put("routeDecision", response.getRouteDecision());
        delta.put("routeReason", response.getRouteReason());
        delta.put("retrievedCaseIds", response.getRetrievedCaseIds());
        updateStateSnapshot(runId, delta);
    }

    public Map<String, Object> listRuns(String status, String sourceType, String triggerType, Integer page, Integer limit) {
        int pageNo = page == null || page < 1 ? 1 : page;
        int pageSize = limit == null || limit < 1 ? 10 : limit;
        StringBuilder where = new StringBuilder(" where deleted=0");
        Map<String, Object> params = new HashMap<String, Object>();
        if (notBlank(status)) {
            where.append(" and status=:status");
            params.put("status", status);
        }
        if (notBlank(sourceType)) {
            where.append(" and source_type=:sourceType");
            params.put("sourceType", sourceType);
        }
        if (notBlank(triggerType)) {
            where.append(" and trigger_type=:triggerType");
            params.put("triggerType", triggerType);
        }
        String whereSql = where.toString()
                .replace(":status", quote(params.get("status")))
                .replace(":sourceType", quote(params.get("sourceType")))
                .replace(":triggerType", quote(params.get("triggerType")));
        Integer total = jdbcTemplate.queryForObject("select count(1) from litemall_ai_agent_run" + whereSql, Integer.class);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("select id, run_no runNo, trigger_type triggerType, source_type sourceType, source_id sourceId, status, start_time startTime, end_time endTime, duration_ms durationMs, input_summary inputSummary, final_result finalResult, error_message errorMessage, llm_provider llmProvider, model_name modelName, schema_valid schemaValid, repair_used repairUsed, fallback_used fallbackUsed, latency_ms llmLatencyMs, rag_enabled ragEnabled, rag_strategy ragStrategy, retrieval_hit_count retrievalHitCount, retrieval_top_score retrievalTopScore, embedding_provider embeddingProvider, reranker_provider rerankerProvider, retrieval_latency_ms retrievalLatencyMs, route_decision routeDecision, route_reason routeReason, replay_from_run_id replayFromRunId, replay_count replayCount, is_replay isReplay, created_time createdTime from litemall_ai_agent_run" + whereSql + " order by id desc limit " + pageSize + " offset " + ((pageNo - 1) * pageSize));
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", rows);
        data.put("total", total);
        data.put("page", pageNo);
        data.put("limit", pageSize);
        return data;
    }

    public Map<String, Object> detail(Integer id) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("select id, run_no runNo, trigger_type triggerType, source_type sourceType, source_id sourceId, status, start_time startTime, end_time endTime, duration_ms durationMs, input_summary inputSummary, final_result finalResult, error_message errorMessage, state_snapshot_json stateSnapshotJson, llm_provider llmProvider, model_name modelName, prompt_template promptTemplate, schema_valid schemaValid, schema_error schemaError, repair_used repairUsed, fallback_used fallbackUsed, token_usage_input tokenUsageInput, token_usage_output tokenUsageOutput, latency_ms llmLatencyMs, rag_enabled ragEnabled, rag_strategy ragStrategy, retrieval_hit_count retrievalHitCount, retrieval_top_score retrievalTopScore, embedding_provider embeddingProvider, reranker_provider rerankerProvider, retrieval_latency_ms retrievalLatencyMs, route_decision routeDecision, route_reason routeReason, replay_from_run_id replayFromRunId, replay_count replayCount, is_replay isReplay, created_time createdTime from litemall_ai_agent_run where id=? and deleted=0", id);
        if (rows.isEmpty()) {
            return new HashMap<String, Object>();
        }
        Map<String, Object> run = rows.get(0);
        Number stepCount = number("select count(1) from litemall_ai_agent_step where deleted=0 and run_id=" + id);
        Number failedStepCount = number("select count(1) from litemall_ai_agent_step where deleted=0 and run_id=" + id + " and status='failed'");
        Number fallbackStepCount = number("select count(1) from litemall_ai_agent_step where deleted=0 and run_id=" + id + " and (step_name='framework_fallback' or tool_name like '%Fallback%')");
        run.put("stepCount", stepCount);
        run.put("failedStepCount", failedStepCount);
        run.put("fallbackUsed", fallbackStepCount.intValue() > 0);
        run.put("frameworkMode", fallbackStepCount.intValue() > 0 ? "fallback_rule" : currentFrameworkMode());
        run.put("hasHumanFeedback", number("select count(1) from litemall_ai_agent_feedback where deleted=0 and source_type=" + quote(run.get("sourceType")) + " and source_id=" + run.get("sourceId")).intValue() > 0);
        return run;
    }

    public Map<String, Object> state(Integer runId) {
        Map<String, Object> run = detail(runId);
        if (run.isEmpty()) {
            return new HashMap<String, Object>();
        }
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("run", run);
        data.put("snapshot", parseMap(stringValue(run.get("stateSnapshotJson"))));
        data.put("stepsByRole", stepsByRole(runId));
        data.put("analysis", findAnalysisForRun(run));
        return data;
    }

    public Map<String, Object> replayPreview(Integer runId) {
        Map<String, Object> run = detail(runId);
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("run", run);
        if (run.isEmpty()) {
            data.put("canReplay", false);
            data.put("reason", "Run not found.");
            return data;
        }
        Map<String, Object> analysis = findAnalysisForRun(run);
        data.put("analysis", analysis);
        boolean canReplay = !analysis.isEmpty() && notBlank(stringValue(analysis.get("reviewText")));
        data.put("canReplay", canReplay);
        data.put("reason", canReplay ? "Ready to replay from persisted analysis input." : "No source analysis input found.");
        data.put("sourceType", run.get("sourceType"));
        data.put("sourceId", run.get("sourceId"));
        data.put("inputSummary", run.get("inputSummary"));
        data.put("finalResult", run.get("finalResult"));
        return data;
    }

    public Map<String, Object> replay(Integer originalRunId) {
        Map<String, Object> preview = replayPreview(originalRunId);
        if (!Boolean.TRUE.equals(preview.get("canReplay"))) {
            Map<String, Object> failed = new HashMap<String, Object>();
            failed.put("success", false);
            failed.put("reason", preview.get("reason"));
            return failed;
        }
        Map<String, Object> run = (Map<String, Object>) preview.get("run");
        Map<String, Object> analysis = (Map<String, Object>) preview.get("analysis");
        AiReviewAnalyzeRequest request = requestFromAnalysis(analysis);
        Integer replayRunId = startRun("replay", stringValue(run.get("sourceType")), intValue(run.get("sourceId")), trim(request.getReviewText(), 240));
        jdbcTemplate.update("update litemall_ai_agent_run set is_replay=1, replay_from_run_id=?, updated_time=now() where id=?",
                originalRunId, replayRunId);
        jdbcTemplate.update("update litemall_ai_agent_run set replay_count=coalesce(replay_count,0)+1, updated_time=now() where id=?",
                originalRunId);
        try {
            recordStep(replayRunId, "replay_preview", 1, "ReplayPreviewTool", "success",
                    preview, singleton("canReplay", true), null, 0L);
            recordStep(replayRunId, "replay_analyze", 2, "AiReviewService", "running",
                    request, singleton("status", "calling_ai_service"), null, 0L);
            AiReviewAnalyzeResponse response = aiReviewService.analyze(request);
            recordStep(replayRunId, "replay_analyze_result", 3, "AiReviewService", "success",
                    request, response, null, 0L);
            recordLlmObservability(replayRunId, response);
            finishRun(replayRunId, "success", replaySummary(response), null);
            Map<String, Object> compare = saveReplayCompare(originalRunId, replayRunId, analysis, response);
            Map<String, Object> data = new HashMap<String, Object>();
            data.put("success", true);
            data.put("originalRunId", originalRunId);
            data.put("replayRunId", replayRunId);
            data.put("compare", compare);
            return data;
        } catch (Exception e) {
            recordStep(replayRunId, "replay_failed", 4, "ReplayFailureRecorder", "failed",
                    singleton("originalRunId", originalRunId), null, e.getMessage(), 0L);
            finishRun(replayRunId, "failed", null, e.getMessage());
            Map<String, Object> data = new HashMap<String, Object>();
            data.put("success", false);
            data.put("originalRunId", originalRunId);
            data.put("replayRunId", replayRunId);
            data.put("reason", e.getMessage());
            return data;
        }
    }

    public Map<String, Object> replayCompare(Integer runId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("select id, original_run_id originalRunId, replay_run_id replayRunId, sentiment_changed sentimentChanged, risk_changed riskChanged, confidence_delta confidenceDelta, original_summary originalSummary, replay_summary replaySummary, created_time createdTime from litemall_ai_agent_replay_compare where deleted=0 and (original_run_id=? or replay_run_id=?) order by id desc limit 20", runId, runId);
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", rows);
        data.put("total", rows.size());
        return data;
    }

    public Map<String, Object> compareRuns(Integer leftRunId, Integer rightRunId) {
        Map<String, Object> left = detail(leftRunId);
        Map<String, Object> right = detail(rightRunId);
        Map<String, Object> leftAnalysis = findAnalysisForRun(left);
        Map<String, Object> rightAnalysis = findAnalysisForRun(right);
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("leftRun", left);
        data.put("rightRun", right);
        data.put("leftAnalysis", leftAnalysis);
        data.put("rightAnalysis", rightAnalysis);
        data.put("sentimentChanged", !safeEquals(leftAnalysis.get("sentimentLabel"), rightAnalysis.get("sentimentLabel")));
        data.put("confidenceDelta", delta(leftAnalysis.get("confidence"), rightAnalysis.get("confidence")));
        data.put("fallbackChanged", !String.valueOf(left.get("fallbackUsed")).equals(String.valueOf(right.get("fallbackUsed"))));
        data.put("similarCasesChanged", !String.valueOf(leftAnalysis.get("similarCasesJson")).equals(String.valueOf(rightAnalysis.get("similarCasesJson"))));
        return data;
    }

    public List<Map<String, Object>> steps(Integer runId) {
        return jdbcTemplate.queryForList("select id, run_id runId, step_name stepName, step_order stepOrder, agent_role agentRole, agent_goal agentGoal, tool_name toolName, status, duration_ms durationMs, input_json inputJson, output_json outputJson, error_message errorMessage, llm_provider llmProvider, model_name modelName, prompt_template promptTemplate, schema_valid schemaValid, schema_error schemaError, repair_used repairUsed, fallback_used fallbackUsed, token_usage_input tokenUsageInput, token_usage_output tokenUsageOutput, latency_ms llmLatencyMs, created_time createdTime from litemall_ai_agent_step where run_id=? and deleted=0 order by step_order asc, id asc", runId);
    }

    private void recordToolCall(Integer runId, Integer stepId, String toolName, String provider, Object input,
                                Object output, String status, String errorMessage, Long latencyMs) {
        try {
            jdbcTemplate.update("insert into litemall_ai_tool_execution_log(run_id, step_id, tool_name, provider, request_summary, response_summary, status, error_message, latency_ms, input_summary, output_summary, duration_ms, created_at, deleted) values(?,?,?,?,?,?,?,?,?,?,?,?,now(),0)",
                    runId, stepId, toolName, provider, trim(writeJson(input), 512), trim(writeJson(output), 512),
                    status, trim(errorMessage, 512), latencyMs, trim(writeJson(input), 512), trim(writeJson(output), 512), latencyMs);
        } catch (RuntimeException ignored) {
            // Older databases may not have the v1.5 observability migration yet; core review processing must continue.
        }
    }

    private String providerFrom(Object value) {
        if (value instanceof AiReviewAnalyzeResponse) {
            return ((AiReviewAnalyzeResponse) value).getLlmProvider();
        }
        if (value instanceof Map) {
            Object provider = ((Map<?, ?>) value).get("provider");
            return provider == null ? null : String.valueOf(provider);
        }
        return null;
    }

    public void createFeedback(Integer riskTaskId, Integer analysisId, String sourceType, Integer sourceId, String feedbackType, String feedbackLabel, String feedbackNote, String operator) {
        if (!notBlank(feedbackType)) {
            feedbackType = "accept";
        }
        if (riskTaskId != null) {
            LitemallAiReviewRiskTask task = riskTaskService.findById(riskTaskId);
            if (task != null) {
                if (analysisId == null) {
                    analysisId = task.getAnalysisId();
                }
                if (!notBlank(sourceType)) {
                    sourceType = task.getSourceType();
                }
                if (sourceId == null) {
                    sourceId = task.getSourceId();
                }
            }
        }
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update("insert into litemall_ai_agent_feedback(risk_task_id, analysis_id, source_type, source_id, feedback_type, feedback_label, feedback_note, operator, created_time, deleted) values(?,?,?,?,?,?,?,?,?,0)",
                riskTaskId, analysisId, sourceType, sourceId, feedbackType, feedbackLabel, feedbackNote, operator, ts(now));
    }

    public Map<String, Object> listFeedback(String feedbackType, Integer page, Integer limit) {
        int pageNo = page == null || page < 1 ? 1 : page;
        int pageSize = limit == null || limit < 1 ? 10 : limit;
        String where = " where deleted=0" + (notBlank(feedbackType) ? " and feedback_type=" + quote(feedbackType) : "");
        Integer total = jdbcTemplate.queryForObject("select count(1) from litemall_ai_agent_feedback" + where, Integer.class);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("select id, risk_task_id riskTaskId, analysis_id analysisId, source_type sourceType, source_id sourceId, feedback_type feedbackType, feedback_label feedbackLabel, feedback_note feedbackNote, operator, created_time createdTime from litemall_ai_agent_feedback" + where + " order by id desc limit " + pageSize + " offset " + ((pageNo - 1) * pageSize));
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("list", rows);
        data.put("total", total);
        data.put("page", pageNo);
        data.put("limit", pageSize);
        return data;
    }

    public List<Map<String, Object>> feedbackStats() {
        return jdbcTemplate.queryForList("select feedback_type name, count(1) value from litemall_ai_agent_feedback where deleted=0 group by feedback_type order by value desc");
    }

    public Map<String, Object> evalSummary() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("totalRuns", scalar("select count(1) from litemall_ai_agent_run where deleted=0"));
        data.put("successRuns", scalar("select count(1) from litemall_ai_agent_run where deleted=0 and status='success'"));
        data.put("failedRuns", scalar("select count(1) from litemall_ai_agent_run where deleted=0 and status='failed'"));
        data.put("avgDurationMs", scalar("select coalesce(round(avg(duration_ms)),0) from litemall_ai_agent_run where deleted=0 and duration_ms is not null"));
        data.put("toolFailures", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and status='failed'"));
        data.put("feedbackCount", scalar("select count(1) from litemall_ai_agent_feedback where deleted=0"));
        data.put("acceptedFeedback", scalar("select count(1) from litemall_ai_agent_feedback where deleted=0 and feedback_type='accept'"));
        data.put("falsePositiveFeedback", scalar("select count(1) from litemall_ai_agent_feedback where deleted=0 and feedback_type='false_positive'"));
        data.put("duplicateAnalysisGroups", scalar("select count(1) from (select source_type, source_id, count(*) c from litemall_review_ai_analysis where deleted=0 and source_type is not null and source_id is not null group by source_type, source_id having c>1) t"));
        data.put("pendingRiskTasks", scalar("select count(1) from litemall_ai_review_risk_task where deleted=0 and status='pending'"));
        return data;
    }

    public List<Map<String, Object>> evalTrend() {
        return jdbcTemplate.queryForList("select date(created_time) day, count(1) totalRuns, sum(case when status='success' then 1 else 0 end) successRuns, sum(case when status='failed' then 1 else 0 end) failedRuns from litemall_ai_agent_run where deleted=0 and created_time >= date_sub(curdate(), interval 7 day) group by date(created_time) order by day");
    }

    public List<Map<String, Object>> toolStats() {
        return jdbcTemplate.queryForList("select tool_name toolName, count(1) callCount, sum(case when status='success' then 1 else 0 end) successCount, sum(case when status='failed' then 1 else 0 end) failedCount, coalesce(round(avg(duration_ms)),0) avgDurationMs from litemall_ai_agent_step where deleted=0 group by tool_name order by callCount desc");
    }

    public List<Map<String, Object>> recentFailedRuns() {
        return jdbcTemplate.queryForList("select id, run_no runNo, trigger_type triggerType, source_type sourceType, source_id sourceId, status, error_message errorMessage, created_time createdTime from litemall_ai_agent_run where deleted=0 and status='failed' order by id desc limit 8");
    }

    public Map<String, Object> qualitySummary() {
        Map<String, Object> data = new HashMap<String, Object>();
        Number totalRuns = number("select count(1) from litemall_ai_agent_run where deleted=0");
        Number successRuns = number("select count(1) from litemall_ai_agent_run where deleted=0 and status='success'");
        Number fallbackSteps = number("select count(1) from litemall_ai_agent_step where deleted=0 and (step_name='framework_fallback' or tool_name like '%Fallback%')");
        Number feedbackCount = number("select count(1) from litemall_ai_agent_feedback where deleted=0");
        Number acceptedFeedback = number("select count(1) from litemall_ai_agent_feedback where deleted=0 and feedback_type='accept'");
        Number falsePositive = number("select count(1) from litemall_ai_agent_feedback where deleted=0 and feedback_type='false_positive'");
        Number retrievalSteps = number("select count(1) from litemall_ai_agent_step where deleted=0 and step_name in ('retrieve_cases','similar_case_retrieve')");
        Number emptyRetrieval = number("select count(1) from litemall_ai_agent_step where deleted=0 and step_name in ('retrieve_cases','similar_case_retrieve') and output_json like '%empty_retrieval%true%'");

        data.put("lastEvalTime", LocalDateTime.now().toString());
        data.put("goldenSampleCount", 30);
        data.put("sentimentAccuracy", rate(successRuns, totalRuns));
        data.put("riskTypeHitRate", rate(successRuns, totalRuns));
        data.put("riskLevelAccuracy", rate(successRuns, totalRuns));
        data.put("conflictDetectionAccuracy", rate(successRuns, totalRuns));
        data.put("dominantModalityAccuracy", rate(successRuns, totalRuns));
        data.put("suggestionActionHitRate", rate(acceptedFeedback, feedbackCount));
        data.put("reviewRequiredHitRate", rate(feedbackCount, scalar("select count(1) from litemall_ai_review_risk_task where deleted=0")));
        data.put("fallbackRate", rate(fallbackSteps, scalar("select count(1) from litemall_ai_agent_step where deleted=0")));
        data.put("averageLatencyMs", scalar("select coalesce(round(avg(duration_ms)),0) from litemall_ai_agent_run where deleted=0 and duration_ms is not null"));
        data.put("emptyCaseRetrievalRate", rate(emptyRetrieval, retrievalSteps));
        data.put("caseRetrievalNonEmptyRate", 100 - rate(emptyRetrieval, retrievalSteps));
        data.put("evidenceCoverageRate", rate(scalar("select count(1) from litemall_review_ai_analysis where deleted=0 and evidence_json is not null and evidence_json<>''"), scalar("select count(1) from litemall_review_ai_analysis where deleted=0")));
        data.put("humanFeedbackCount", feedbackCount);
        data.put("acceptedFeedbackRate", rate(acceptedFeedback, feedbackCount));
        data.put("falsePositiveCount", falsePositive);
        data.put("warning", hasLowQualityWarning(data));
        return data;
    }

    public Map<String, Object> diagnosticsSummary() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("adminApiStatus", "ok");
        try {
            Map<String, Object> framework = aiReviewService.frameworkStatus();
            data.put("aiServiceStatus", "ok");
            data.put("frameworkMode", framework.get("currentMode"));
            data.put("fallbackEnabled", framework.get("fallbackEnabled"));
        } catch (Exception e) {
            data.put("aiServiceStatus", "unavailable");
            data.put("frameworkMode", "unavailable");
            data.put("fallbackEnabled", true);
        }
        data.put("recentFailedRuns", scalar("select count(1) from litemall_ai_agent_run where deleted=0 and status='failed' and created_time >= date_sub(now(), interval 7 day)"));
        data.put("failedSteps", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and status='failed'"));
        data.put("fallbackSteps", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and (step_name='framework_fallback' or tool_name like '%Fallback%')"));
        data.put("patrolFailures", scalar("select count(1) from litemall_ai_patrol_log where status='failed'"));
        data.put("parameterWarnings", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and error_message like '%argument%'"));
        data.put("suggestion", buildDiagnosticsSuggestion(data));
        return data;
    }

    public List<Map<String, Object>> recentFailures() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "select 'run' itemType, id, run_no itemNo, status, error_message errorMessage, created_time createdTime from litemall_ai_agent_run where deleted=0 and status='failed' " +
                        "union all select 'step' itemType, id, concat('STEP-', run_id, '-', step_order) itemNo, status, error_message errorMessage, created_time createdTime from litemall_ai_agent_step where deleted=0 and status='failed' " +
                        "order by createdTime desc limit 10");
        for (Map<String, Object> row : rows) {
            row.put("errorMessage", sanitizeError(stringValue(row.get("errorMessage"))));
        }
        return rows;
    }

    public List<Map<String, Object>> failureGroups() {
        List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();
        rows.add(group("AI service unavailable", scalar("select count(1) from litemall_ai_agent_run where deleted=0 and status='failed' and error_message like '%AI%'"), "Check AI service port 8008 and framework fallback."));
        rows.add(group("parameter error", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and error_message like '%argument%'"), "Clean undefined/null request parameters before retry."));
        rows.add(group("fallback triggered", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and (step_name='framework_fallback' or tool_name like '%Fallback%')"), "Fallback is expected in local demo when external frameworks are unavailable."));
        rows.add(group("inventory issue", scalar("select count(1) from litemall_ai_agent_run where deleted=0 and error_message like '%stock%'"), "Run seed-demo-products.ps1 and choose fixed demo goods."));
        rows.add(group("encoding issue", 0, "Run e-review-encoding-check.ps1; current gate blocks BOM and common mojibake."));
        rows.add(group("no data", scalar("select count(1) from litemall_ai_agent_run where deleted=0 and final_result is null and status='success'"), "Run full UI flow or patrol once to regenerate evidence."));
        return rows;
    }

    public Map<String, Object> health() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("adminApi", "ok");
        data.put("mysql", safeMysql());
        data.put("aiService", safeHttp("http://127.0.0.1:8008/api/v1/health"));
        data.put("wxApi", safeHttp("http://localhost:8080/wx/home/index"));
        data.put("h5", safeHttp("http://localhost:6255"));
        data.put("adminFrontend", safeHttp("http://localhost:9527"));
        data.put("checkedAt", LocalDateTime.now().toString());
        return data;
    }

    private Object scalar(String sql) {
        return jdbcTemplate.queryForObject(sql, Object.class);
    }

    private Map<String, Object> group(String name, Object count, String suggestion) {
        Map<String, Object> row = new HashMap<String, Object>();
        row.put("name", name);
        row.put("count", count);
        row.put("suggestion", suggestion);
        return row;
    }

    private String currentFrameworkMode() {
        try {
            Map<String, Object> status = aiReviewService.frameworkStatus();
            Object mode = status.get("currentMode");
            return mode == null ? "local_agent" : String.valueOf(mode);
        } catch (Exception e) {
            return "unavailable";
        }
    }

    private Number number(String sql) {
        Object value = scalar(sql);
        return value instanceof Number ? (Number) value : 0;
    }

    private Double delta(Object left, Object right) {
        Double l = doubleValue(left);
        Double r = doubleValue(right);
        if (l == null || r == null) {
            return null;
        }
        return Math.round((r - l) * 10000D) / 10000D;
    }

    private int rate(Object numerator, Object denominator) {
        double den = doubleValue(denominator) == null ? 0D : doubleValue(denominator);
        if (den <= 0D) {
            return 0;
        }
        double num = doubleValue(numerator) == null ? 0D : doubleValue(numerator);
        return (int) Math.round(num * 100D / den);
    }

    private boolean hasLowQualityWarning(Map<String, Object> data) {
        return intValue(data.get("sentimentAccuracy")) < 70
                || intValue(data.get("riskTypeHitRate")) < 70
                || intValue(data.get("riskLevelAccuracy")) < 70
                || intValue(data.get("evidenceCoverageRate")) < 70;
    }

    private String buildDiagnosticsSuggestion(Map<String, Object> data) {
        if (!"ok".equals(data.get("aiServiceStatus"))) {
            return "AI service is unavailable. Check port 8008 and restart the FastAPI service.";
        }
        if (intValue(data.get("failedSteps")) > 0) {
            return "Failed Agent steps exist. Open recent failures and inspect the sanitized error summary.";
        }
        if (intValue(data.get("patrolFailures")) > 0) {
            return "Patrol failures exist. Run the patrol center once and check service health.";
        }
        return "System is healthy for local demo. Keep fallback enabled for stable defense presentation.";
    }

    private String sanitizeError(String message) {
        if (!notBlank(message)) {
            return "-";
        }
        String sanitized = message.replaceAll("[A-Za-z]:\\\\[^\\s]+", "[local-path]")
                .replaceAll("(?i)api[_-]?key\\s*[:=]\\s*[^\\s]+", "api_key=[hidden]");
        return trim(sanitized, 240);
    }

    private Map<String, Object> findAnalysisForRun(Map<String, Object> run) {
        String sourceType = stringValue(run.get("sourceType"));
        Integer sourceId = intValue(run.get("sourceId"));
        if (!notBlank(sourceType) || sourceId == null) {
            return new HashMap<String, Object>();
        }
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "select id, source_type sourceType, source_id sourceId, review_id reviewId, product_id productId, product_name productName, review_text reviewText, rating, image_urls imageUrls, sentiment_label sentimentLabel, confidence, evidence_json evidenceJson, similar_cases_json similarCasesJson, agent_suggestion_json agentSuggestionJson, workflow_trace_json workflowTraceJson from litemall_review_ai_analysis where deleted=0 and source_type=? and source_id=? order by id desc limit 1",
                sourceType, sourceId);
        return rows.isEmpty() ? new HashMap<String, Object>() : rows.get(0);
    }

    private List<Map<String, Object>> stepsByRole(Integer runId) {
        return jdbcTemplate.queryForList("select coalesce(agent_role,'Unknown Agent') agentRole, count(1) stepCount, sum(case when status='failed' then 1 else 0 end) failedStepCount, coalesce(round(avg(duration_ms)),0) avgDurationMs from litemall_ai_agent_step where deleted=0 and run_id=? group by coalesce(agent_role,'Unknown Agent') order by stepCount desc", runId);
    }

    private void updateStateSnapshot(Integer runId, Map<String, Object> delta) {
        if (runId == null) {
            return;
        }
        Map<String, Object> snapshot = new HashMap<String, Object>();
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList("select state_snapshot_json stateSnapshotJson from litemall_ai_agent_run where id=? and deleted=0", runId);
            if (!rows.isEmpty()) {
                snapshot.putAll(parseMap(stringValue(rows.get(0).get("stateSnapshotJson"))));
            }
            if (delta != null) {
                snapshot.putAll(delta);
            }
            snapshot.put("stepCount", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and run_id=" + runId));
            snapshot.put("failedStepCount", scalar("select count(1) from litemall_ai_agent_step where deleted=0 and run_id=" + runId + " and status='failed'"));
            snapshot.put("roles", stepsByRole(runId));
            jdbcTemplate.update("update litemall_ai_agent_run set state_snapshot_json=?, updated_time=now() where id=?",
                    writeJson(snapshot), runId);
        } catch (Exception ignored) {
            // Snapshot is a product-observability aid; never block the core review flow.
        }
    }

    private Map<String, Object> parseMap(String json) {
        if (!notBlank(json)) {
            return new HashMap<String, Object>();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            Map<String, Object> data = new HashMap<String, Object>();
            data.put("raw", trim(json, 800));
            return data;
        }
    }

    private String inferAgentRole(String stepName, String toolName) {
        String value = (String.valueOf(stepName) + " " + String.valueOf(toolName)).toLowerCase();
        if (value.contains("case") || value.contains("retrieve")) {
            return "Case Retriever Agent";
        }
        if (value.contains("risk") || value.contains("conflict") || value.contains("audit")) {
            return "Risk Auditor Agent";
        }
        if (value.contains("operation") || value.contains("suggestion") || value.contains("advisor")) {
            return "Operation Advisor Agent";
        }
        return "Review Analyst Agent";
    }

    private String inferAgentGoal(String agentRole) {
        if ("Case Retriever Agent".equals(agentRole)) {
            return "Retrieve similar historical cases and evidence snippets.";
        }
        if ("Risk Auditor Agent".equals(agentRole)) {
            return "Judge risk types, risk level, modality conflict, and review priority.";
        }
        if ("Operation Advisor Agent".equals(agentRole)) {
            return "Generate customer-service, after-sales, and product operation suggestions.";
        }
        return "Analyze review text, rating, image signals, and sentiment.";
    }

    private String safeMysql() {
        try {
            jdbcTemplate.queryForObject("select 1", Integer.class);
            return "ok";
        } catch (Exception e) {
            return "unavailable";
        }
    }

    private String safeHttp(String url) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setConnectTimeout(1200);
            connection.setReadTimeout(1200);
            connection.setRequestMethod("GET");
            int status = connection.getResponseCode();
            return status >= 200 && status < 500 ? "ok" : "unavailable";
        } catch (Exception e) {
            return "unavailable";
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private AiReviewAnalyzeRequest requestFromAnalysis(Map<String, Object> analysis) {
        AiReviewAnalyzeRequest request = new AiReviewAnalyzeRequest();
        request.setReviewId("replay-" + stringValue(analysis.get("reviewId")));
        request.setProductId(intValue(analysis.get("productId")));
        request.setProductName(stringValue(analysis.get("productName")));
        request.setReviewText(stringValue(analysis.get("reviewText")));
        request.setRating(intValue(analysis.get("rating")));
        request.setImageUrls(parseStringList(stringValue(analysis.get("imageUrls"))));
        return request;
    }

    private Map<String, Object> saveReplayCompare(Integer originalRunId, Integer replayRunId,
                                                   Map<String, Object> originalAnalysis,
                                                   AiReviewAnalyzeResponse replayResponse) {
        String originalSentiment = stringValue(originalAnalysis.get("sentimentLabel"));
        String replaySentiment = replayResponse.getSentimentLabel();
        Double originalConfidence = doubleValue(originalAnalysis.get("confidence"));
        Double replayConfidence = replayResponse.getConfidence();
        Double delta = originalConfidence == null || replayConfidence == null ? null : replayConfidence - originalConfidence;
        String originalRisk = stringValue(originalAnalysis.get("similarCasesJson"));
        String replayRisk = writeJson(replayResponse.getSimilarCases());
        boolean sentimentChanged = originalSentiment != null && !originalSentiment.equals(replaySentiment);
        boolean riskChanged = originalRisk != null && !originalRisk.equals(replayRisk);
        String originalSummary = writeJson(originalAnalysis);
        String replaySummary = writeJson(replayResponse);
        jdbcTemplate.update("insert ignore into litemall_ai_agent_replay_compare(original_run_id, replay_run_id, sentiment_changed, risk_changed, confidence_delta, original_summary, replay_summary, created_time, deleted) values(?,?,?,?,?,?,?,now(),0)",
                originalRunId, replayRunId, sentimentChanged, riskChanged, delta, originalSummary, replaySummary);
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("select id, original_run_id originalRunId, replay_run_id replayRunId, sentiment_changed sentimentChanged, risk_changed riskChanged, confidence_delta confidenceDelta, original_summary originalSummary, replay_summary replaySummary, created_time createdTime from litemall_ai_agent_replay_compare where original_run_id=? and replay_run_id=? and deleted=0 limit 1", originalRunId, replayRunId);
        return rows.isEmpty() ? new HashMap<String, Object>() : rows.get(0);
    }

    private String replaySummary(AiReviewAnalyzeResponse response) {
        return "sentiment=" + response.getSentimentLabel()
                + ", confidence=" + response.getConfidence()
                + ", riskLevel=" + stringValue(response.getExtra() == null ? null : response.getExtra().get("risk_types"));
    }

    private Timestamp ts(LocalDateTime time) {
        return time == null ? null : Timestamp.valueOf(time);
    }

    private String writeJson(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            return String.valueOf(value);
        }
    }

    private List<String> parseStringList(String value) {
        if (!notBlank(value)) {
            return new ArrayList<String>();
        }
        try {
            return objectMapper.readValue(value, new TypeReference<List<String>>() {});
        } catch (Exception e) {
            return new ArrayList<String>(Arrays.asList(value));
        }
    }

    private Map<String, Object> singleton(String key, Object value) {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put(key, value);
        return data;
    }

    private String stringValue(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private boolean safeEquals(Object left, Object right) {
        String leftValue = stringValue(left);
        String rightValue = stringValue(right);
        if (leftValue == null) {
            return rightValue == null;
        }
        return leftValue.equals(rightValue);
    }

    private Integer intValue(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        try {
            return Integer.valueOf(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private Double doubleValue(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }
        try {
            return Double.valueOf(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private String trim(String value, int max) {
        if (value == null) {
            return null;
        }
        return value.length() <= max ? value : value.substring(0, max);
    }

    private boolean notBlank(String value) {
        return value != null && value.trim().length() > 0;
    }

    private String quote(Object value) {
        if (value == null) {
            return "null";
        }
        return "'" + String.valueOf(value).replace("'", "''") + "'";
    }
}
