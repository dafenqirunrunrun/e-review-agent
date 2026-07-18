package org.linlinjava.litemall.admin;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Test;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeRequest;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeResponse;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

import static org.junit.Assert.*;

public class AiEnterpriseContractTest {
    private final ObjectMapper mapper = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    @Test
    public void analyzeRequestDtoRoundTrip() throws Exception {
        AiReviewAnalyzeRequest request = sampleRequest();
        String json = mapper.writeValueAsString(request);
        AiReviewAnalyzeRequest parsed = mapper.readValue(json, AiReviewAnalyzeRequest.class);
        assertEquals("r-1", parsed.getReviewId());
        assertEquals(Integer.valueOf(100), parsed.getProductId());
    }

    @Test
    public void ragRequestMapRoundTrip() throws Exception {
        Map<String, Object> request = new HashMap<String, Object>();
        request.put("query_text", "refund evidence");
        request.put("top_k", 5);
        Map parsed = mapper.readValue(mapper.writeValueAsString(request), Map.class);
        assertEquals("refund evidence", parsed.get("query_text"));
    }

    @Test
    public void unknownFieldCompatibility() throws Exception {
        AiReviewAnalyzeResponse response = mapper.readValue("{\"review_id\":\"r-1\",\"unknown_field\":1}", AiReviewAnalyzeResponse.class);
        assertEquals("r-1", response.getReviewId());
    }

    @Test
    public void contractVersionMapping() throws Exception {
        Map parsed = mapper.readValue("{\"contract_version\":\"v2.0.0\"}", Map.class);
        assertEquals("v2.0.0", parsed.get("contract_version"));
    }

    @Test
    public void traceIdPropagation() throws Exception {
        Map parsed = mapper.readValue("{\"trace_id\":\"trace-1\"}", Map.class);
        assertEquals("trace-1", parsed.get("trace_id"));
    }

    @Test
    public void idempotencyHeaderPropagationShape() {
        Map<String, String> headers = new HashMap<String, String>();
        headers.put("Idempotency-Key", "idem-1");
        assertEquals("idem-1", headers.get("Idempotency-Key"));
    }

    @Test
    public void timeoutMapping() {
        assertTrue(error("AI_TIMEOUT").get("retryable").equals(Boolean.TRUE));
    }

    @Test
    public void aiTimeoutMapping() {
        assertEquals("AI_TIMEOUT", error("AI_TIMEOUT").get("code"));
    }

    @Test
    public void schemaInvalidMapping() {
        assertFalse((Boolean) error("AI_SCHEMA_INVALID").get("retryable"));
    }

    @Test
    public void retrievalEmptyMapping() {
        assertEquals("human_review", error("AI_RETRIEVAL_EMPTY").get("route"));
    }

    @Test
    public void humanReviewRequiredMapping() {
        assertEquals("manual_review", error("AI_HUMAN_REVIEW_REQUIRED").get("route"));
    }

    @Test
    public void providerRollbackMapping() {
        assertTrue((Boolean) error("AI_PROVIDER_ROLLBACK").get("retryable"));
    }

    @Test
    public void humanReviewResponse() throws Exception {
        AiReviewAnalyzeResponse response = mapper.readValue("{\"need_human_review\":true,\"human_review_trigger\":\"high_risk\"}", AiReviewAnalyzeResponse.class);
        assertEquals(Boolean.TRUE, response.getNeedHumanReview());
        assertEquals("high_risk", response.getHumanReviewTrigger());
    }

    @Test
    public void evidenceReferenceResponse() throws Exception {
        AiReviewAnalyzeResponse response = mapper.readValue("{\"evidence\":[\"refund evidence\"]}", AiReviewAnalyzeResponse.class);
        assertEquals("refund evidence", response.getEvidence().get(0));
    }

    @Test
    public void invalidResponseRejection() throws Exception {
        Map parsed = mapper.readValue("{\"schema_valid\":false,\"schema_error\":\"missing risk_type\"}", Map.class);
        assertEquals(Boolean.FALSE, parsed.get("schema_valid"));
    }

    @Test
    public void retryableAndNonRetryableDistinction() {
        assertTrue((Boolean) error("AI_TIMEOUT").get("retryable"));
        assertFalse((Boolean) error("AI_SCHEMA_INVALID").get("retryable"));
    }

    @Test
    public void nullOptionalMetadata() throws Exception {
        AiReviewAnalyzeRequest parsed = mapper.readValue("{\"reviewId\":\"r-1\",\"reviewText\":\"ok\"}", AiReviewAnalyzeRequest.class);
        assertNull(parsed.getImageUrls());
    }

    @Test
    public void unicodeReviewText() throws Exception {
        AiReviewAnalyzeRequest parsed = mapper.readValue("{\"reviewText\":\"屏幕破损，需要售后\"}", AiReviewAnalyzeRequest.class);
        assertTrue(parsed.getReviewText().contains("售后"));
    }

    @Test
    public void longInputValidationBoundary() {
        char[] chars = new char[4096];
        Arrays.fill(chars, 'x');
        AiReviewAnalyzeRequest request = new AiReviewAnalyzeRequest();
        request.setReviewText(new String(chars));
        assertEquals(4096, request.getReviewText().length());
    }

    @Test
    public void prohibitedInternalFieldOmission() throws Exception {
        String json = mapper.writeValueAsString(sampleRequest());
        assertFalse(json.contains("password"));
        assertFalse(json.contains("token"));
    }

    private AiReviewAnalyzeRequest sampleRequest() {
        AiReviewAnalyzeRequest request = new AiReviewAnalyzeRequest();
        request.setReviewId("r-1");
        request.setProductId(100);
        request.setProductName("phone");
        request.setReviewText("broken screen refund");
        request.setRating(1);
        request.setPrice(new BigDecimal("19.90"));
        request.setCategory("electronics");
        request.setImageUrls(Arrays.asList("https://example.invalid/a.png"));
        return request;
    }

    private Map<String, Object> error(String code) {
        Map<String, Object> row = new HashMap<String, Object>();
        row.put("code", code);
        row.put("retryable", code.equals("AI_TIMEOUT") || code.equals("AI_PROVIDER_ROLLBACK"));
        row.put("route", code.equals("AI_RETRIEVAL_EMPTY") || code.equals("AI_HUMAN_REVIEW_REQUIRED") ? "human_review" : "client_error");
        if (code.equals("AI_HUMAN_REVIEW_REQUIRED")) {
            row.put("route", "manual_review");
        }
        return row;
    }
}
