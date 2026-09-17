package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.ArrayList;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentRagAudit {
    private String evidenceId;
    private Long durationMs;
    private List<Object> agentPath = new ArrayList<Object>();
    private String startedAt;
    private String finishedAt;

    public String getEvidenceId() { return evidenceId; }
    public void setEvidenceId(String evidenceId) { this.evidenceId = evidenceId; }
    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }
    public List<Object> getAgentPath() { return agentPath; }
    public void setAgentPath(List<Object> agentPath) { this.agentPath = agentPath; }
    public String getStartedAt() { return startedAt; }
    public void setStartedAt(String startedAt) { this.startedAt = startedAt; }
    public String getFinishedAt() { return finishedAt; }
    public void setFinishedAt(String finishedAt) { this.finishedAt = finishedAt; }
}
