package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentRagAnalyzeResponse {
    private String requestId;
    private String tenantId;
    private String subjectId;
    private AgentRagDecision decision;
    private AgentRagAnalysis analysis;
    private AgentRagRetrievalResult retrieval;
    private AgentRagRuntime runtime;
    private AgentRagAudit audit;

    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }
    public String getSubjectId() { return subjectId; }
    public void setSubjectId(String subjectId) { this.subjectId = subjectId; }
    public AgentRagDecision getDecision() { return decision; }
    public void setDecision(AgentRagDecision decision) { this.decision = decision; }
    public AgentRagAnalysis getAnalysis() { return analysis; }
    public void setAnalysis(AgentRagAnalysis analysis) { this.analysis = analysis; }
    public AgentRagRetrievalResult getRetrieval() { return retrieval; }
    public void setRetrieval(AgentRagRetrievalResult retrieval) { this.retrieval = retrieval; }
    public AgentRagRuntime getRuntime() { return runtime; }
    public void setRuntime(AgentRagRuntime runtime) { this.runtime = runtime; }
    public AgentRagAudit getAudit() { return audit; }
    public void setAudit(AgentRagAudit audit) { this.audit = audit; }
}
