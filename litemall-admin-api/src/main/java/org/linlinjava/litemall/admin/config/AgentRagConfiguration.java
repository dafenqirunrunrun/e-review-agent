package org.linlinjava.litemall.admin.config;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagCircuitBreaker;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagClient;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagConfig;
import org.linlinjava.litemall.admin.service.agentrag.AgentRagTenantResolver;
import org.linlinjava.litemall.admin.service.agentrag.RestTemplateAgentRagClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

@Configuration
public class AgentRagConfiguration {
    @Bean
    public AgentRagConfig agentRagConfig(
            @Value("${agent-rag.enabled:true}") boolean enabled,
            @Value("${agent-rag.base-url:http://127.0.0.1:8008}") String baseUrl,
            @Value("${agent-rag.analyze-path:/api/v1/agent-rag/analyze}") String analyzePath,
            @Value("${agent-rag.health-path:/api/v1/internal/agent-rag/dense/health}") String healthPath,
            @Value("${agent-rag.connect-timeout-ms:2000}") int connectTimeoutMs,
            @Value("${agent-rag.read-timeout-ms:30000}") int readTimeoutMs,
            @Value("${agent-rag.total-timeout-ms:35000}") int totalTimeoutMs,
            @Value("${agent-rag.max-retries:1}") int maxRetries,
            @Value("${agent-rag.retry-backoff-ms:200}") int retryBackoffMs,
            @Value("${agent-rag.max-response-bytes:2097152}") int maxResponseBytes,
            @Value("${agent-rag.max-context-bytes:65536}") int maxContextBytes,
            @Value("${agent-rag.max-citations:20}") int maxCitations,
            @Value("${agent-rag.max-evidence-bytes:524288}") int maxEvidenceBytes,
            @Value("${agent-rag.single-tenant-id:__local__}") String singleTenantId,
            @Value("${agent-rag.circuit-breaker.failure-threshold:5}") int failureThreshold,
            @Value("${agent-rag.circuit-breaker.open-duration-ms:30000}") long openDurationMs,
            @Value("${agent-rag.circuit-breaker.half-open-max-calls:1}") int halfOpenMaxCalls) {
        AgentRagConfig config = new AgentRagConfig();
        config.setEnabled(enabled);
        config.setBaseUrl(baseUrl);
        config.setAnalyzePath(analyzePath);
        config.setHealthPath(healthPath);
        config.setConnectTimeoutMs(connectTimeoutMs);
        config.setReadTimeoutMs(readTimeoutMs);
        config.setTotalTimeoutMs(totalTimeoutMs);
        config.setMaxRetries(maxRetries);
        config.setRetryBackoffMs(retryBackoffMs);
        config.setMaxResponseBytes(maxResponseBytes);
        config.setMaxContextBytes(maxContextBytes);
        config.setMaxCitations(maxCitations);
        config.setMaxEvidenceBytes(maxEvidenceBytes);
        config.setSingleTenantId(singleTenantId);
        config.setCircuitBreakerFailureThreshold(failureThreshold);
        config.setCircuitBreakerOpenDurationMs(openDurationMs);
        config.setCircuitBreakerHalfOpenMaxCalls(halfOpenMaxCalls);
        config.validate();
        return config;
    }

    @Bean
    public AgentRagTenantResolver agentRagTenantResolver(AgentRagConfig config) {
        return new AgentRagTenantResolver(config);
    }

    @Bean
    public AgentRagCircuitBreaker agentRagCircuitBreaker(AgentRagConfig config) {
        return new AgentRagCircuitBreaker(config);
    }

    @Bean
    public AgentRagClient agentRagClient(AgentRagConfig config, AgentRagTenantResolver tenantResolver,
                                         AgentRagCircuitBreaker circuitBreaker, ObjectMapper objectMapper) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(config.getConnectTimeoutMs());
        factory.setReadTimeout(config.getReadTimeoutMs());
        ObjectMapper safeMapper = objectMapper.copy().configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
        return new RestTemplateAgentRagClient(config, tenantResolver, circuitBreaker, new RestTemplate(factory), safeMapper);
    }
}
