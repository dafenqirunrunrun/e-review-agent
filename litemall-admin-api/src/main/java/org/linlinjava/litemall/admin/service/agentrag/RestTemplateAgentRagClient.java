package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.net.SocketTimeoutException;
import java.util.List;
import java.util.Map;

public class RestTemplateAgentRagClient implements AgentRagClient {
    private final AgentRagConfig config;
    private final AgentRagTenantResolver tenantResolver;
    private final AgentRagCircuitBreaker circuitBreaker;
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public RestTemplateAgentRagClient(AgentRagConfig config) {
        this(config, new AgentRagTenantResolver(config), new AgentRagCircuitBreaker(config), createRestTemplate(config),
                new ObjectMapper().configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false));
    }

    public RestTemplateAgentRagClient(AgentRagConfig config, AgentRagTenantResolver tenantResolver,
                                      AgentRagCircuitBreaker circuitBreaker, RestTemplate restTemplate,
                                      ObjectMapper objectMapper) {
        config.validate();
        this.config = config;
        this.tenantResolver = tenantResolver;
        this.circuitBreaker = circuitBreaker;
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    }

    @Override
    public AgentRagAnalyzeResponse analyze(AgentRagAnalyzeRequest request) {
        if (!config.isEnabled()) {
            throw new AgentRagClientException("AGENT_RAG_DISABLED", "Agent-RAG client is disabled.");
        }
        tenantResolver.applyTrustedTenant(request);
        request.validate(config);
        validateContextLimit(request);
        long started = System.currentTimeMillis();
        int retryCount = 0;
        while (true) {
            circuitBreaker.beforeCall();
            try {
                String body = postJson(config.analyzeUrl(), request);
                AgentRagAnalyzeResponse response = parseAnalyzeResponse(body);
                validateResponse(request, response);
                circuitBreaker.recordSuccess();
                return response;
            } catch (AgentRagClientException e) {
                boolean circuitFailure = countsForCircuit(e);
                circuitBreaker.recordFailure(circuitFailure);
                if (canRetry(e) && retryCount < config.getMaxRetries()) {
                    retryCount++;
                    backoff();
                    continue;
                }
                throw retryCount == 0 ? e : withTiming(e, retryCount, started);
            } catch (RestClientException e) {
                AgentRagClientException mapped = mapRestException(e);
                circuitBreaker.recordFailure(countsForCircuit(mapped));
                if (canRetry(mapped) && retryCount < config.getMaxRetries()) {
                    retryCount++;
                    backoff();
                    continue;
                }
                throw retryCount == 0 ? mapped : withTiming(mapped, retryCount, started);
            }
        }
    }

    @Override
    public AgentRagHealthResponse health() {
        try {
            String body = getJson(config.healthUrl());
            Map<String, Object> raw = objectMapper.readValue(body, new TypeReference<Map<String, Object>>() {});
            AgentRagHealthResponse response = objectMapper.readValue(body, AgentRagHealthResponse.class);
            response.setRaw(raw);
            return response;
        } catch (Exception e) {
            AgentRagHealthResponse response = new AgentRagHealthResponse();
            response.setStatus("unavailable");
            return response;
        }
    }

    public Map<String, Object> circuitBreakerSnapshot() {
        return circuitBreaker.snapshot();
    }

    private String postJson(String url, Object request) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (request instanceof AgentRagAnalyzeRequest) {
            AgentRagAnalyzeRequest analyzeRequest = (AgentRagAnalyzeRequest) request;
            headers.set("X-Request-Id", analyzeRequest.getRequestId());
            headers.set("X-Tenant-Id", analyzeRequest.getTenantId());
        }
        ResponseEntity<String> entity = restTemplate.exchange(url, HttpMethod.POST, new HttpEntity<Object>(request, headers), String.class);
        String body = entity.getBody() == null ? "" : entity.getBody();
        if (body.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > config.getMaxResponseBytes()) {
            throw new AgentRagResponseTooLargeException();
        }
        return body;
    }

    private String getJson(String url) {
        ResponseEntity<String> entity = restTemplate.exchange(url, HttpMethod.GET, HttpEntity.EMPTY, String.class);
        String body = entity.getBody() == null ? "" : entity.getBody();
        if (body.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > config.getMaxResponseBytes()) {
            throw new AgentRagResponseTooLargeException();
        }
        return body;
    }

    private AgentRagAnalyzeResponse parseAnalyzeResponse(String body) {
        try {
            return objectMapper.readValue(body, AgentRagAnalyzeResponse.class);
        } catch (Exception e) {
            throw new AgentRagProtocolException("AGENT_RAG_INVALID_JSON", "Invalid Agent-RAG JSON response.", e);
        }
    }

    private void validateResponse(AgentRagAnalyzeRequest request, AgentRagAnalyzeResponse response) {
        if (response == null || blank(response.getRequestId()) || blank(response.getTenantId()) || blank(response.getSubjectId())
                || response.getDecision() == null || response.getRuntime() == null || response.getAudit() == null
                || blank(response.getRuntime().getSchemaVersion())) {
            throw new AgentRagProtocolException("AGENT_RAG_SCHEMA_MISMATCH", "Agent-RAG response missing required fields.");
        }
        if (!request.getRequestId().equals(response.getRequestId())) {
            throw new AgentRagProtocolException("AGENT_RAG_SCHEMA_MISMATCH", "Agent-RAG requestId mismatch.");
        }
        if (!request.getTenantId().equals(response.getTenantId())) {
            throw new AgentRagTenantMismatchException("Agent-RAG tenant mismatch.");
        }
        if (!request.getSubjectId().equals(response.getSubjectId())) {
            throw new AgentRagProtocolException("AGENT_RAG_SUBJECT_MISMATCH", "Agent-RAG subject mismatch.");
        }
        validateDecision(response.getDecision());
        if (response.getAnalysis() != null) {
            BigDecimal confidence = response.getAnalysis().getConfidence();
            if (confidence != null && (confidence.compareTo(BigDecimal.ZERO) < 0 || confidence.compareTo(BigDecimal.ONE) > 0)) {
                throw new AgentRagProtocolException("AGENT_RAG_SCHEMA_MISMATCH", "Agent-RAG confidence out of range.");
            }
            String summary = response.getAnalysis().getSummary();
            if (summary != null && summary.length() > config.getMaxSummaryChars()) {
                throw new AgentRagProtocolException("AGENT_RAG_SCHEMA_MISMATCH", "Agent-RAG summary too large.");
            }
        }
        validateCitations(request.getTenantId(), response.getRetrieval());
    }

    private void validateDecision(AgentRagDecision decision) {
        if (!oneOf(decision.getRiskLevel(), "low", "medium", "high")) {
            throw new AgentRagProtocolException("AGENT_RAG_SCHEMA_MISMATCH", "Agent-RAG riskLevel invalid.");
        }
        if (!oneOf(decision.getAction(), "none", "create-risk-task", "manual-review", "explicit-failure")) {
            throw new AgentRagProtocolException("AGENT_RAG_SCHEMA_MISMATCH", "Agent-RAG action invalid.");
        }
    }

    private void validateCitations(String tenantId, AgentRagRetrievalResult retrieval) {
        if (retrieval == null || retrieval.getCitations() == null) {
            return;
        }
        List<AgentRagCitation> citations = retrieval.getCitations();
        if (citations.size() > config.getMaxCitations()) {
            throw new AgentRagProtocolException("AGENT_RAG_SCHEMA_MISMATCH", "Too many Agent-RAG citations.");
        }
        for (AgentRagCitation citation : citations) {
            String citationTenant = citation.getTenantId();
            if (!tenantId.equals(citationTenant) && !"__public__".equals(citationTenant)) {
                throw new AgentRagTenantMismatchException("Cross-tenant citation rejected.");
            }
            String snippet = citation.getBoundedSnippet();
            if (snippet != null && snippet.length() > config.getMaxSnippetChars()) {
                throw new AgentRagProtocolException("AGENT_RAG_SCHEMA_MISMATCH", "Citation snippet too large.");
            }
        }
    }

    private void validateContextLimit(AgentRagAnalyzeRequest request) {
        try {
            int bytes = objectMapper.writeValueAsBytes(request.getContext()).length;
            if (bytes > config.getMaxContextBytes()) {
                throw new AgentRagProtocolException("AGENT_RAG_CONTEXT_TOO_LARGE", "Context exceeds configured limit.");
            }
        } catch (JsonProcessingException e) {
            throw new AgentRagProtocolException("AGENT_RAG_REQUEST_INVALID", "Context is not JSON serializable.", e);
        }
    }

    private AgentRagClientException mapRestException(RestClientException e) {
        if (e instanceof HttpStatusCodeException) {
            HttpStatusCodeException http = (HttpStatusCodeException) e;
            int code = http.getStatusCode().value();
            if (code >= 500) {
                return new AgentRagUnavailableException("AGENT_RAG_HTTP_5XX", "Agent-RAG HTTP 5xx.", e, 0, 0L);
            }
            return new AgentRagClientException("AGENT_RAG_HTTP_4XX", "Agent-RAG HTTP 4xx.", e);
        }
        if (e instanceof ResourceAccessException) {
            Throwable cause = e.getCause();
            if (cause instanceof SocketTimeoutException) {
                return new AgentRagTimeoutException("AGENT_RAG_READ_TIMEOUT", "Agent-RAG read timeout.", e, 0, 0L);
            }
            return new AgentRagUnavailableException("AGENT_RAG_CONNECT_TIMEOUT", "Agent-RAG connection unavailable.", e, 0, 0L);
        }
        return new AgentRagClientException("AGENT_RAG_UNKNOWN_ERROR", "Agent-RAG unknown error.", e);
    }

    private AgentRagClientException withTiming(AgentRagClientException e, int retryCount, long started) {
        return new AgentRagClientException(e.getErrorCode(), e.getMessage(), e.getCause(), retryCount, System.currentTimeMillis() - started);
    }

    private boolean canRetry(AgentRagClientException e) {
        String code = e.getErrorCode();
        return "AGENT_RAG_CONNECT_TIMEOUT".equals(code)
                || "AGENT_RAG_READ_TIMEOUT".equals(code)
                || "AGENT_RAG_HTTP_5XX".equals(code);
    }

    private boolean countsForCircuit(AgentRagClientException e) {
        String code = e.getErrorCode();
        return "AGENT_RAG_CONNECT_TIMEOUT".equals(code)
                || "AGENT_RAG_READ_TIMEOUT".equals(code)
                || "AGENT_RAG_HTTP_5XX".equals(code)
                || "AGENT_RAG_INVALID_JSON".equals(code)
                || "AGENT_RAG_SCHEMA_MISMATCH".equals(code)
                || "AGENT_RAG_RESPONSE_TOO_LARGE".equals(code);
    }

    private void backoff() {
        if (config.getRetryBackoffMs() <= 0) {
            return;
        }
        try {
            Thread.sleep(config.getRetryBackoffMs());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private boolean blank(String value) {
        return value == null || value.trim().length() == 0;
    }

    private boolean oneOf(String value, String a, String b, String c) {
        return a.equals(value) || b.equals(value) || c.equals(value);
    }

    private boolean oneOf(String value, String a, String b, String c, String d) {
        return a.equals(value) || b.equals(value) || c.equals(value) || d.equals(value);
    }

    private static RestTemplate createRestTemplate(AgentRagConfig config) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(config.getConnectTimeoutMs());
        factory.setReadTimeout(config.getReadTimeoutMs());
        return new RestTemplate(factory);
    }
}
