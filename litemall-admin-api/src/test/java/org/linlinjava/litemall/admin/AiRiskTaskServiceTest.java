package org.linlinjava.litemall.admin;

import org.junit.Test;
import org.linlinjava.litemall.admin.service.AiRiskTaskService;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class AiRiskTaskServiceTest {
    @Test
    public void humanDecisionMapsToTerminalStatus() {
        assertEquals("closed", AiRiskTaskService.statusForHumanDecision("accept_ai_suggestion"));
        assertEquals("closed", AiRiskTaskService.statusForHumanDecision("override"));
        assertEquals("ignored", AiRiskTaskService.statusForHumanDecision("no_action"));
        assertEquals("accept_ai_suggestion", AiRiskTaskService.normalizeHumanDecision("unexpected"));
    }

    @Test
    public void terminalStatusPreventsDuplicateHumanReview() {
        assertFalse(AiRiskTaskService.isTerminalStatus("pending"));
        assertFalse(AiRiskTaskService.isTerminalStatus("viewed"));
        assertTrue(AiRiskTaskService.isTerminalStatus("closed"));
        assertTrue(AiRiskTaskService.isTerminalStatus("ignored"));
        assertTrue(AiRiskTaskService.isTerminalStatus("processed"));
    }

    @Test
    public void businessLabelsHideInternalAuditCodes() {
        assertEquals("需人工复核", AiRiskTaskService.decisionLabel("manual_review"));
        assertEquals("证据不匹配", AiRiskTaskService.evidenceStatusLabel("mismatch"));
        assertEquals("售后争议", AiRiskTaskService.riskTypeLabel("after_sales_risk"));
        assertEquals("售后争议、评分操纵", AiRiskTaskService.riskTypeListLabel("after_sales_risk,rating_manipulation"));
    }
}
