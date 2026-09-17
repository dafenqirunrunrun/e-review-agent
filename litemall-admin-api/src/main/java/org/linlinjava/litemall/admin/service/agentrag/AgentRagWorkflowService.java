package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.linlinjava.litemall.db.domain.LitemallAgentRagAuditChain;
import org.linlinjava.litemall.db.domain.LitemallAgentRagOverride;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;
import org.linlinjava.litemall.db.service.LitemallAgentRagAuditChainService;
import org.linlinjava.litemall.db.service.LitemallAgentRagEvidenceService;
import org.linlinjava.litemall.db.service.LitemallAgentRagOverrideService;
import org.linlinjava.litemall.db.service.LitemallAgentRagRunService;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import javax.annotation.Resource;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;

@Service
public class AgentRagWorkflowService {
    private static final Logger logger = LoggerFactory.getLogger(AgentRagWorkflowService.class);
    public static final String STATUS_RUNNING = "RUNNING";
    public static final String STATUS_SUCCESS = "SUCCESS";
    public static final String STATUS_RULE_FALLBACK = "RULE_FALLBACK";
    public static final String STATUS_FAILED = "FAILED";
    public static final String STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED";

    private static final List<String> RISK_LEVELS = Arrays.asList("none", "low", "medium", "high", "critical");
    private static final List<String> ACTIONS = Arrays.asList("none", "monitor", "reply", "hide", "escalate", "refund_review", "manual_review");
    private static final Pattern WINDOWS_PATH = Pattern.compile("[A-Za-z]:\\\\[^\\s\\\"]+");
    private static final Pattern UNIX_PATH = Pattern.compile("(?<![A-Za-z0-9_])/(?:home|Users|mnt|var|tmp|opt)/[^\\s\\\"]+");

    @Resource
    private AgentRagClient agentRagClient;
    @Resource
    private AgentRagTenantResolver tenantResolver;
    @Resource
    private AgentRagConfig config;
    @Resource
    private ObjectMapper objectMapper;
    @Resource
    private LitemallAgentRagRunService runService;
    @Resource
    private LitemallAgentRagEvidenceService evidenceService;
    @Resource
    private LitemallAgentRagOverrideService overrideService;
    @Resource
    private AgentRagRuntimeMetricsService metricsService;
    @Resource
    private AgentRagAuditIntegrityService auditIntegrityService;
    @Resource
    private LitemallAgentRagAuditChainService auditChainService;

    public AgentRagWorkflowResult analyze(AgentRagAnalyzeRequest request) {
        return analyze(request, null, null);
    }

    public AgentRagWorkflowResult replay(Long replayOfRunId) {
        LitemallAgentRagRun original = requireRun(replayOfRunId);
        AgentRagAnalyzeRequest request = new AgentRagAnalyzeRequest();
        request.setRequestId("replay-" + UUID.randomUUID().toString().replace("-", ""));
        request.setTenantId(original.getTenantId());
        request.setSubjectType(original.getSubjectType());
        request.setSubjectId(original.getSubjectId());
        request.setQuery("Replay Agent-RAG analysis for " + original.getSubjectType() + ":" + original.getSubjectId());
        request.setRuntimeMode(safeRequestRuntimeMode(original.getRuntimeMode()));
        request.setSchemaVersion(original.getSchemaVersion() == null ? "2.0.0" : original.getSchemaVersion());
        return analyze(request, original.getParentRunId(), original.getId());
    }

    public AgentRagWorkflowResult analyze(AgentRagAnalyzeRequest request, Long parentRunId, Long replayOfRunId) {
        tenantResolver.applyTrustedTenant(request);
        request.validate(config);
        MDC.put("agentRag.requestId", request.getRequestId());
        MDC.put("agentRag.tenantId", request.getTenantId());
        MDC.put("agentRag.subjectId", request.getSubjectId());
        metricsService.recordRequest();
        logger.info("agent_rag_workflow_started");
        String idempotencyKey = computeIdempotencyKey(request, parentRunId, replayOfRunId);
        LitemallAgentRagRun existing = runService.findByIdempotencyKey(idempotencyKey);
        if (existing != null) {
            metricsService.recordIdempotencyHit();
            logger.info("agent_rag_workflow_idempotency_hit");
            MDC.clear();
            return new AgentRagWorkflowResult(existing, evidenceService.findByRunId(existing.getId()), null, true);
        }

        LocalDateTime startedAt = LocalDateTime.now();
        LitemallAgentRagRun run = newRun(request, idempotencyKey, parentRunId, replayOfRunId, startedAt);
        try {
            runService.create(run);
        } catch (DuplicateKeyException e) {
            LitemallAgentRagRun duplicate = runService.findByIdempotencyKey(idempotencyKey);
            if (duplicate != null) {
                metricsService.recordIdempotencyHit();
                logger.info("agent_rag_workflow_duplicate_key_replayed");
                MDC.clear();
                return new AgentRagWorkflowResult(duplicate, evidenceService.findByRunId(duplicate.getId()), null, true);
            }
            throw e;
        }

        try {
            AgentRagAnalyzeResponse response = agentRagClient.analyze(request);
            LocalDateTime finishedAt = LocalDateTime.now();
            LitemallAgentRagEvidence evidence = buildEvidence(run, response, finishedAt);
            String previousAuditHash = previousAuditHash(run.getTenantId());
            completeRun(run, response, evidence, startedAt, finishedAt);
            auditIntegrityService.applySecurityAndAudit(run, response, evidence, previousAuditHash);
            evidenceService.create(evidence);
            runService.update(run);
            updateAuditChain(run);
            metricsService.recordSuccess(Boolean.TRUE.equals(run.getFallbackUsed()), Duration.between(startedAt, finishedAt).toMillis());
            MDC.put("agentRag.runId", String.valueOf(run.getId()));
            logger.info("agent_rag_workflow_finished status={} fallbackUsed={}", run.getStatus(), run.getFallbackUsed());
            return new AgentRagWorkflowResult(run, evidence, response, false);
        } catch (RuntimeException ex) {
            failRun(run, ex, startedAt, LocalDateTime.now());
            runService.update(run);
            metricsService.recordFailure(Duration.between(startedAt, LocalDateTime.now()).toMillis());
            MDC.put("agentRag.runId", String.valueOf(run.getId()));
            logger.warn("agent_rag_workflow_failed code={}", run.getErrorCode());
            throw ex;
        } finally {
            MDC.clear();
        }
    }

    public LitemallAgentRagOverride appendOverride(AgentRagOverrideRequest request) {
        validateOverride(request);
        LitemallAgentRagRun run = requireRun(request.getRunId());
        String tenantId = tenantResolver.resolveCurrentTenant();
        if (!tenantId.equals(run.getTenantId())) {
            throw new AgentRagClientException("AGENT_RAG_OVERRIDE_TENANT_MISMATCH", "Override tenant does not match run tenant.");
        }

        LitemallAgentRagOverride override = new LitemallAgentRagOverride();
        override.setRunId(run.getId());
        override.setTenantId(tenantId);
        override.setPreviousRiskLevel(run.getRiskLevel());
        override.setNewRiskLevel(normalizeEnum(request.getNewRiskLevel()));
        override.setPreviousAction(run.getAction());
        override.setNewAction(normalizeEnum(request.getNewAction()));
        override.setReason(trimToLength(request.getReason(), 1000));
        override.setOperatorId(request.getOperatorId());
        override.setCreatedAt(LocalDateTime.now());
        List<LitemallAgentRagOverride> history = overrideService.listByRun(tenantId, run.getId());
        String previousOverrideHash = history == null || history.isEmpty() ? null : history.get(0).getOverrideHash();
        run.setRiskLevel(override.getNewRiskLevel());
        run.setAction(override.getNewAction());
        String effectiveDecisionHash = auditIntegrityService.effectiveDecisionHash(run, null);
        AgentRagAuditIntegrityService.LitemallAgentRagOverrideView view = new AgentRagAuditIntegrityService.LitemallAgentRagOverrideView();
        view.previousOverrideHash = previousOverrideHash;
        view.effectiveDecisionHash = effectiveDecisionHash;
        view.operatorId = override.getOperatorId();
        view.reason = override.getReason();
        view.createdAt = override.getCreatedAt().toString();
        override.setPreviousOverrideHash(previousOverrideHash);
        override.setEffectiveDecisionHash(effectiveDecisionHash);
        override.setOverrideHash(auditIntegrityService.overrideHash(view, run.getAuditHash(), run.getEffectiveDecisionHash()));
        override.setDeleted(false);
        overrideService.create(override);
        return override;
    }

    public LitemallAgentRagRun findRun(Long id) {
        return requireRun(id);
    }

    public LitemallAgentRagEvidence findEvidence(Long runId) {
        return evidenceService.findByRunId(runId);
    }

    public List<LitemallAgentRagOverride> overrideHistory(Long runId) {
        LitemallAgentRagRun run = requireRun(runId);
        return overrideService.listByRun(run.getTenantId(), run.getId());
    }

    public List<LitemallAgentRagRun> recentRuns(String status, Integer limit) {
        return runService.recent(tenantResolver.resolveCurrentTenant(), status, limit);
    }

    public Map<String, Object> listRuns(String subjectType, String subjectId, String requestId,
                                        String status, String riskLevel, String providerImpl,
                                        Boolean fallbackUsed, Boolean requiresHumanReview,
                                        String createdFrom, String createdTo, Integer page, Integer limit) {
        String tenantId = tenantResolver.resolveCurrentTenant();
        List<LitemallAgentRagRun> runs = runService.listForAdmin(tenantId, subjectType, subjectId, requestId,
                status, riskLevel, providerImpl, fallbackUsed, requiresHumanReview, createdFrom, createdTo, page, limit);
        long total = runService.countForAdmin(tenantId, subjectType, subjectId, requestId, status, riskLevel,
                providerImpl, fallbackUsed, requiresHumanReview, createdFrom, createdTo);
        List<Long> runIds = new ArrayList<Long>();
        for (LitemallAgentRagRun run : runs) {
            runIds.add(run.getId());
        }
        Map<Long, LitemallAgentRagOverride> latestOverrides = latestOverrideMap(tenantId, runIds);
        Map<Long, Integer> overrideCounts = overrideCountMap(tenantId, runIds);
        List<Map<String, Object>> items = new ArrayList<Map<String, Object>>();
        for (LitemallAgentRagRun run : runs) {
            items.add(runProjection(run, latestOverrides.get(run.getId()), overrideCounts.get(run.getId())));
        }
        Map<String, Object> result = new LinkedHashMap<String, Object>();
        result.put("items", items);
        result.put("total", total);
        result.put("page", page == null || page <= 0 ? 1 : page);
        result.put("limit", limit == null || limit <= 0 ? 20 : Math.min(limit, 100));
        return result;
    }

    public Map<String, Object> overview(String createdFrom, String createdTo, int maxSampleSize) {
        String tenantId = tenantResolver.resolveCurrentTenant();
        int safeLimit = maxSampleSize <= 0 || maxSampleSize > 10000 ? 10000 : maxSampleSize;
        List<LitemallAgentRagRun> runs = runService.overviewWindow(tenantId, createdFrom, createdTo, safeLimit);
        long total = runService.countForAdmin(tenantId, null, null, null, null, null, null, null, null, createdFrom, createdTo);
        long overrideCount = overrideService.countInWindow(tenantId, createdFrom, createdTo);
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("todayRunCount", total);
        data.put("todaySuccessCount", countStatus(runs, STATUS_SUCCESS));
        data.put("todayHighRiskCount", countRisk(runs, "high"));
        data.put("todayReviewRequiredCount", countReviewRequired(runs));
        data.put("todayFallbackCount", countFallback(runs));
        data.put("todayFailureCount", countStatus(runs, STATUS_FAILED));
        data.put("averageDurationMs", averageDuration(runs));
        data.put("p95DurationMs", percentileDuration(runs, 0.95));
        data.put("overrideCount", overrideCount);
        data.put("replayCount", countReplay(runs));
        data.put("statusDistribution", distribution(runs, "status"));
        data.put("riskDistribution", distribution(runs, "risk"));
        data.put("providerDistribution", distribution(runs, "provider"));
        data.put("fallbackDistribution", distribution(runs, "fallback"));
        data.put("recentFailures", projectLimited(filterRecentFailures(runs), 10));
        data.put("pendingReviews", projectLimited(filterPendingReviews(runs), 10));
        data.put("sampled", total > runs.size());
        data.put("sampleSize", runs.size());
        data.put("maxSampleSize", safeLimit);
        return data;
    }

    public Map<String, Object> compareRuns(Long baseRunId, Long compareRunId) {
        LitemallAgentRagRun base = requireRun(baseRunId);
        LitemallAgentRagRun other = requireRun(compareRunId);
        String tenantId = tenantResolver.resolveCurrentTenant();
        if (!tenantId.equals(base.getTenantId()) || !tenantId.equals(other.getTenantId())) {
            throw new AgentRagClientException("AGENT_RAG_TENANT_MISMATCH", "Run tenant does not match current tenant.");
        }
        Map<String, Object> changes = new LinkedHashMap<String, Object>();
        changes.put("riskLevelChanged", !value(base.getRiskLevel()).equals(value(other.getRiskLevel())));
        changes.put("actionChanged", !value(base.getAction()).equals(value(other.getAction())));
        changes.put("confidenceDelta", decimalDelta(base, other));
        changes.put("providerChanged", !value(base.getEffectiveProviderImpl()).equals(value(other.getEffectiveProviderImpl())));
        changes.put("indexVersionChanged", !value(base.getIndexVersion()).equals(value(other.getIndexVersion())));
        changes.put("fallbackChanged", !value(base.getFallbackUsed()).equals(value(other.getFallbackUsed())));
        changes.put("citationAdded", Collections.emptyList());
        changes.put("citationRemoved", Collections.emptyList());
        changes.put("durationDeltaMs", safeLong(other.getDurationMs()) - safeLong(base.getDurationMs()));
        changes.put("baseStatus", base.getStatus());
        changes.put("compareStatus", other.getStatus());
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("baseRunId", base.getId());
        data.put("compareRunId", other.getId());
        data.put("baseReplayOfRunId", base.getReplayOfRunId());
        data.put("compareReplayOfRunId", other.getReplayOfRunId());
        data.put("changes", changes);
        return data;
    }

    public Map<String, Object> verifyIntegrity(Long runId) {
        LitemallAgentRagRun run = requireRun(runId);
        String tenantId = tenantResolver.resolveCurrentTenant();
        if (!tenantId.equals(run.getTenantId())) {
            throw new AgentRagClientException("AGENT_RAG_TENANT_MISMATCH", "Run tenant does not match current tenant.");
        }
        return auditIntegrityService.verifyRun(run, evidenceService.findByRunId(run.getId()));
    }

    public Map<String, Object> securityStatus() {
        return auditIntegrityService.securityStatus(tenantResolver.resolveCurrentTenant());
    }

    String computeIdempotencyKey(AgentRagAnalyzeRequest request, Long parentRunId, Long replayOfRunId) {
        String retrievalMode = request.getRetrieval() == null ? "" : request.getRetrieval().getRequestedMode();
        String replayNonce = replayOfRunId == null ? "" : request.getRequestId();
        String raw = tenantResolver.resolveCurrentTenant() + "|" + value(request.getSubjectType()) + "|" +
                value(request.getSubjectId()) + "|" + value(request.getSchemaVersion()) + "|" +
                value(request.getRuntimeMode()) + "|" + value(retrievalMode) + "|" +
                value(parentRunId) + "|" + value(replayOfRunId) + "|" + value(replayNonce);
        return sha256(raw);
    }

    private Map<Long, LitemallAgentRagOverride> latestOverrideMap(String tenantId, List<Long> runIds) {
        Map<Long, LitemallAgentRagOverride> data = new LinkedHashMap<Long, LitemallAgentRagOverride>();
        for (LitemallAgentRagOverride override : overrideService.latestByRuns(tenantId, runIds)) {
            if (!data.containsKey(override.getRunId())) {
                data.put(override.getRunId(), override);
            }
        }
        return data;
    }

    private Map<Long, Integer> overrideCountMap(String tenantId, List<Long> runIds) {
        Map<Long, Integer> data = new LinkedHashMap<Long, Integer>();
        for (Map<String, Object> row : overrideService.countByRuns(tenantId, runIds)) {
            Long runId = toLong(row.get("runId"));
            Integer count = toInteger(row.get("count"));
            if (runId != null) {
                data.put(runId, count == null ? 0 : count);
            }
        }
        return data;
    }

    private Map<String, Object> runProjection(LitemallAgentRagRun run, LitemallAgentRagOverride latestOverride, Integer overrideCount) {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("id", run.getId());
        data.put("requestId", run.getRequestId());
        data.put("subjectType", run.getSubjectType());
        data.put("subjectId", run.getSubjectId());
        data.put("status", run.getStatus());
        data.put("originalRiskLevel", run.getRiskLevel());
        data.put("effectiveRiskLevel", latestOverride == null ? run.getRiskLevel() : latestOverride.getNewRiskLevel());
        data.put("originalAction", run.getAction());
        data.put("effectiveAction", latestOverride == null ? run.getAction() : latestOverride.getNewAction());
        data.put("confidence", run.getConfidence());
        data.put("requestedProviderImpl", run.getRequestedProviderImpl());
        data.put("effectiveProviderImpl", run.getEffectiveProviderImpl());
        data.put("requestedRetrievalMode", run.getRequestedRetrievalMode());
        data.put("effectiveRetrievalMode", run.getEffectiveRetrievalMode());
        data.put("indexVersion", run.getIndexVersion());
        data.put("fallbackUsed", run.getFallbackUsed());
        data.put("fallbackReason", run.getFallbackReason());
        data.put("requiresHumanReview", run.getRequiresHumanReview());
        data.put("durationMs", run.getDurationMs());
        data.put("errorCode", run.getErrorCode());
        data.put("errorMessage", trimToLength(run.getErrorMessage(), 160));
        data.put("overrideCount", overrideCount == null ? 0 : overrideCount);
        data.put("replayCount", run.getReplayOfRunId() == null ? 0 : 1);
        data.put("parentRunId", run.getParentRunId());
        data.put("replayOfRunId", run.getReplayOfRunId());
        data.put("createdAt", run.getCreatedAt());
        data.put("finishedAt", run.getFinishedAt());
        return data;
    }

    private List<Map<String, Object>> projectLimited(List<LitemallAgentRagRun> runs, int limit) {
        List<Map<String, Object>> data = new ArrayList<Map<String, Object>>();
        int count = Math.min(limit, runs.size());
        for (int i = 0; i < count; i++) {
            data.add(runProjection(runs.get(i), null, 0));
        }
        return data;
    }

    private List<LitemallAgentRagRun> filterRecentFailures(List<LitemallAgentRagRun> runs) {
        List<LitemallAgentRagRun> data = new ArrayList<LitemallAgentRagRun>();
        for (LitemallAgentRagRun run : runs) {
            if (STATUS_FAILED.equals(run.getStatus()) || StringUtils.hasText(run.getErrorCode())) {
                data.add(run);
            }
        }
        return data;
    }

    private List<LitemallAgentRagRun> filterPendingReviews(List<LitemallAgentRagRun> runs) {
        List<LitemallAgentRagRun> data = new ArrayList<LitemallAgentRagRun>();
        for (LitemallAgentRagRun run : runs) {
            if (STATUS_REVIEW_REQUIRED.equals(run.getStatus()) || Boolean.TRUE.equals(run.getRequiresHumanReview())) {
                data.add(run);
            }
        }
        return data;
    }

    private long countStatus(List<LitemallAgentRagRun> runs, String status) {
        long count = 0;
        for (LitemallAgentRagRun run : runs) {
            if (status.equals(run.getStatus())) {
                count++;
            }
        }
        return count;
    }

    private long countRisk(List<LitemallAgentRagRun> runs, String risk) {
        long count = 0;
        for (LitemallAgentRagRun run : runs) {
            if (risk.equals(run.getRiskLevel())) {
                count++;
            }
        }
        return count;
    }

    private long countReviewRequired(List<LitemallAgentRagRun> runs) {
        long count = 0;
        for (LitemallAgentRagRun run : runs) {
            if (STATUS_REVIEW_REQUIRED.equals(run.getStatus()) || Boolean.TRUE.equals(run.getRequiresHumanReview())) {
                count++;
            }
        }
        return count;
    }

    private long countFallback(List<LitemallAgentRagRun> runs) {
        long count = 0;
        for (LitemallAgentRagRun run : runs) {
            if (Boolean.TRUE.equals(run.getFallbackUsed())) {
                count++;
            }
        }
        return count;
    }

    private long countReplay(List<LitemallAgentRagRun> runs) {
        long count = 0;
        for (LitemallAgentRagRun run : runs) {
            if (run.getReplayOfRunId() != null) {
                count++;
            }
        }
        return count;
    }

    private String previousAuditHash(String tenantId) {
        if (auditChainService == null) {
            return null;
        }
        LitemallAgentRagAuditChain chain = auditChainService.findByTenantForUpdate(tenantId);
        return chain == null ? null : chain.getLastAuditHash();
    }

    private void updateAuditChain(LitemallAgentRagRun run) {
        if (auditChainService == null) {
            return;
        }
        LitemallAgentRagAuditChain chain = auditChainService.findByTenantForUpdate(run.getTenantId());
        LocalDateTime now = LocalDateTime.now();
        if (chain == null) {
            chain = new LitemallAgentRagAuditChain();
            chain.setTenantId(run.getTenantId());
            chain.setLastRunId(run.getId());
            chain.setLastAuditHash(run.getAuditHash());
            chain.setChainVersion(1L);
            chain.setCreatedAt(now);
            chain.setUpdatedAt(now);
            auditChainService.create(chain);
        } else {
            chain.setLastRunId(run.getId());
            chain.setLastAuditHash(run.getAuditHash());
            chain.setChainVersion(chain.getChainVersion() == null ? 1L : chain.getChainVersion() + 1);
            chain.setUpdatedAt(now);
            auditChainService.update(chain);
        }
    }

    private long averageDuration(List<LitemallAgentRagRun> runs) {
        long count = 0;
        long total = 0;
        for (LitemallAgentRagRun run : runs) {
            if (run.getDurationMs() != null) {
                count++;
                total += run.getDurationMs();
            }
        }
        return count == 0 ? 0 : total / count;
    }

    private long percentileDuration(List<LitemallAgentRagRun> runs, double percentile) {
        List<Long> values = new ArrayList<Long>();
        for (LitemallAgentRagRun run : runs) {
            if (run.getDurationMs() != null) {
                values.add(run.getDurationMs());
            }
        }
        if (values.isEmpty()) {
            return 0;
        }
        Collections.sort(values);
        int index = (int) Math.ceil(values.size() * percentile) - 1;
        return values.get(Math.max(0, Math.min(index, values.size() - 1)));
    }

    private List<Map<String, Object>> distribution(List<LitemallAgentRagRun> runs, String type) {
        Map<String, Long> counts = new LinkedHashMap<String, Long>();
        for (LitemallAgentRagRun run : runs) {
            String key;
            if ("status".equals(type)) {
                key = value(run.getStatus());
            } else if ("risk".equals(type)) {
                key = value(run.getRiskLevel());
            } else if ("provider".equals(type)) {
                key = value(run.getEffectiveProviderImpl());
            } else {
                key = Boolean.TRUE.equals(run.getFallbackUsed()) ? "fallback" : "normal";
            }
            if (key.length() == 0) {
                key = "unknown";
            }
            counts.put(key, counts.containsKey(key) ? counts.get(key) + 1 : 1);
        }
        List<Map<String, Object>> data = new ArrayList<Map<String, Object>>();
        for (Map.Entry<String, Long> entry : counts.entrySet()) {
            Map<String, Object> item = new LinkedHashMap<String, Object>();
            item.put("name", entry.getKey());
            item.put("value", entry.getValue());
            data.add(item);
        }
        return data;
    }

    private Long toLong(Object value) {
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        return value == null ? null : Long.valueOf(String.valueOf(value));
    }

    private Integer toInteger(Object value) {
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        return value == null ? null : Integer.valueOf(String.valueOf(value));
    }

    private long safeLong(Long value) {
        return value == null ? 0L : value;
    }

    private String decimalDelta(LitemallAgentRagRun base, LitemallAgentRagRun other) {
        BigDecimal baseValue = base.getConfidence() == null ? BigDecimal.ZERO : base.getConfidence();
        BigDecimal otherValue = other.getConfidence() == null ? BigDecimal.ZERO : other.getConfidence();
        return otherValue.subtract(baseValue).toPlainString();
    }

    LitemallAgentRagEvidence buildEvidence(LitemallAgentRagRun run, AgentRagAnalyzeResponse response, LocalDateTime createdAt) {
        String evidenceId = response.getAudit() == null || !StringUtils.hasText(response.getAudit().getEvidenceId())
                ? "ev-" + run.getRequestId()
                : response.getAudit().getEvidenceId();
        Map<String, Object> bundle = new LinkedHashMap<String, Object>();
        bundle.put("requestId", run.getRequestId());
        bundle.put("tenantId", run.getTenantId());
        bundle.put("subjectType", run.getSubjectType());
        bundle.put("subjectId", run.getSubjectId());
        bundle.put("decision", sanitize(objectMapper.convertValue(response.getDecision(), Map.class)));
        bundle.put("analysis", sanitize(objectMapper.convertValue(response.getAnalysis(), Map.class)));
        bundle.put("retrieval", sanitize(objectMapper.convertValue(response.getRetrieval(), Map.class)));
        bundle.put("runtime", sanitize(objectMapper.convertValue(response.getRuntime(), Map.class)));
        bundle.put("audit", sanitize(objectMapper.convertValue(response.getAudit(), Map.class)));

        String fullJson = writeJson(bundle);
        String boundedJson = boundJson(fullJson, config.getMaxEvidenceBytes());
        LitemallAgentRagEvidence evidence = new LitemallAgentRagEvidence();
        evidence.setEvidenceId(evidenceId);
        evidence.setRunId(run.getId());
        evidence.setRequestId(run.getRequestId());
        evidence.setTenantId(run.getTenantId());
        evidence.setBoundedJson(boundedJson);
        evidence.setBundleHash(sha256(boundedJson));
        evidence.setCitationCount(citationCount(response));
        evidence.setPayloadSizeBytes(boundedJson.getBytes(StandardCharsets.UTF_8).length);
        evidence.setCreatedAt(createdAt);
        return evidence;
    }

    Object sanitize(Object value) {
        if (value instanceof Map) {
            Map<?, ?> input = (Map<?, ?>) value;
            Map<String, Object> output = new LinkedHashMap<String, Object>();
            for (Map.Entry<?, ?> entry : input.entrySet()) {
                String key = String.valueOf(entry.getKey());
                if (isSensitiveKey(key)) {
                    output.put(key, "[redacted]");
                } else {
                    output.put(key, sanitize(entry.getValue()));
                }
            }
            return output;
        }
        if (value instanceof List) {
            List<?> input = (List<?>) value;
            List<Object> output = new ArrayList<Object>();
            for (Object item : input) {
                output.add(sanitize(item));
            }
            return output;
        }
        if (value instanceof String) {
            return redactPath((String) value);
        }
        return value;
    }

    String boundJson(String json, int maxBytes) {
        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= maxBytes) {
            return json;
        }
        int prefixBytes = Math.max(0, maxBytes - 256);
        String prefix = new String(bytes, 0, prefixBytes, StandardCharsets.UTF_8);
        Map<String, Object> bounded = new LinkedHashMap<String, Object>();
        bounded.put("truncated", true);
        bounded.put("originalSha256", sha256(json));
        bounded.put("originalBytes", bytes.length);
        bounded.put("payloadPrefix", prefix);
        return writeJson(bounded);
    }

    private LitemallAgentRagRun newRun(AgentRagAnalyzeRequest request, String idempotencyKey,
                                       Long parentRunId, Long replayOfRunId, LocalDateTime startedAt) {
        LitemallAgentRagRun run = new LitemallAgentRagRun();
        run.setRequestId(request.getRequestId());
        run.setIdempotencyKey(idempotencyKey);
        run.setTenantId(request.getTenantId());
        run.setSubjectType(request.getSubjectType());
        run.setSubjectId(request.getSubjectId());
        run.setParentRunId(parentRunId);
        run.setReplayOfRunId(replayOfRunId);
        run.setStatus(STATUS_RUNNING);
        run.setRuntimeMode(request.getRuntimeMode());
        run.setRequestedRetrievalMode(request.getRetrieval() == null ? null : request.getRetrieval().getRequestedMode());
        run.setSchemaVersion(request.getSchemaVersion());
        run.setStartedAt(startedAt);
        run.setCreatedAt(startedAt);
        run.setUpdatedAt(startedAt);
        run.setRequiresHumanReview(false);
        run.setFallbackUsed(false);
        run.setRetryCount(0);
        run.setDeleted(false);
        return run;
    }

    private void completeRun(LitemallAgentRagRun run, AgentRagAnalyzeResponse response,
                             LitemallAgentRagEvidence evidence, LocalDateTime startedAt, LocalDateTime finishedAt) {
        AgentRagDecision decision = response.getDecision();
        AgentRagAnalysis analysis = response.getAnalysis();
        AgentRagRuntime runtime = response.getRuntime();
        AgentRagRetrievalResult retrieval = response.getRetrieval();
        run.setRiskLevel(decision == null ? null : decision.getRiskLevel());
        run.setRiskTypesJson(writeJson(decision == null ? new ArrayList<String>() : decision.getRiskTypes()));
        run.setAction(decision == null ? null : decision.getAction());
        run.setRequiresHumanReview((decision != null && Boolean.TRUE.equals(decision.getRequiresHumanReview())) ||
                (runtime != null && Boolean.TRUE.equals(runtime.getRequiresHumanReview())));
        run.setConfidence(analysis == null ? null : analysis.getConfidence());
        if (runtime != null) {
            run.setRuntimeMode(runtime.getEngineType());
            run.setTargetMode(runtime.getTargetMode());
            run.setRequestedProviderImpl(firstText(runtime.getRequestedAnalysisProvider(), runtime.getRequestedLlmProvider(), runtime.getRequestedProviderImpl()));
            run.setEffectiveProviderImpl(firstText(runtime.getEffectiveAnalysisProvider(), runtime.getEffectiveLlmProvider(), runtime.getEffectiveProviderImpl()));
            run.setEffectiveRetrievalMode(firstText(retrieval == null ? null : retrieval.getEffectiveRetrievalMode(), runtime.getEffectiveRetrievalMode()));
            run.setIndexVersion(firstText(retrieval == null ? null : retrieval.getIndexVersion(), runtime.getIndexVersion()));
            run.setFallbackUsed(Boolean.TRUE.equals(runtime.getFallbackUsed()) ||
                    Boolean.TRUE.equals(runtime.getLlmFallbackUsed()) ||
                    (retrieval != null && (Boolean.TRUE.equals(retrieval.getDenseFallbackUsed()) || Boolean.TRUE.equals(retrieval.getRerankerFallbackUsed()))));
            run.setFallbackReason(firstText(runtime.getFallbackReason(), runtime.getLlmFallbackReason(),
                    retrieval == null ? null : retrieval.getDenseFallbackReason(),
                    retrieval == null ? null : retrieval.getRerankerFallbackReason()));
            run.setSchemaVersion(runtime.getSchemaVersion() == null ? run.getSchemaVersion() : runtime.getSchemaVersion());
            run.setAnalyzerVersion(runtime.getAnalyzerVersion());
        } else if (retrieval != null) {
            run.setEffectiveRetrievalMode(retrieval.getEffectiveRetrievalMode());
            run.setIndexVersion(retrieval.getIndexVersion());
        }
        run.setEvidenceId(evidence.getEvidenceId());
        run.setStatus(statusFor(run));
        run.setFinishedAt(finishedAt);
        run.setDurationMs(Duration.between(startedAt, finishedAt).toMillis());
        run.setUpdatedAt(finishedAt);
    }

    private void failRun(LitemallAgentRagRun run, RuntimeException ex, LocalDateTime startedAt, LocalDateTime finishedAt) {
        run.setStatus(STATUS_FAILED);
        run.setRequiresHumanReview(true);
        run.setErrorCode(ex instanceof AgentRagClientException ? ((AgentRagClientException) ex).getErrorCode() : ex.getClass().getSimpleName());
        run.setErrorMessage(trimToLength(ex.getMessage(), 512));
        run.setFinishedAt(finishedAt);
        run.setDurationMs(Duration.between(startedAt, finishedAt).toMillis());
        run.setUpdatedAt(finishedAt);
    }

    private String statusFor(LitemallAgentRagRun run) {
        if (Boolean.TRUE.equals(run.getFallbackUsed())) {
            return STATUS_RULE_FALLBACK;
        }
        if (Boolean.TRUE.equals(run.getRequiresHumanReview())) {
            return STATUS_REVIEW_REQUIRED;
        }
        return STATUS_SUCCESS;
    }

    private String safeRequestRuntimeMode(String runtimeMode) {
        if ("local-model".equals(runtimeMode) || "model-only".equals(runtimeMode) ||
                "rule-fallback".equals(runtimeMode) || "explicit-failure".equals(runtimeMode)) {
            return runtimeMode;
        }
        return "local-model";
    }

    private LitemallAgentRagRun requireRun(Long id) {
        if (id == null) {
            throw new AgentRagClientException("AGENT_RAG_RUN_ID_REQUIRED", "runId is required.");
        }
        LitemallAgentRagRun run = runService.findById(id);
        if (run == null) {
            throw new AgentRagClientException("AGENT_RAG_RUN_NOT_FOUND", "Run does not exist.");
        }
        return run;
    }

    private void validateOverride(AgentRagOverrideRequest request) {
        if (request == null || request.getRunId() == null || request.getOperatorId() == null) {
            throw new AgentRagClientException("AGENT_RAG_OVERRIDE_INVALID", "runId and operatorId are required.");
        }
        if (!RISK_LEVELS.contains(normalizeEnum(request.getNewRiskLevel()))) {
            throw new AgentRagClientException("AGENT_RAG_OVERRIDE_RISK_INVALID", "Risk level is invalid.");
        }
        if (!ACTIONS.contains(normalizeEnum(request.getNewAction()))) {
            throw new AgentRagClientException("AGENT_RAG_OVERRIDE_ACTION_INVALID", "Action is invalid.");
        }
        if (!StringUtils.hasText(request.getReason()) || request.getReason().trim().length() < 8) {
            throw new AgentRagClientException("AGENT_RAG_OVERRIDE_REASON_REQUIRED", "Override reason must be explicit.");
        }
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new AgentRagProtocolException("AGENT_RAG_JSON_WRITE_FAILED", "Failed to serialize Agent-RAG evidence.");
        }
    }

    private int citationCount(AgentRagAnalyzeResponse response) {
        if (response.getRetrieval() == null || response.getRetrieval().getCitations() == null) {
            return 0;
        }
        return response.getRetrieval().getCitations().size();
    }

    private boolean isSensitiveKey(String key) {
        String lower = key.toLowerCase(Locale.ROOT);
        return lower.contains("token") || lower.contains("secret") || lower.contains("api_key") ||
                lower.contains("authorization") || lower.contains("password") || lower.contains("prompt") ||
                lower.contains("model_path") || lower.endsWith("path");
    }

    private String redactPath(String value) {
        return UNIX_PATH.matcher(WINDOWS_PATH.matcher(value).replaceAll("[redacted-path]")).replaceAll("[redacted-path]");
    }

    private String normalizeEnum(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private String trimToLength(String value, int maxLength) {
        if (value == null) {
            return null;
        }
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }

    private String firstText(String... values) {
        if (values == null) {
            return null;
        }
        for (String item : values) {
            if (StringUtils.hasText(item)) {
                return item;
            }
        }
        return null;
    }

    private String value(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String sha256(String raw) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(raw.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder();
            for (byte b : bytes) {
                builder.append(String.format("%02x", b));
            }
            return builder.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new AgentRagClientException("AGENT_RAG_SHA256_UNAVAILABLE", "SHA-256 is unavailable.");
        }
    }
}
