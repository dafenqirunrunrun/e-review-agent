package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Before;
import org.junit.Test;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;

import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.Assert.*;

public class AgentRagWorkflowPersistenceTest {
    private AgentRagWorkflowService service;

    @Before
    public void setUp() throws Exception {
        AgentRagConfig config = new AgentRagConfig();
        config.setSingleTenantId("tenant-a");
        config.setMaxEvidenceBytes(500);

        service = new AgentRagWorkflowService();
        set("config", config);
        set("tenantResolver", new AgentRagTenantResolver(config));
        set("objectMapper", new ObjectMapper());
    }

    @Test
    public void idempotencyKeyIsStableAndTenantScoped() {
        AgentRagAnalyzeRequest first = request("req-1", "tenant-b", "review-1");
        AgentRagAnalyzeRequest second = request("req-2", "tenant-c", "review-1");

        String firstKey = service.computeIdempotencyKey(first, null, null);
        String secondKey = service.computeIdempotencyKey(second, null, null);

        assertEquals(64, firstKey.length());
        assertEquals(firstKey, secondKey);
        first.setSubjectId("review-2");
        assertNotEquals(firstKey, service.computeIdempotencyKey(first, null, null));
    }

    @Test
    public void replayIdempotencyKeyIncludesReplayRequestId() {
        AgentRagAnalyzeRequest first = request("replay-1", "tenant-a", "review-1");
        AgentRagAnalyzeRequest second = request("replay-2", "tenant-a", "review-1");
        assertNotEquals(
                service.computeIdempotencyKey(first, null, 99L),
                service.computeIdempotencyKey(second, null, 99L));
    }

    @Test
    public void evidenceBundleRedactsSecretsAndLocalPaths() {
        LitemallAgentRagRun run = run("req-1");
        AgentRagAnalyzeResponse response = response();
        response.getRuntime().setModelName("D:\\EReviewAgent\\models\\private-model");
        response.getAnalysis().setSummary("loaded from C:\\Users\\demo\\secret.txt");
        Map<String, Object> audit = new LinkedHashMap<String, Object>();
        audit.put("apiToken", "abc");
        audit.put("promptTemplate", "hidden prompt");

        Object sanitized = service.sanitize(audit);
        String sanitizedJson = new ObjectMapper().valueToTree(sanitized).toString();
        assertTrue(sanitizedJson.contains("[redacted]"));
        assertFalse(sanitizedJson.contains("hidden prompt"));

        LitemallAgentRagEvidence evidence = service.buildEvidence(run, response, LocalDateTime.now());
        assertEquals("ev-1", evidence.getEvidenceId());
        assertEquals(Integer.valueOf(1), evidence.getCitationCount());
        assertFalse(evidence.getBoundedJson().contains("C:\\Users"));
        assertFalse(evidence.getBoundedJson().contains("D:\\EReviewAgent"));
        assertEquals(64, evidence.getBundleHash().length());
    }

    @Test
    public void evidenceBundleRemainsValidJsonWhenBounded() throws Exception {
        LitemallAgentRagRun run = run("req-2");
        AgentRagAnalyzeResponse response = response();
        StringBuilder large = new StringBuilder();
        for (int i = 0; i < 3000; i++) {
            large.append('x');
        }
        response.getAnalysis().setSummary(large.toString());

        LitemallAgentRagEvidence evidence = service.buildEvidence(run, response, LocalDateTime.now());
        Map parsed = new ObjectMapper().readValue(evidence.getBoundedJson(), Map.class);
        assertEquals(Boolean.TRUE, parsed.get("truncated"));
        assertTrue(((Number) parsed.get("originalBytes")).intValue() > evidence.getPayloadSizeBytes());
    }

    @Test
    public void completeRunPersistsRealModelProviderAndRetrievalEvidence() throws Exception {
        LitemallAgentRagRun run = run("req-3");
        AgentRagAnalyzeResponse response = response();
        response.getRuntime().setRequestedAnalysisProvider("local_qwen3_transformers");
        response.getRuntime().setEffectiveAnalysisProvider("local_qwen3_transformers");
        response.getRuntime().setLlmFallbackUsed(false);
        response.getRuntime().setRequiresHumanReview(true);
        response.getRetrieval().setEffectiveRetrievalMode("hybrid-real");
        response.getRetrieval().setIndexVersion("idx-v22");
        response.getRetrieval().setDenseFallbackUsed(false);
        response.getRetrieval().setRerankerFallbackUsed(false);
        LitemallAgentRagEvidence evidence = new LitemallAgentRagEvidence();
        evidence.setEvidenceId("ev-3");
        LocalDateTime started = LocalDateTime.now().minusSeconds(1);
        LocalDateTime finished = LocalDateTime.now();

        java.lang.reflect.Method method = AgentRagWorkflowService.class.getDeclaredMethod(
                "completeRun", LitemallAgentRagRun.class, AgentRagAnalyzeResponse.class,
                LitemallAgentRagEvidence.class, LocalDateTime.class, LocalDateTime.class);
        method.setAccessible(true);
        method.invoke(service, run, response, evidence, started, finished);

        assertEquals("local_qwen3_transformers", run.getRequestedProviderImpl());
        assertEquals("local_qwen3_transformers", run.getEffectiveProviderImpl());
        assertEquals("hybrid-real", run.getEffectiveRetrievalMode());
        assertEquals("idx-v22", run.getIndexVersion());
        assertEquals(Boolean.FALSE, run.getFallbackUsed());
        assertEquals(Boolean.TRUE, run.getRequiresHumanReview());
    }

    private AgentRagAnalyzeRequest request(String requestId, String tenantId, String subjectId) {
        AgentRagAnalyzeRequest request = new AgentRagAnalyzeRequest();
        request.setRequestId(requestId);
        request.setTenantId(tenantId);
        request.setSubjectType("review");
        request.setSubjectId(subjectId);
        request.setQuery("refund broken item");
        return request;
    }

    private LitemallAgentRagRun run(String requestId) {
        LitemallAgentRagRun run = new LitemallAgentRagRun();
        run.setId(99L);
        run.setRequestId(requestId);
        run.setTenantId("tenant-a");
        run.setSubjectType("review");
        run.setSubjectId("review-1");
        run.setSchemaVersion("2.0.0");
        return run;
    }

    private AgentRagAnalyzeResponse response() {
        AgentRagAnalyzeResponse response = new AgentRagAnalyzeResponse();
        response.setRequestId("req-1");
        response.setTenantId("tenant-a");
        response.setSubjectId("review-1");
        AgentRagDecision decision = new AgentRagDecision();
        decision.setRiskLevel("high");
        decision.setAction("escalate");
        decision.setRequiresHumanReview(true);
        response.setDecision(decision);
        AgentRagAnalysis analysis = new AgentRagAnalysis();
        analysis.setSummary("bounded summary");
        analysis.setConfidence(new BigDecimal("0.91"));
        response.setAnalysis(analysis);
        AgentRagRuntime runtime = new AgentRagRuntime();
        runtime.setEngineType("model-rag");
        runtime.setFallbackUsed(false);
        runtime.setSchemaVersion("2.0.0");
        runtime.setAnalyzerVersion("agent-rag-phase1-v1");
        response.setRuntime(runtime);
        AgentRagRetrievalResult retrieval = new AgentRagRetrievalResult();
        AgentRagCitation citation = new AgentRagCitation();
        citation.setDocumentId("doc-1");
        citation.setChunkId("chunk-1");
        citation.setTenantId("tenant-a");
        citation.setSnippet("bounded citation");
        retrieval.getCitations().add(citation);
        response.setRetrieval(retrieval);
        AgentRagAudit audit = new AgentRagAudit();
        audit.setEvidenceId("ev-1");
        response.setAudit(audit);
        return response;
    }

    private void set(String name, Object value) throws Exception {
        Field field = AgentRagWorkflowService.class.getDeclaredField(name);
        field.setAccessible(true);
        field.set(service, value);
    }
}
