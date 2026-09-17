package org.linlinjava.litemall.admin.service.agentrag;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.ArrayList;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentRagDecision {
    private String riskLevel;
    private List<String> riskTypes = new ArrayList<String>();
    private String action;
    private Boolean requiresHumanReview = false;

    public String getRiskLevel() { return riskLevel; }
    public void setRiskLevel(String riskLevel) { this.riskLevel = riskLevel; }
    public List<String> getRiskTypes() { return riskTypes; }
    public void setRiskTypes(List<String> riskTypes) { this.riskTypes = riskTypes; }
    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }
    public Boolean getRequiresHumanReview() { return requiresHumanReview; }
    public void setRequiresHumanReview(Boolean requiresHumanReview) { this.requiresHumanReview = requiresHumanReview; }
}
