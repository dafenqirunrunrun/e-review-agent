package org.linlinjava.litemall.admin.service;

import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeRequest;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeResponse;
import org.linlinjava.litemall.admin.util.PublicRequestContext;
import org.linlinjava.litemall.admin.util.PublicRuntimeMetrics;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

@Service
public class AiReviewService {
    @Value("${ai.service.base-url:http://127.0.0.1:8008}")
    private String baseUrl;

    @Value("${ai.service.connect-timeout:3000}")
    private Integer connectTimeout;

    @Value("${ai.service.read-timeout:10000}")
    private Integer readTimeout;

    @Value("${ai.agent-framework.enabled:false}")
    private Boolean agentFrameworkEnabled;

    @Value("${ai.agent-framework.fallback-to-legacy:true}")
    private Boolean agentFrameworkFallbackToLegacy;

    public AiReviewAnalyzeResponse analyze(AiReviewAnalyzeRequest request) {
        RestTemplate restTemplate = createRestTemplate();
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.add(PublicRequestContext.REQUEST_ID_HEADER, PublicRequestContext.currentOrCreate());
        HttpEntity<AiReviewAnalyzeRequest> entity = new HttpEntity<AiReviewAnalyzeRequest>(request, headers);

        String url = trimTrailingSlash(baseUrl) + "/api/v1/review/analyze";
        try {
            ResponseEntity<AiReviewAnalyzeResponse> response = restTemplate.postForEntity(url, entity, AiReviewAnalyzeResponse.class);
            PublicRuntimeMetrics.recordAiAnalysis(true);
            return response.getBody();
        } catch (RestClientException e) {
            PublicRuntimeMetrics.recordAiAnalysis(false);
            throw new AiReviewServiceException("AI service request failed: " + e.getMessage(), e);
        }
    }

    public Map frameworkStatus() {
        RestTemplate restTemplate = createRestTemplate();
        String url = trimTrailingSlash(baseUrl) + "/api/v1/agent-framework/status";
        try {
            Map status = restTemplate.getForObject(url, Map.class);
            if (status != null) {
                status.put("javaConfigEnabled", Boolean.TRUE.equals(agentFrameworkEnabled));
                status.put("javaFallbackToLegacy", Boolean.TRUE.equals(agentFrameworkFallbackToLegacy));
            }
            return status;
        } catch (RestClientException e) {
            throw new AiReviewServiceException("AI framework status request failed: " + e.getMessage(), e);
        }
    }

    public Map ragV2Status() {
        return getMap("/api/v1/rag-v2/status", "RAG v2 status");
    }

    public Map ragV2Search(Map request) {
        return postMap("/api/v1/rag-v2/search", request, "RAG v2 search");
    }

    public Map ragV2Evaluate(Map request) {
        return postMap("/api/v1/rag-v2/evaluate", request, "RAG v2 evaluate");
    }

    public Map enterpriseHealth() {
        return getMap("/api/v1/e-review/health", "Enterprise e-review health");
    }

    public Map enterpriseRuntimeStatus() {
        return getMap("/api/v1/e-review/runtime-status", "Enterprise e-review runtime status");
    }

    public Map enterpriseMetrics() {
        return getMap("/api/v1/e-review/metrics", "Enterprise e-review metrics");
    }

    public Map enterpriseAnalyze(Map request) {
        return postMap("/api/v1/e-review/analyze", request, "Enterprise e-review analyze");
    }

    public Map enterpriseAnalyzeRag(Map request) {
        return postMap("/api/v1/e-review/analyze/rag", request, "Enterprise e-review RAG analyze");
    }

    public String ragV2Report() {
        RestTemplate restTemplate = createRestTemplate();
        try {
            return restTemplate.getForObject(trimTrailingSlash(baseUrl) + "/api/v1/rag-v2/report", String.class);
        } catch (RestClientException e) {
            throw new AiReviewServiceException("RAG v2 report request failed: " + e.getMessage(), e);
        }
    }

    private Map getMap(String path, String operation) {
        RestTemplate restTemplate = createRestTemplate();
        try {
            return restTemplate.getForObject(trimTrailingSlash(baseUrl) + path, Map.class);
        } catch (RestClientException e) {
            throw new AiReviewServiceException(operation + " request failed: " + e.getMessage(), e);
        }
    }

    private Map postMap(String path, Map request, String operation) {
        RestTemplate restTemplate = createRestTemplate();
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.add(PublicRequestContext.REQUEST_ID_HEADER, PublicRequestContext.currentOrCreate());
        try {
            return restTemplate.postForObject(trimTrailingSlash(baseUrl) + path,
                    new HttpEntity<Map>(request, headers), Map.class);
        } catch (RestClientException e) {
            throw new AiReviewServiceException(operation + " request failed: " + e.getMessage(), e);
        }
    }

    private RestTemplate createRestTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connectTimeout);
        factory.setReadTimeout(readTimeout);
        return new RestTemplate(factory);
    }

    private String trimTrailingSlash(String value) {
        if (value == null || value.length() == 0) {
            return "http://127.0.0.1:8008";
        }
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    public static class AiReviewServiceException extends RuntimeException {
        public AiReviewServiceException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
