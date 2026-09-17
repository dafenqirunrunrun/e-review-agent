package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Before;
import org.junit.Test;
import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.linlinjava.litemall.db.domain.LitemallAgentRagOverride;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;
import org.linlinjava.litemall.db.service.LitemallAgentRagEvidenceService;
import org.linlinjava.litemall.db.service.LitemallAgentRagOverrideService;
import org.linlinjava.litemall.db.service.LitemallAgentRagRunService;

import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.*;

public class AgentRagRetentionExportServiceTest {
    private AgentRagRetentionExportService service;
    private FakeEvidenceService evidenceService;
    private FakeRunService runService;
    private FakeOverrideService overrideService;
    private FakeAuditIntegrityService auditIntegrityService;

    @Before
    public void setUp() throws Exception {
        service = new AgentRagRetentionExportService();
        AgentRagConfig config = new AgentRagConfig();
        config.setSingleTenantId("tenant-a");
        evidenceService = new FakeEvidenceService();
        runService = new FakeRunService();
        overrideService = new FakeOverrideService();
        auditIntegrityService = new FakeAuditIntegrityService();
        set("tenantResolver", new AgentRagTenantResolver(config));
        set("evidenceService", evidenceService);
        set("runService", runService);
        set("overrideService", overrideService);
        set("auditIntegrityService", auditIntegrityService);
        set("objectMapper", new ObjectMapper());
    }

    @Test
    public void secureExportExcludesRawEvidencePayload() {
        LitemallAgentRagRun run = run("tenant-a");
        LitemallAgentRagEvidence evidence = evidence(run, "{\"requestId\":\"req-1\",\"subjectType\":\"review\",\"subjectId\":\"42\",\"analysis\":{\"summary\":\"safe\"}}");
        LitemallAgentRagOverride override = new LitemallAgentRagOverride();
        override.setId(5L);
        override.setRunId(run.getId());
        override.setReason("manual judgement should not be exported verbatim");
        runService.run = run;
        evidenceService.evidence = evidence;
        overrideService.overrides = Collections.singletonList(override);

        Map<String, Object> exported = service.secureExport(run.getId());

        assertEquals(Boolean.FALSE, exported.get("rawEvidenceExported"));
        assertFalse(exported.toString().contains("boundedJson"));
        assertFalse(exported.toString().contains("manual judgement should not be exported verbatim"));
        assertTrue(exported.toString().contains("RAW_EVIDENCE_NOT_EXPORTED"));
        assertTrue(exported.toString().contains("requestId=req-1"));
    }

    @Test
    public void executeRetentionReplacesPayloadWithExpiryMarker() {
        LitemallAgentRagRun run = run("tenant-a");
        LitemallAgentRagEvidence evidence = evidence(run, "{\"raw\":\"payload\"}");
        evidenceService.candidates = Collections.singletonList(evidence);

        Map<String, Object> result = service.executeRetention(null);

        assertEquals(Boolean.FALSE, result.get("dryRun"));
        assertEquals(1, result.get("expiredEvidenceCount"));
        assertEquals(0, result.get("businessRowsDeleted"));
        assertFalse(evidenceService.lastBoundedJson.contains("{\"raw\":\"payload\"}"));
        assertTrue(evidenceService.lastBoundedJson.contains("rawPayloadRemoved"));
    }

    @Test
    public void rejectsCrossTenantExport() {
        LitemallAgentRagRun run = run("other-tenant");
        runService.run = run;

        try {
            service.secureExport(run.getId());
            fail("Expected tenant mismatch");
        } catch (AgentRagClientException e) {
            assertEquals("AGENT_RAG_TENANT_MISMATCH", e.getErrorCode());
        }
    }

    private LitemallAgentRagRun run(String tenantId) {
        LitemallAgentRagRun run = new LitemallAgentRagRun();
        run.setId(91L);
        run.setTenantId(tenantId);
        run.setRequestId("req-1");
        run.setSubjectType("review");
        run.setSubjectId("42");
        run.setStatus("SUCCESS");
        run.setRiskLevel("high");
        run.setAction("manual_review");
        run.setConfidence(new BigDecimal("0.91"));
        run.setRequiresHumanReview(true);
        run.setEvidenceId("ev-1");
        run.setAuditHash("audit-hash");
        run.setEvidenceExpiresAt(LocalDateTime.now().minusDays(1));
        return run;
    }

    private LitemallAgentRagEvidence evidence(LitemallAgentRagRun run, String boundedJson) {
        LitemallAgentRagEvidence evidence = new LitemallAgentRagEvidence();
        evidence.setRunId(run.getId());
        evidence.setTenantId(run.getTenantId());
        evidence.setRequestId(run.getRequestId());
        evidence.setEvidenceId(run.getEvidenceId());
        evidence.setBundleHash("bundle-hash");
        evidence.setBoundedJson(boundedJson);
        evidence.setPayloadSizeBytes(boundedJson.length());
        evidence.setEvidenceExpired(false);
        evidence.setCitationCount(1);
        return evidence;
    }

    private void set(String name, Object value) throws Exception {
        Field field = AgentRagRetentionExportService.class.getDeclaredField(name);
        field.setAccessible(true);
        field.set(service, value);
    }

    private static class FakeRunService extends LitemallAgentRagRunService {
        private LitemallAgentRagRun run;

        @Override
        public LitemallAgentRagRun findById(Long id) {
            return run != null && run.getId().equals(id) ? run : null;
        }
    }

    private static class FakeEvidenceService extends LitemallAgentRagEvidenceService {
        private LitemallAgentRagEvidence evidence;
        private List<LitemallAgentRagEvidence> candidates = new ArrayList<LitemallAgentRagEvidence>();
        private String lastBoundedJson;

        @Override
        public LitemallAgentRagEvidence findByRunId(Long runId) {
            return evidence != null && evidence.getRunId().equals(runId) ? evidence : null;
        }

        @Override
        public long countExpiredCandidates(String tenantId, LocalDateTime now) {
            return candidates.size();
        }

        @Override
        public List<LitemallAgentRagEvidence> expiredCandidates(String tenantId, LocalDateTime now, Integer limit) {
            return candidates;
        }

        @Override
        public int expirePayload(String tenantId, Long runId, String boundedJson, Integer payloadSizeBytes, LocalDateTime expiredAt) {
            this.lastBoundedJson = boundedJson;
            return 1;
        }
    }

    private static class FakeOverrideService extends LitemallAgentRagOverrideService {
        private List<LitemallAgentRagOverride> overrides = new ArrayList<LitemallAgentRagOverride>();

        @Override
        public List<LitemallAgentRagOverride> listByRun(String tenantId, Long runId) {
            return overrides;
        }
    }

    private static class FakeAuditIntegrityService extends AgentRagAuditIntegrityService {
        @Override
        public Map<String, Object> verifyRun(LitemallAgentRagRun run, LitemallAgentRagEvidence evidence) {
            return Collections.<String, Object>singletonMap("status", "VALID");
        }
    }
}
