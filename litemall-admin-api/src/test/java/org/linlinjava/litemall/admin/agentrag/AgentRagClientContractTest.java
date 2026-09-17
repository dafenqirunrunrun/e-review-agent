package org.linlinjava.litemall.admin.agentrag;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Before;
import org.junit.Test;
import org.linlinjava.litemall.admin.service.agentrag.*;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;

import static org.junit.Assert.*;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.ExpectedCount.twice;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

public class AgentRagClientContractTest {
    private AgentRagConfig config;
    private RestTemplate restTemplate;
    private MockRestServiceServer server;
    private RestTemplateAgentRagClient client;

    @Before
    public void setUp() {
        config = new AgentRagConfig();
        config.setBaseUrl("http://agent-rag.test");
        config.setAnalyzePath("/analyze");
        config.setHealthPath("/health");
        config.setSingleTenantId("tenant-a");
        config.setRetryBackoffMs(0);
        config.setCircuitBreakerFailureThreshold(5);
        restTemplate = new RestTemplate();
        server = MockRestServiceServer.createServer(restTemplate);
        client = new RestTemplateAgentRagClient(
                config,
                new AgentRagTenantResolver(config),
                new AgentRagCircuitBreaker(config),
                restTemplate,
                new ObjectMapper().configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false));
    }

    @Test
    public void requestAndTrustedTenantArePropagated() {
        server.expect(once(), requestTo("http://agent-rag.test/analyze"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Request-Id", "req-1"))
                .andExpect(header("X-Tenant-Id", "tenant-a"))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("\"requestId\":\"req-1\"")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("\"tenantId\":\"tenant-a\"")))
                .andRespond(withSuccess(successJson("req-1", "tenant-a", "review-1", "low", "none", "tenant-a"), MediaType.APPLICATION_JSON));

        AgentRagAnalyzeRequest request = sampleRequest();
        request.setTenantId("forged-tenant");
        AgentRagAnalyzeResponse response = client.analyze(request);
        assertEquals("tenant-a", response.getTenantId());
        server.verify();
    }

    @Test
    public void unknownResponseFieldsAreCompatible() {
        server.expect(once(), requestTo("http://agent-rag.test/analyze"))
                .andRespond(withSuccess(successJson("req-1", "tenant-a", "review-1", "low", "none", "tenant-a")
                        .replaceFirst("\\}$", ",\"futureField\":1}"), MediaType.APPLICATION_JSON));
        assertEquals("low", client.analyze(sampleRequest()).getDecision().getRiskLevel());
    }

    @Test
    public void responseRequestIdMismatchIsRejected() {
        server.expect(once(), requestTo("http://agent-rag.test/analyze"))
                .andRespond(withSuccess(successJson("other", "tenant-a", "review-1", "low", "none", "tenant-a"), MediaType.APPLICATION_JSON));
        try {
            client.analyze(sampleRequest());
            fail("expected mismatch");
        } catch (AgentRagClientException e) {
            assertEquals("AGENT_RAG_SCHEMA_MISMATCH", e.getErrorCode());
        }
    }

    @Test
    public void tenantMismatchIsRejected() {
        server.expect(once(), requestTo("http://agent-rag.test/analyze"))
                .andRespond(withSuccess(successJson("req-1", "tenant-b", "review-1", "low", "none", "tenant-b"), MediaType.APPLICATION_JSON));
        try {
            client.analyze(sampleRequest());
            fail("expected tenant mismatch");
        } catch (AgentRagTenantMismatchException e) {
            assertEquals("AGENT_RAG_TENANT_MISMATCH", e.getErrorCode());
        }
    }

    @Test
    public void crossTenantCitationRejectsWholeResponse() {
        server.expect(once(), requestTo("http://agent-rag.test/analyze"))
                .andRespond(withSuccess(successJson("req-1", "tenant-a", "review-1", "low", "none", "tenant-b"), MediaType.APPLICATION_JSON));
        try {
            client.analyze(sampleRequest());
            fail("expected citation tenant mismatch");
        } catch (AgentRagTenantMismatchException e) {
            assertEquals("AGENT_RAG_TENANT_MISMATCH", e.getErrorCode());
        }
    }

    @Test
    public void http500IsRetriedOnceWithSameRequestId() {
        server.expect(twice(), requestTo("http://agent-rag.test/analyze"))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("\"requestId\":\"req-1\"")))
                .andRespond(withServerError());
        try {
            client.analyze(sampleRequest());
            fail("expected 5xx");
        } catch (AgentRagClientException e) {
            assertEquals("AGENT_RAG_HTTP_5XX", e.getErrorCode());
            assertEquals(1, e.getRetryCount());
        }
        server.verify();
    }

    @Test
    public void http400IsNotRetried() {
        server.expect(once(), requestTo("http://agent-rag.test/analyze"))
                .andRespond(withBadRequest());
        try {
            client.analyze(sampleRequest());
            fail("expected 4xx");
        } catch (AgentRagClientException e) {
            assertEquals("AGENT_RAG_HTTP_4XX", e.getErrorCode());
            assertEquals(0, e.getRetryCount());
        }
        server.verify();
    }

    @Test
    public void invalidJsonIsProtocolFailure() {
        server.expect(once(), requestTo("http://agent-rag.test/analyze"))
                .andRespond(withSuccess("{not-json", MediaType.APPLICATION_JSON));
        try {
            client.analyze(sampleRequest());
            fail("expected invalid json");
        } catch (AgentRagClientException e) {
            assertEquals("AGENT_RAG_INVALID_JSON", e.getErrorCode());
        }
    }

    @Test
    public void responseTooLargeIsRejected() {
        config.setMaxResponseBytes(10);
        server.expect(once(), requestTo("http://agent-rag.test/analyze"))
                .andRespond(withSuccess(successJson("req-1", "tenant-a", "review-1", "low", "none", "tenant-a"), MediaType.APPLICATION_JSON));
        try {
            client.analyze(sampleRequest());
            fail("expected response too large");
        } catch (AgentRagResponseTooLargeException e) {
            assertEquals("AGENT_RAG_RESPONSE_TOO_LARGE", e.getErrorCode());
        }
    }

    @Test
    public void healthParsesProviderFields() {
        server.expect(once(), requestTo("http://agent-rag.test/health"))
                .andRespond(withSuccess("{\"status\":\"ready\",\"targetMode\":\"enterprise-maturity-local-single-node\",\"effectiveProviderImpl\":\"flagembedding\",\"indexCompatible\":true}", MediaType.APPLICATION_JSON));
        AgentRagHealthResponse response = client.health();
        assertEquals("ready", response.getStatus());
        assertEquals("flagembedding", response.getEffectiveProviderImpl());
        assertEquals(Boolean.TRUE, response.getIndexCompatible());
    }

    @Test
    public void dtoRoundTripAllowsUnknownFields() throws Exception {
        ObjectMapper mapper = new ObjectMapper().configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
        AgentRagAnalyzeResponse response = mapper.readValue(successJson("req-1", "tenant-a", "review-1", "high", "create-risk-task", "tenant-a")
                .replaceFirst("\\}$", ",\"unknown\":true}"), AgentRagAnalyzeResponse.class);
        assertEquals("high", response.getDecision().getRiskLevel());
        assertEquals(new BigDecimal("0.82"), response.getAnalysis().getConfidence());
        assertEquals("local_qwen3_transformers", response.getRuntime().getEffectiveAnalysisProvider());
        assertEquals("Qwen/Qwen3-1.7B", response.getRuntime().getLlmModelId());
        assertEquals("GROUNDED", response.getRuntime().getGroundingStatus());
        assertEquals("bge-m3", response.getRetrieval().getDenseProvider());
        assertEquals("local-model", response.getRetrieval().getEffectiveRerankerType());
        assertEquals(Integer.valueOf(2), response.getRetrieval().getRerankerInputCount());
    }

    private AgentRagAnalyzeRequest sampleRequest() {
        AgentRagAnalyzeRequest request = new AgentRagAnalyzeRequest();
        request.setRequestId("req-1");
        request.setTenantId("tenant-a");
        request.setSubjectType("review");
        request.setSubjectId("review-1");
        request.setQuery("refund broken item");
        return request;
    }

    private String successJson(String requestId, String tenantId, String subjectId, String riskLevel, String action, String citationTenant) {
        return "{"
                + "\"requestId\":\"" + requestId + "\","
                + "\"tenantId\":\"" + tenantId + "\","
                + "\"subjectId\":\"" + subjectId + "\","
                + "\"decision\":{\"riskLevel\":\"" + riskLevel + "\",\"riskTypes\":[\"normal_review\"],\"action\":\"" + action + "\"},"
                + "\"analysis\":{\"summary\":\"bounded summary\",\"confidence\":0.82},"
                + "\"retrieval\":{\"used\":true,\"retrievalEmpty\":false,\"query\":\"refund\",\"topK\":8,\"returned\":1,"
                + "\"denseProvider\":\"bge-m3\",\"requestedRetrievalMode\":\"hybrid-real\",\"effectiveRetrievalMode\":\"hybrid-real\","
                + "\"indexVersion\":\"idx-v1\",\"modelFingerprint\":\"dense-fp\",\"embeddingDimension\":1024,"
                + "\"faissIndexType\":\"IndexFlatIP\",\"faissMetric\":\"inner-product\",\"embeddingDurationMs\":11,\"faissSearchDurationMs\":2,"
                + "\"denseFallbackUsed\":false,\"requestedRerankerType\":\"local-model\",\"effectiveRerankerType\":\"local-model\","
                + "\"rerankerModelId\":\"BAAI/bge-reranker-v2-m3\",\"rerankerRevision\":\"953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e\","
                + "\"rerankerFingerprint\":\"rerank-fp\",\"rerankerInputCount\":2,\"rerankerOutputCount\":1,\"rerankerDurationMs\":15,\"rerankerFallbackUsed\":false,"
                + "\"citations\":[{\"documentId\":\"doc-1\",\"chunkId\":\"chunk-1\",\"tenantId\":\"" + citationTenant + "\",\"sourceType\":\"policy\",\"title\":\"Refund\",\"score\":0.9,\"rank\":1,\"contentHash\":\"abc123abc123\",\"snippet\":\"bounded\"}]},"
                + "\"runtime\":{\"engineType\":\"grounded-local-llm-rag\",\"fallbackUsed\":false,\"analyzerVersion\":\"agent-rag-phase1-v1\",\"schemaVersion\":\"2.0.0\",\"targetMode\":\"enterprise-maturity-local-single-node\","
                + "\"requestedAnalysisProvider\":\"local_qwen3_transformers\",\"effectiveAnalysisProvider\":\"local_qwen3_transformers\","
                + "\"llmModelId\":\"Qwen/Qwen3-1.7B\",\"llmRevision\":\"70d244cc86ccca08cf5af4e1e306ecf908b1ad5e\",\"llmFingerprint\":\"llm-fp\","
                + "\"promptVersion\":\"v22-grounded-qwen3-analysis-v1\",\"promptFingerprint\":\"prompt-fp\","
                + "\"llmInputTokens\":512,\"llmOutputTokens\":64,\"llmDurationMs\":1200,\"structuredOutputValid\":true,"
                + "\"groundingStatus\":\"GROUNDED\",\"abstained\":false,\"requiresHumanReview\":false,\"llmFallbackUsed\":false},"
                + "\"audit\":{\"evidenceId\":\"ev-1\",\"durationMs\":12,\"agentPath\":[],\"startedAt\":\"2026-01-01T00:00:00Z\",\"finishedAt\":\"2026-01-01T00:00:01Z\"}"
                + "}";
    }
}
