package org.linlinjava.litemall.admin.service.agentrag;

import org.linlinjava.litemall.db.domain.LitemallAgentRagEvidence;
import org.linlinjava.litemall.db.domain.LitemallAgentRagRun;

public class AgentRagWorkflowResult {
    private final LitemallAgentRagRun run;
    private final LitemallAgentRagEvidence evidence;
    private final AgentRagAnalyzeResponse response;
    private final boolean idempotentReplay;

    public AgentRagWorkflowResult(LitemallAgentRagRun run, LitemallAgentRagEvidence evidence,
                                  AgentRagAnalyzeResponse response, boolean idempotentReplay) {
        this.run = run;
        this.evidence = evidence;
        this.response = response;
        this.idempotentReplay = idempotentReplay;
    }

    public LitemallAgentRagRun getRun() {
        return run;
    }

    public LitemallAgentRagEvidence getEvidence() {
        return evidence;
    }

    public AgentRagAnalyzeResponse getResponse() {
        return response;
    }

    public boolean isIdempotentReplay() {
        return idempotentReplay;
    }
}
