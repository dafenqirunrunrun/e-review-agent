package org.linlinjava.litemall.admin.agentrag.trace;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

public class AgentTracePropagationSigner {
    public String sign(AgentTraceContext context, String key) {
        return sign(context.getRequestId(), context.getTraceId(), context.getExecutionId(),
                context.getTraceSchemaVersion(), context.getCallerService(), context.getIssuedAtUtc(), key);
    }

    public String sign(String requestId, String traceId, String executionId, String traceSchemaVersion,
                       String callerService, String issuedAtUtc, String key) {
        try {
            String payload = requestId + "\n" + traceId + "\n" + executionId + "\n"
                    + traceSchemaVersion + "\n" + callerService + "\n" + issuedAtUtc;
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] digest = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder();
            for (byte item : digest) {
                builder.append(String.format("%02x", item));
            }
            return builder.toString();
        } catch (Exception ex) {
            throw new IllegalStateException("TRACE_CONTEXT_SIGN_FAILED", ex);
        }
    }
}
