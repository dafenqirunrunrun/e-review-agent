package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.linlinjava.litemall.db.domain.LitemallAgentRagOverride;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;
import org.linlinjava.litemall.db.service.LitemallAgentRagEvidenceService;
import org.linlinjava.litemall.db.service.LitemallAgentRagOverrideService;
import org.linlinjava.litemall.db.service.LitemallAgentRagRunService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class AgentRagRetentionExportService {
    private static final int DEFAULT_BATCH_LIMIT = 50;
    private static final int MAX_BATCH_LIMIT = 100;

    @Resource
    private AgentRagTenantResolver tenantResolver;
    @Resource
    private LitemallAgentRagEvidenceService evidenceService;
    @Resource
    private LitemallAgentRagRunService runService;
    @Resource
    private LitemallAgentRagOverrideService overrideService;
    @Resource
    private AgentRagAuditIntegrityService auditIntegrityService;
    @Resource
    private ObjectMapper objectMapper;

    public Map<String, Object> retentionStatus() {
        String tenantId = tenantResolver.resolveCurrentTenant();
        LocalDateTime now = LocalDateTime.now();
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("tenantId", tenantId);
        data.put("policy", "expire evidence payloads after run.evidence_expires_at");
        data.put("pendingExpiredEvidenceCount", evidenceService.countExpiredCandidates(tenantId, now));
        data.put("maxBatchLimit", MAX_BATCH_LIMIT);
        data.put("supportsPreview", true);
        data.put("supportsExecute", true);
        data.put("destructiveBusinessDelete", false);
        data.put("evaluatedAt", now);
        return data;
    }

    public Map<String, Object> previewRetention(Integer limit) {
        String tenantId = tenantResolver.resolveCurrentTenant();
        LocalDateTime now = LocalDateTime.now();
        List<LitemallAgentRagEvidence> candidates = evidenceService.expiredCandidates(tenantId, now, safeLimit(limit));
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("tenantId", tenantId);
        data.put("dryRun", true);
        data.put("pendingExpiredEvidenceCount", evidenceService.countExpiredCandidates(tenantId, now));
        data.put("candidateCount", candidates.size());
        data.put("candidates", evidenceSummaries(candidates));
        data.put("executeEndpoint", "/admin/agent-rag/security/retention/execute");
        data.put("evaluatedAt", now);
        return data;
    }

    @Transactional
    public Map<String, Object> executeRetention(Integer limit) {
        String tenantId = tenantResolver.resolveCurrentTenant();
        LocalDateTime now = LocalDateTime.now();
        List<LitemallAgentRagEvidence> candidates = evidenceService.expiredCandidates(tenantId, now, safeLimit(limit));
        int updated = 0;
        for (LitemallAgentRagEvidence evidence : candidates) {
            String marker = expiredEvidenceMarker(evidence, now);
            updated += evidenceService.expirePayload(tenantId, evidence.getRunId(), marker,
                    marker.getBytes(StandardCharsets.UTF_8).length, now);
        }
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("tenantId", tenantId);
        data.put("dryRun", false);
        data.put("candidateCount", candidates.size());
        data.put("expiredEvidenceCount", updated);
        data.put("businessRowsDeleted", 0);
        data.put("executedAt", now);
        data.put("remainingExpiredEvidenceCount", evidenceService.countExpiredCandidates(tenantId, LocalDateTime.now()));
        return data;
    }

    public Map<String, Object> secureExport(Long runId) {
        String tenantId = tenantResolver.resolveCurrentTenant();
        LitemallAgentRagRun run = runService.findById(runId);
        if (run == null) {
            throw new AgentRagClientException("AGENT_RAG_RUN_NOT_FOUND", "Agent-RAG run was not found.");
        }
        if (!tenantId.equals(run.getTenantId())) {
            throw new AgentRagClientException("AGENT_RAG_TENANT_MISMATCH", "Run tenant does not match current tenant.");
        }
        LitemallAgentRagEvidence evidence = evidenceService.findByRunId(run.getId());
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("schemaVersion", "agent-rag-secure-export-v1");
        data.put("exportedAt", LocalDateTime.now());
        data.put("rawEvidenceExported", false);
        data.put("tenantId", tenantId);
        data.put("run", runExport(run));
        data.put("evidence", evidenceExport(evidence));
        data.put("overrideHistory", overrideExport(overrideService.listByRun(tenantId, run.getId())));
        data.put("integrity", auditIntegrityService.verifyRun(run, evidence));
        data.put("boundedSummary", boundedSummary(evidence));
        List<String> boundaries = new ArrayList<String>();
        boundaries.add("RAW_EVIDENCE_NOT_EXPORTED");
        boundaries.add("BUSINESS_TABLES_NOT_EXPORTED");
        boundaries.add("MODEL_PATHS_NOT_EXPORTED");
        data.put("boundaries", boundaries);
        return data;
    }

    private int safeLimit(Integer limit) {
        if (limit == null || limit <= 0) {
            return DEFAULT_BATCH_LIMIT;
        }
        return Math.min(limit, MAX_BATCH_LIMIT);
    }

    private List<Map<String, Object>> evidenceSummaries(List<LitemallAgentRagEvidence> candidates) {
        List<Map<String, Object>> data = new ArrayList<Map<String, Object>>();
        for (LitemallAgentRagEvidence evidence : candidates) {
            Map<String, Object> item = new LinkedHashMap<String, Object>();
            item.put("runId", evidence.getRunId());
            item.put("evidenceId", evidence.getEvidenceId());
            item.put("bundleHash", evidence.getBundleHash());
            item.put("citationSetHash", evidence.getCitationSetHash());
            item.put("payloadSizeBytes", evidence.getPayloadSizeBytes());
            item.put("createdAt", evidence.getCreatedAt());
            data.add(item);
        }
        return data;
    }

    private String expiredEvidenceMarker(LitemallAgentRagEvidence evidence, LocalDateTime now) {
        Map<String, Object> marker = new LinkedHashMap<String, Object>();
        marker.put("schemaVersion", "agent-rag-expired-evidence-v1");
        marker.put("expired", true);
        marker.put("expiredAt", now.toString());
        marker.put("runId", evidence.getRunId());
        marker.put("evidenceId", evidence.getEvidenceId());
        marker.put("originalBundleHash", evidence.getBundleHash());
        marker.put("citationSetHash", evidence.getCitationSetHash());
        marker.put("rawPayloadRemoved", true);
        try {
            return objectMapper.writeValueAsString(marker);
        } catch (Exception e) {
            return "{\"schemaVersion\":\"agent-rag-expired-evidence-v1\",\"expired\":true,\"rawPayloadRemoved\":true}";
        }
    }

    private Map<String, Object> runExport(LitemallAgentRagRun run) {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("id", run.getId());
        data.put("requestId", run.getRequestId());
        data.put("subjectType", run.getSubjectType());
        data.put("subjectId", run.getSubjectId());
        data.put("status", run.getStatus());
        data.put("riskLevel", run.getRiskLevel());
        data.put("riskTypesJson", run.getRiskTypesJson());
        data.put("action", run.getAction());
        data.put("confidence", run.getConfidence());
        data.put("requiresHumanReview", run.getRequiresHumanReview());
        data.put("targetMode", run.getTargetMode());
        data.put("requestedProviderImpl", run.getRequestedProviderImpl());
        data.put("effectiveProviderImpl", run.getEffectiveProviderImpl());
        data.put("effectiveRetrievalMode", run.getEffectiveRetrievalMode());
        data.put("indexVersion", run.getIndexVersion());
        data.put("fallbackUsed", run.getFallbackUsed());
        data.put("fallbackReason", run.getFallbackReason());
        data.put("schemaVersion", run.getSchemaVersion());
        data.put("analyzerVersion", run.getAnalyzerVersion());
        data.put("securityPolicyVersion", run.getSecurityPolicyVersion());
        data.put("piiDetected", run.getPiiDetected());
        data.put("piiTypesJson", run.getPiiTypesJson());
        data.put("piiCount", run.getPiiCount());
        data.put("modelInputRedacted", run.getModelInputRedacted());
        data.put("auditRedacted", run.getAuditRedacted());
        data.put("uiRedacted", run.getUiRedacted());
        data.put("promptInjectionDetected", run.getPromptInjectionDetected());
        data.put("promptInjectionRiskLevel", run.getPromptInjectionRiskLevel());
        data.put("promptInjectionExecutionSuppressed", run.getPromptInjectionExecutionSuppressed());
        data.put("citationSetHash", run.getCitationSetHash());
        data.put("runtimeConfigHash", run.getRuntimeConfigHash());
        data.put("effectiveDecisionHash", run.getEffectiveDecisionHash());
        data.put("previousAuditHash", run.getPreviousAuditHash());
        data.put("auditHash", run.getAuditHash());
        data.put("auditIntegrityStatus", run.getAuditIntegrityStatus());
        data.put("evidenceExpiresAt", run.getEvidenceExpiresAt());
        data.put("rawInputExpiresAt", run.getRawInputExpiresAt());
        data.put("parentRunId", run.getParentRunId());
        data.put("replayOfRunId", run.getReplayOfRunId());
        data.put("createdAt", run.getCreatedAt());
        data.put("finishedAt", run.getFinishedAt());
        data.put("durationMs", run.getDurationMs());
        return data;
    }

    private Map<String, Object> evidenceExport(LitemallAgentRagEvidence evidence) {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        if (evidence == null) {
            data.put("available", false);
            return data;
        }
        data.put("available", true);
        data.put("evidenceId", evidence.getEvidenceId());
        data.put("runId", evidence.getRunId());
        data.put("requestId", evidence.getRequestId());
        data.put("bundleHash", evidence.getBundleHash());
        data.put("citationCount", evidence.getCitationCount());
        data.put("payloadSizeBytes", evidence.getPayloadSizeBytes());
        data.put("piiRedacted", evidence.getPiiRedacted());
        data.put("evidenceExpired", evidence.getEvidenceExpired());
        data.put("expiredAt", evidence.getExpiredAt());
        data.put("citationSetHash", evidence.getCitationSetHash());
        data.put("createdAt", evidence.getCreatedAt());
        return data;
    }

    private List<Map<String, Object>> overrideExport(List<LitemallAgentRagOverride> overrides) {
        List<Map<String, Object>> data = new ArrayList<Map<String, Object>>();
        if (overrides == null) {
            return data;
        }
        for (LitemallAgentRagOverride override : overrides) {
            Map<String, Object> item = new LinkedHashMap<String, Object>();
            item.put("id", override.getId());
            item.put("runId", override.getRunId());
            item.put("previousRiskLevel", override.getPreviousRiskLevel());
            item.put("newRiskLevel", override.getNewRiskLevel());
            item.put("previousAction", override.getPreviousAction());
            item.put("newAction", override.getNewAction());
            item.put("reasonLength", override.getReason() == null ? 0 : override.getReason().length());
            item.put("operatorId", override.getOperatorId());
            item.put("previousOverrideHash", override.getPreviousOverrideHash());
            item.put("overrideHash", override.getOverrideHash());
            item.put("effectiveDecisionHash", override.getEffectiveDecisionHash());
            item.put("createdAt", override.getCreatedAt());
            data.add(item);
        }
        return data;
    }

    private Map<String, Object> boundedSummary(LitemallAgentRagEvidence evidence) {
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("rawEvidenceIncluded", false);
        if (evidence == null || evidence.getBoundedJson() == null) {
            data.put("available", false);
            return data;
        }
        data.put("available", true);
        data.put("expired", Boolean.TRUE.equals(evidence.getEvidenceExpired()));
        try {
            Map<String, Object> parsed = objectMapper.readValue(evidence.getBoundedJson(), new TypeReference<Map<String, Object>>() {});
            data.put("requestId", parsed.get("requestId"));
            data.put("subjectType", parsed.get("subjectType"));
            data.put("subjectId", parsed.get("subjectId"));
            data.put("hasRetrieval", parsed.containsKey("retrieval"));
            data.put("hasAnalysis", parsed.containsKey("analysis"));
            data.put("hasRuntime", parsed.containsKey("runtime"));
            data.put("hasAudit", parsed.containsKey("audit"));
        } catch (Exception e) {
            data.put("parseable", false);
        }
        return data;
    }
}
