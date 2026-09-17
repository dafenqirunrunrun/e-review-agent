package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Before;
import org.junit.Test;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;

import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Map;

import static org.junit.Assert.*;

public class AgentRagAuditIntegrityServiceTest {
    private AgentRagAuditIntegrityService service;

    @Before
    public void setUp() throws Exception {
        service = new AgentRagAuditIntegrityService();
        set("objectMapper", new ObjectMapper());
    }

    @Test
    public void appliesSecurityMetadataAndStableHashes() {
        LitemallAgentRagRun run = run();
        AgentRagAnalyzeResponse response = response(false, 2);
        LitemallAgentRagEvidence evidence = evidence(run);

        service.applySecurityAndAudit(run, response, evidence, "prevhash");

        assertEquals(AgentRagAuditIntegrityService.SECURITY_POLICY_VERSION, run.getSecurityPolicyVersion());
        assertTrue(run.getPiiDetected());
        assertEquals(Integer.valueOf(2), run.getPiiCount());
        assertEquals("none", run.getPromptInjectionRiskLevel());
        assertEquals("prevhash", run.getPreviousAuditHash());
        assertEquals(64, run.getCitationSetHash().length());
        assertEquals(64, run.getRuntimeConfigHash().length());
        assertEquals(64, run.getEffectiveDecisionHash().length());
        assertEquals(64, run.getAuditHash().length());
        assertEquals("VALID", run.getAuditIntegrityStatus());
        assertEquals(run.getCitationSetHash(), evidence.getCitationSetHash());
        assertTrue(evidence.getPiiRedacted());
        assertFalse(evidence.getEvidenceExpired());
    }

    @Test
    public void promptInjectionSuppressesExecutionMetadata() {
        LitemallAgentRagRun run = run();
        AgentRagAnalyzeResponse response = response(true, 0);
        LitemallAgentRagEvidence evidence = evidence(run);

        service.applySecurityAndAudit(run, response, evidence, null);

        assertTrue(run.getPromptInjectionDetected());
        assertEquals("high", run.getPromptInjectionRiskLevel());
        assertTrue(run.getPromptInjectionExecutionSuppressed());
        assertEquals("[\"instruction_override\"]", run.getPromptInjectionSignalsJson());
    }

    @Test
    public void verifiesBundleHashAndDetectsTamper() {
        LitemallAgentRagRun run = run();
        LitemallAgentRagEvidence evidence = evidence(run);
        run.setAuditHash("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef");

        Map<String, Object> valid = service.verifyRun(run, evidence);
        assertEquals("VALID", valid.get("status"));
        assertEquals(Boolean.TRUE, valid.get("valid"));

        evidence.setBoundedJson("{\"changed\":true}");
        Map<String, Object> invalid = service.verifyRun(run, evidence);
        assertEquals("INVALID_BUNDLE_HASH", invalid.get("status"));
        assertEquals(Boolean.FALSE, invalid.get("valid"));
    }

    @Test
    public void overrideHashUsesPreviousHashAndReasonHash() {
        AgentRagAuditIntegrityService.LitemallAgentRagOverrideView view = new AgentRagAuditIntegrityService.LitemallAgentRagOverrideView();
        view.previousOverrideHash = "previous";
        view.effectiveDecisionHash = "decision";
        view.operatorId = 7L;
        view.reason = "explicit human correction";
        view.createdAt = "2026-07-20T00:00:00";

        String first = service.overrideHash(view, "runhash", "olddecision");
        String second = service.overrideHash(view, "runhash", "olddecision");
        view.reason = "different human correction";
        String third = service.overrideHash(view, "runhash", "olddecision");

        assertEquals(64, first.length());
        assertEquals(first, second);
        assertNotEquals(first, third);
    }

    private LitemallAgentRagRun run() {
        LitemallAgentRagRun run = new LitemallAgentRagRun();
        run.setId(88L);
        run.setRequestId("req-audit");
        run.setTenantId("tenant-a");
        run.setSubjectType("review");
        run.setSubjectId("review-1");
        run.setRiskLevel("high");
        run.setAction("manual_review");
        run.setRequiresHumanReview(true);
        run.setSchemaVersion("2.0.0");
        run.setAnalyzerVersion("agent-rag-phase1-v1");
        run.setTargetMode("enterprise-maturity-local-single-node");
        run.setEffectiveProviderImpl("hash");
        run.setEffectiveRetrievalMode("bm25-first-semantic-hybrid");
        run.setIndexVersion("fixture-index");
        run.setEvidenceId("ev-audit");
        run.setCreatedAt(LocalDateTime.of(2026, 7, 20, 0, 0));
        return run;
    }

    private LitemallAgentRagEvidence evidence(LitemallAgentRagRun run) {
        LitemallAgentRagEvidence evidence = new LitemallAgentRagEvidence();
        evidence.setRunId(run.getId());
        evidence.setTenantId(run.getTenantId());
        evidence.setEvidenceId(run.getEvidenceId());
        evidence.setBoundedJson("{\"safe\":true}");
        evidence.setBundleHash("13f513fe32a8991557ebf28941b75597641e94717c08569b7723d998c7428423");
        evidence.setEvidenceExpired(false);
        return evidence;
    }

    private AgentRagAnalyzeResponse response(boolean injection, int piiCount) {
        AgentRagAnalyzeResponse response = new AgentRagAnalyzeResponse();
        AgentRagDecision decision = new AgentRagDecision();
        decision.setRiskLevel("high");
        decision.setAction("manual_review");
        decision.setRequiresHumanReview(true);
        response.setDecision(decision);
        AgentRagAnalysis analysis = new AgentRagAnalysis();
        analysis.setConfidence(new BigDecimal("0.92"));
        analysis.setSummary("safe summary");
        response.setAnalysis(analysis);
        AgentRagRuntime runtime = new AgentRagRuntime();
        runtime.setTargetMode("enterprise-maturity-local-single-node");
        runtime.setEffectiveProviderImpl("hash");
        runtime.setEffectiveRetrievalMode("bm25-first-semantic-hybrid");
        runtime.setIndexVersion("fixture-index");
        runtime.setAnalyzerVersion("agent-rag-phase1-v1");
        runtime.setSchemaVersion("2.0.0");
        runtime.setPiiRedactionCount(piiCount);
        runtime.setPromptInjectionDetected(injection);
        runtime.setPromptInjectionAction(injection ? "manual-review" : "none");
        response.setRuntime(runtime);
        AgentRagRetrievalResult retrieval = new AgentRagRetrievalResult();
        AgentRagCitation citation = new AgentRagCitation();
        citation.setDocumentId("doc-1");
        citation.setChunkId("chunk-1");
        citation.setContentHash("abc123abc123");
        citation.setRank(1);
        retrieval.getCitations().add(citation);
        response.setRetrieval(retrieval);
        return response;
    }

    private void set(String name, Object value) throws Exception {
        Field field = AgentRagAuditIntegrityService.class.getDeclaredField(name);
        field.setAccessible(true);
        field.set(service, value);
    }
}
