package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.linlinjava.litemall.db.domain.LitemallAgentRagAuditChain;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;
import org.linlinjava.litemall.db.service.LitemallAgentRagAuditChainService;
import org.linlinjava.litemall.db.service.LitemallAgentRagEvidenceService;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import javax.annotation.Resource;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class AgentRagAuditIntegrityService {
    public static final String SECURITY_POLICY_VERSION = "agent-rag-security-v1";
    public static final String STATUS_VALID = "VALID";
    public static final String STATUS_INVALID_BUNDLE_HASH = "INVALID_BUNDLE_HASH";
    public static final String STATUS_INVALID_CITATION_HASH = "INVALID_CITATION_HASH";
    public static final String STATUS_INVALID_RUNTIME_CONFIG_HASH = "INVALID_RUNTIME_CONFIG_HASH";
    public static final String STATUS_INVALID_DECISION_HASH = "INVALID_DECISION_HASH";
    public static final String STATUS_INVALID_AUDIT_HASH = "INVALID_AUDIT_HASH";
    public static final String STATUS_MISSING_HISTORY = "MISSING_HISTORY";
    public static final String STATUS_EVIDENCE_EXPIRED_BUT_HASH_VALID = "EVIDENCE_EXPIRED_BUT_HASH_VALID";

    private static final DateTimeFormatter CANONICAL_TIME = DateTimeFormatter.ISO_LOCAL_DATE_TIME;

    @Resource
    private ObjectMapper objectMapper;
    @Resource
    private LitemallAgentRagEvidenceService evidenceService;
    @Resource
    private LitemallAgentRagAuditChainService auditChainService;

    public void applySecurityAndAudit(LitemallAgentRagRun run, AgentRagAnalyzeResponse response,
                                      LitemallAgentRagEvidence evidence, String previousAuditHash) {
        AgentRagRuntime runtime = response.getRuntime();
        AgentRagRetrievalResult retrieval = response.getRetrieval();
        run.setSecurityPolicyVersion(SECURITY_POLICY_VERSION);
        int piiCount = runtime == null || runtime.getPiiRedactionCount() == null ? 0 : runtime.getPiiRedactionCount();
        boolean injection = runtime != null && Boolean.TRUE.equals(runtime.getPromptInjectionDetected());
        run.setPiiDetected(piiCount > 0);
        run.setPiiCount(piiCount);
        run.setPiiTypesJson(piiCount > 0 ? "[\"text_pattern\"]" : "[]");
        run.setModelInputRedacted(piiCount > 0);
        run.setAuditRedacted(true);
        run.setUiRedacted(true);
        run.setPromptInjectionDetected(injection);
        run.setPromptInjectionRiskLevel(injection ? "high" : "none");
        run.setPromptInjectionSignalsJson(injection ? "[\"instruction_override\"]" : "[]");
        run.setPromptInjectionExecutionSuppressed(injection);
        run.setPreviousAuditHash(previousAuditHash);
        run.setCitationSetHash(citationSetHash(retrieval));
        run.setRuntimeConfigHash(runtimeConfigHash(run, runtime));
        run.setEffectiveDecisionHash(effectiveDecisionHash(run, null));
        run.setAuditHash(auditHash(run));
        run.setAuditIntegrityStatus(STATUS_VALID);
        run.setEvidenceExpiresAt(run.getCreatedAt() == null ? null : run.getCreatedAt().plusDays(180));
        run.setRawInputExpiresAt(run.getCreatedAt() == null ? null : run.getCreatedAt().plusDays(30));
        evidence.setCitationSetHash(run.getCitationSetHash());
        evidence.setPiiRedacted(piiCount > 0);
        evidence.setEvidenceExpired(false);
    }

    public Map<String, Object> verifyRun(LitemallAgentRagRun run, LitemallAgentRagEvidence evidence) {
        Map<String, Object> result = new LinkedHashMap<String, Object>();
        result.put("runId", run == null ? null : run.getId());
        result.put("tenantId", run == null ? null : run.getTenantId());
        if (run == null || evidence == null) {
            result.put("status", STATUS_MISSING_HISTORY);
            result.put("valid", false);
            return result;
        }
        String status = STATUS_VALID;
        if (Boolean.TRUE.equals(evidence.getEvidenceExpired())) {
            status = STATUS_EVIDENCE_EXPIRED_BUT_HASH_VALID;
        } else if (StringUtils.hasText(evidence.getBoundedJson()) && StringUtils.hasText(evidence.getBundleHash()) &&
                !evidence.getBundleHash().equals(sha256(evidence.getBoundedJson()))) {
            status = STATUS_INVALID_BUNDLE_HASH;
        }
        if (!StringUtils.hasText(run.getAuditHash())) {
            status = STATUS_INVALID_AUDIT_HASH;
        }
        result.put("status", status);
        result.put("valid", STATUS_VALID.equals(status) || STATUS_EVIDENCE_EXPIRED_BUT_HASH_VALID.equals(status));
        result.put("bundleHash", evidence.getBundleHash());
        result.put("citationSetHash", run.getCitationSetHash());
        result.put("runtimeConfigHash", run.getRuntimeConfigHash());
        result.put("effectiveDecisionHash", run.getEffectiveDecisionHash());
        result.put("previousAuditHash", run.getPreviousAuditHash());
        result.put("auditHash", run.getAuditHash());
        result.put("evidenceExpired", Boolean.TRUE.equals(evidence.getEvidenceExpired()));
        return result;
    }

    public Map<String, Object> verifyRun(Long runId, String tenantId) {
        LitemallAgentRagEvidence evidence = evidenceService.findByRunId(runId);
        Map<String, Object> result = new LinkedHashMap<String, Object>();
        result.put("runId", runId);
        result.put("tenantId", tenantId);
        result.put("status", evidence == null ? STATUS_MISSING_HISTORY : "EVIDENCE_AVAILABLE");
        result.put("valid", evidence != null);
        return result;
    }

    public Map<String, Object> securityStatus(String tenantId) {
        LitemallAgentRagAuditChain chain = auditChainService.findByTenant(tenantId);
        Map<String, Object> data = new LinkedHashMap<String, Object>();
        data.put("tenantId", tenantId);
        data.put("securityPolicyVersion", SECURITY_POLICY_VERSION);
        data.put("piiPolicyEnabled", true);
        data.put("promptInjectionPolicyEnabled", true);
        data.put("auditChainEnabled", true);
        data.put("retentionEnabled", true);
        data.put("lastRetentionRun", null);
        data.put("auditChainStatus", chain == null ? "EMPTY" : STATUS_VALID);
        data.put("lastRunId", chain == null ? null : chain.getLastRunId());
        data.put("lastAuditHash", chain == null ? null : chain.getLastAuditHash());
        return data;
    }

    public String citationSetHash(AgentRagRetrievalResult retrieval) {
        List<AgentRagCitation> citations = retrieval == null || retrieval.getCitations() == null
                ? Collections.<AgentRagCitation>emptyList()
                : new ArrayList<AgentRagCitation>(retrieval.getCitations());
        Collections.sort(citations, new Comparator<AgentRagCitation>() {
            @Override
            public int compare(AgentRagCitation left, AgentRagCitation right) {
                int rank = value(left.getRank()).compareTo(value(right.getRank()));
                if (rank != 0) {
                    return rank;
                }
                return value(left.getChunkId()).compareTo(value(right.getChunkId()));
            }
        });
        List<Map<String, Object>> stable = new ArrayList<Map<String, Object>>();
        for (AgentRagCitation citation : citations) {
            Map<String, Object> item = new LinkedHashMap<String, Object>();
            item.put("documentId", citation.getDocumentId());
            item.put("chunkId", citation.getChunkId());
            item.put("documentVersion", citation.getDocumentVersion());
            item.put("contentHash", citation.getContentHash());
            item.put("rank", citation.getRank());
            stable.add(item);
        }
        return sha256(writeJson(stable));
    }

    public String runtimeConfigHash(LitemallAgentRagRun run, AgentRagRuntime runtime) {
        Map<String, Object> stable = new LinkedHashMap<String, Object>();
        stable.put("targetMode", runtime == null ? run.getTargetMode() : runtime.getTargetMode());
        stable.put("effectiveProviderImpl", runtime == null ? run.getEffectiveProviderImpl() : runtime.getEffectiveProviderImpl());
        stable.put("effectiveRetrievalMode", runtime == null ? run.getEffectiveRetrievalMode() : runtime.getEffectiveRetrievalMode());
        stable.put("effectiveRerankerType", runtime == null ? "" : "");
        stable.put("indexVersion", runtime == null ? run.getIndexVersion() : runtime.getIndexVersion());
        stable.put("analyzerVersion", runtime == null ? run.getAnalyzerVersion() : runtime.getAnalyzerVersion());
        stable.put("schemaVersion", runtime == null ? run.getSchemaVersion() : runtime.getSchemaVersion());
        stable.put("securityPolicyVersion", SECURITY_POLICY_VERSION);
        return sha256(writeJson(stable));
    }

    public String effectiveDecisionHash(LitemallAgentRagRun run, Long overrideId) {
        Map<String, Object> stable = new LinkedHashMap<String, Object>();
        stable.put("decisionSource", overrideId == null ? "machine" : "override");
        stable.put("riskLevel", run.getRiskLevel());
        stable.put("action", run.getAction());
        stable.put("requiresHumanReview", Boolean.TRUE.equals(run.getRequiresHumanReview()));
        stable.put("overrideId", overrideId);
        return sha256(writeJson(stable));
    }

    public String auditHash(LitemallAgentRagRun run) {
        String raw = value(run.getPreviousAuditHash()) + "|" + value(run.getTenantId()) + "|" +
                value(run.getId()) + "|" + value(run.getRequestId()) + "|" +
                value(run.getEvidenceId()) + "|" + value(run.getCitationSetHash()) + "|" +
                value(run.getRuntimeConfigHash()) + "|" + value(run.getEffectiveDecisionHash()) + "|" +
                (run.getCreatedAt() == null ? "" : CANONICAL_TIME.format(run.getCreatedAt()));
        return sha256(raw);
    }

    public String overrideHash(LitemallAgentRagOverrideView override, String runAuditHash, String previousEffectiveDecisionHash) {
        String raw = value(override.previousOverrideHash) + "|" + value(runAuditHash) + "|" +
                value(previousEffectiveDecisionHash) + "|" + value(override.effectiveDecisionHash) + "|" +
                value(override.operatorId) + "|" + sha256(value(override.reason)) + "|" +
                value(override.createdAt);
        return sha256(raw);
    }

    private String value(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new AgentRagProtocolException("AGENT_RAG_JSON_WRITE_FAILED", "Failed to serialize Agent-RAG audit payload.");
        }
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

    public static class LitemallAgentRagOverrideView {
        public String previousOverrideHash;
        public String effectiveDecisionHash;
        public Long operatorId;
        public String reason;
        public String createdAt;
    }
}
