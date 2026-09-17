package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.LinkedHashMap;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentRagAnalyzeRequest {
    private String requestId;
    private String tenantId;
    private String subjectType = "review";
    private String subjectId;
    private String query;
    private Map<String, Object> context = new LinkedHashMap<String, Object>();
    private String runtimeMode = "local-model";
    private String schemaVersion = "2.0.0";
    private AgentRagRetrievalOptions retrieval = new AgentRagRetrievalOptions();

    public void validate(AgentRagConfig config) {
        required(requestId, "requestId");
        required(tenantId, "tenantId");
        required(subjectType, "subjectType");
        required(subjectId, "subjectId");
        required(query, "query");
        required(schemaVersion, "schemaVersion");
        if (query.length() > config.getMaxQueryChars()) {
            throw new AgentRagProtocolException("AGENT_RAG_QUERY_TOO_LARGE", "Query exceeds configured limit.");
        }
    }

    private void required(String value, String field) {
        if (value == null || value.trim().length() == 0) {
            throw new AgentRagProtocolException("AGENT_RAG_REQUEST_INVALID", field + " is required.");
        }
    }

    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }
    public String getSubjectType() { return subjectType; }
    public void setSubjectType(String subjectType) { this.subjectType = subjectType; }
    public String getSubjectId() { return subjectId; }
    public void setSubjectId(String subjectId) { this.subjectId = subjectId; }
    public String getQuery() { return query; }
    public void setQuery(String query) { this.query = query; }
    public Map<String, Object> getContext() { return context; }
    public void setContext(Map<String, Object> context) { this.context = context == null ? new LinkedHashMap<String, Object>() : context; }
    public String getRuntimeMode() { return runtimeMode; }
    public void setRuntimeMode(String runtimeMode) { this.runtimeMode = runtimeMode; }
    public String getSchemaVersion() { return schemaVersion; }
    public void setSchemaVersion(String schemaVersion) { this.schemaVersion = schemaVersion; }
    public AgentRagRetrievalOptions getRetrieval() { return retrieval; }
    public void setRetrieval(AgentRagRetrievalOptions retrieval) { this.retrieval = retrieval == null ? new AgentRagRetrievalOptions() : retrieval; }
}
