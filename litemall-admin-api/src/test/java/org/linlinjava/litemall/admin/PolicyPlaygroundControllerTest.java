package org.linlinjava.litemall.admin;

import org.junit.Test;
import org.linlinjava.litemall.admin.service.AiReviewService;
import org.linlinjava.litemall.admin.web.AdminAiReviewController;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import static org.junit.Assert.assertEquals;
import static org.mockito.Mockito.*;

public class PolicyPlaygroundControllerTest {
    @Test
    public void playgroundProxiesReadOnlyResultWithoutCallingAnalyze() {
        AiReviewService service = mock(AiReviewService.class);
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("isolated", true);
        when(service.policyPlaygroundQuery(anyMap())).thenReturn(result);
        AdminAiReviewController controller = new AdminAiReviewController();
        ReflectionTestUtils.setField(controller, "aiReviewService", service);

        Map<String, Object> request = new HashMap<String, Object>();
        request.put("query", "五星好评截图返现");
        Map response = (Map) controller.policyPlaygroundQuery(request);
        Map data = (Map) response.get("data");

        assertEquals(0, response.get("errno"));
        assertEquals(Boolean.TRUE, data.get("isolated"));
        verify(service, times(1)).policyPlaygroundQuery(request);
        verify(service, never()).analyze(any());
    }

    @Test
    public void playgroundRejectsMissingOrOversizedQuery() {
        AiReviewService service = mock(AiReviewService.class);
        AdminAiReviewController controller = new AdminAiReviewController();
        ReflectionTestUtils.setField(controller, "aiReviewService", service);

        Map missing = (Map) controller.policyPlaygroundQuery(Collections.<String, Object>emptyMap());
        Map<String, Object> tooLong = new HashMap<String, Object>();
        tooLong.put("query", String.join("", Collections.nCopies(2001, "a")));
        Map oversized = (Map) controller.policyPlaygroundQuery(tooLong);

        assertEquals(402, missing.get("errno"));
        assertEquals(402, oversized.get("errno"));
        verifyZeroInteractions(service);
    }

    @Test
    public void playgroundAllowsShortGreetingForGuidanceFallback() {
        AiReviewService service = mock(AiReviewService.class);
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("route", "input_guidance");
        when(service.policyPlaygroundQuery(anyMap())).thenReturn(result);
        AdminAiReviewController controller = new AdminAiReviewController();
        ReflectionTestUtils.setField(controller, "aiReviewService", service);

        Map<String, Object> request = new HashMap<String, Object>();
        request.put("query", "你好");
        Map response = (Map) controller.policyPlaygroundQuery(request);

        assertEquals(0, response.get("errno"));
        verify(service, times(1)).policyPlaygroundQuery(request);
    }
}
