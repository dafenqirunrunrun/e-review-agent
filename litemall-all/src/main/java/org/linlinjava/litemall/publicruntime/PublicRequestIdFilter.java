package org.linlinjava.litemall.publicruntime;

import org.linlinjava.litemall.admin.util.PublicRequestContext;
import org.linlinjava.litemall.admin.util.PublicRuntimeMetrics;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

@Component
public class PublicRequestIdFilter extends OncePerRequestFilter {
    private static final Logger logger = LoggerFactory.getLogger(PublicRequestIdFilter.class);

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        long startedAt = System.currentTimeMillis();
        String requestId = request.getHeader(PublicRequestContext.REQUEST_ID_HEADER);
        PublicRequestContext.set(requestId);
        response.setHeader(PublicRequestContext.REQUEST_ID_HEADER, PublicRequestContext.currentOrCreate());

        try {
            filterChain.doFilter(request, response);
        } finally {
            long durationMs = System.currentTimeMillis() - startedAt;
            PublicRuntimeMetrics.recordHttp(durationMs, response.getStatus());
            logger.info("event=public_http_request service=litemall-all request_id={} operation={} status={} duration_ms={}",
                    PublicRequestContext.currentOrCreate(), request.getRequestURI(), response.getStatus(), durationMs);
            PublicRequestContext.clear();
        }
    }
}
