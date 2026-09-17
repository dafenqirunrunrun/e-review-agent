package org.linlinjava.litemall.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeResponse;
import org.linlinjava.litemall.admin.vo.AiReviewAnalyzeRequest;
import org.linlinjava.litemall.db.domain.LitemallAiGovernanceObservation;
import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;
import org.linlinjava.litemall.db.service.LitemallAiGovernanceObservationService;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Value;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.CompletableFuture;

@Service
public class GovernanceQualityService {
    public static final Set<String> HUMAN_REASON_CODES = new LinkedHashSet<String>(Arrays.asList(
            "FALSE_POSITIVE", "WRONG_RISK_TYPE", "EVIDENCE_INSUFFICIENT", "EVIDENCE_MISMATCH",
            "CONTEXT_MISSING", "POLICY_NOT_APPLICABLE", "BUSINESS_EXCEPTION", "OTHER"));
    private final LitemallAiGovernanceObservationService observationService;
    private final ObjectMapper objectMapper;

    @Value("${ai.governance-quality.shadow-sample-percent:5}")
    private Integer shadowSamplePercent;

    public GovernanceQualityService(LitemallAiGovernanceObservationService observationService, ObjectMapper objectMapper) {
        this.observationService = observationService;
        this.objectMapper = objectMapper;
    }

    public void recordDecision(Integer analysisId, AiReviewAnalyzeResponse response, long latencyMs) {
        Map<String, Object> governance = response.getReviewGovernance();
        LitemallAiGovernanceObservation row = base(governance);
        row.setEventType("decision"); row.setAnalysisId(analysisId); row.setReviewId(response.getReviewId());
        row.setRoute(value(governance, "route", response.getRouteDecision()));
        row.setDecision(value(nested(governance, "decision"), "code", response.getRouteDecision()));
        row.setEvidenceStatus(value(governance, "evidenceStatus", response.getEvidenceStatus()));
        row.setRiskTypesJson(json(list(governance, "riskTypes", response.getRiskTypes())));
        row.setLatencyMs(latencyMs);
        row.setRetrievalMode(retrievalMode(governance));
        row.setEvidenceRefs(evidenceRefs(governance));
        observationService.add(row);
    }

    public void recordHumanReview(LitemallAiReviewRiskTask task, Map<String, Object> governance, String decision, String reasonCode) {
        LitemallAiGovernanceObservation row = base(governance);
        row.setEventType("human_review"); row.setRiskTaskId(task.getId()); row.setAnalysisId(task.getAnalysisId()); row.setReviewId(task.getReviewId());
        row.setDecision(value(nested(governance, "decision"), "code", "manual_review"));
        row.setEvidenceStatus(value(governance, "evidenceStatus", "insufficient")); row.setRiskTypesJson(json(list(governance, "riskTypes", Collections.singletonList(task.getRiskType()))));
        row.setRetrievalMode(retrievalMode(governance)); row.setEvidenceRefs(evidenceRefs(governance)); row.setHumanDecision(decision);
        row.setHumanReasonCode(normalizeReason(reasonCode, decision)); observationService.add(row);
    }

    public Map<String, Object> metrics(Integer hours) {
        int window = hours == null ? 24 : Math.max(1, Math.min(hours, 24 * 90));
        List<LitemallAiGovernanceObservation> events = observationService.querySince(LocalDateTime.now().minusHours(window));
        List<LitemallAiGovernanceObservation> decisions = byType(events, "decision");
        List<LitemallAiGovernanceObservation> humans = byType(events, "human_review");
        Map<String, Object> total = new LinkedHashMap<String, Object>();
        total.put("reviewTotal", decisions.size()); total.put("lightPathTotal", count(decisions, "route", "low_touch")); total.put("strictPathTotal", countNot(decisions, "route", "low_touch"));
        total.put("autoPassTotal", count(decisions, "decision", "auto_pass")); total.put("suggestActionTotal", count(decisions, "decision", "suggest_action")); total.put("manualReviewTotal", count(decisions, "decision", "manual_review"));
        total.put("supportedTotal", count(decisions, "evidenceStatus", "supported")); total.put("insufficientTotal", count(decisions, "evidenceStatus", "insufficient")); total.put("mismatchTotal", count(decisions, "evidenceStatus", "mismatch"));
        total.put("hybridTotal", countPrefix(decisions, "retrievalMode", "hybrid")); total.put("bm25FallbackTotal", countPrefix(decisions, "retrievalMode", "bm25")); total.put("retrievalFailureTotal", count(decisions, "retrievalMode", "retrieval_failure"));
        total.put("humanAcceptAiTotal", count(humans, "humanDecision", "accept_ai_suggestion")); total.put("humanOverrideTotal", count(humans, "humanDecision", "override")); total.put("humanNoActionTotal", count(humans, "humanDecision", "no_action"));
        total.put("shadowDisagreementTotal", countBoolean(events, "shadowDisagreement")); total.put("qaMissedRiskTotal", count(events, "auditResult", "missed_risk"));
        Map<String, Object> rates = new LinkedHashMap<String, Object>(); int all = decisions.size(); int reviewed = humans.size(); int retrieval = (Integer) total.get("hybridTotal") + (Integer) total.get("bm25FallbackTotal");
        rates.put("strictPathRate", ratio((Integer) total.get("strictPathTotal"), all)); rates.put("humanReviewRate", ratio((Integer) total.get("manualReviewTotal"), all));
        rates.put("aiAcceptanceRate", ratio((Integer) total.get("humanAcceptAiTotal"), reviewed)); rates.put("overrideRate", ratio((Integer) total.get("humanOverrideTotal"), reviewed)); rates.put("noActionRate", ratio((Integer) total.get("humanNoActionTotal"), reviewed)); rates.put("bm25FallbackRate", ratio((Integer) total.get("bm25FallbackTotal"), retrieval));
        Map<String, Object> result = new LinkedHashMap<String, Object>(); result.put("windowHours", window); result.put("totals", total); result.put("rates", rates); result.put("topOverrideRiskTypes", top(decisions, humans, true)); result.put("topOverrideReasons", topReasons(humans)); result.put("riskTypeMetrics", riskTypeMetrics(decisions, humans)); result.put("alerts", alerts(total, rates));
        return result;
    }

    public List<LitemallAiGovernanceObservation> sampleAutoPass(Integer limit) { return observationService.pendingQa(Math.max(1, Math.min(limit == null ? 20 : limit, 100))); }
    public boolean recordQaResult(Long id, String result) { return ("correct_pass".equals(result) || "missed_risk".equals(result)) && observationService.updateAuditResult(id, result) > 0; }

    public void maybeShadowAudit(final AiReviewAnalyzeRequest request, final AiReviewAnalyzeResponse original, final AiReviewService aiReviewService) {
        if (request == null || original == null || !"auto_close".equals(original.getRouteDecision()) || !shouldSample(request.getReviewId())) return;
        CompletableFuture.runAsync(new Runnable() { public void run() {
            try {
                AiReviewAnalyzeResponse shadow = aiReviewService.shadowAudit(request);
                Map<String, Object> governance = shadow.getReviewGovernance();
                LitemallAiGovernanceObservation row = base(governance);
                row.setEventType("shadow_audit"); row.setReviewId(original.getReviewId()); row.setRoute(original.getRouteDecision());
                row.setDecision(original.getRouteDecision()); row.setShadowDecision(value(nested(governance, "decision"), "code", shadow.getRouteDecision()));
                row.setShadowDisagreement(!row.getDecision().equals(row.getShadowDecision())); row.setEvidenceStatus(value(governance, "evidenceStatus", shadow.getEvidenceStatus()));
                row.setRiskTypesJson(json(list(governance, "riskTypes", shadow.getRiskTypes()))); row.setRetrievalMode(retrievalMode(governance)); row.setEvidenceRefs(evidenceRefs(governance)); observationService.add(row);
            } catch (Exception ignored) { /* Shadow observation must never affect the review request. */ }
        }});
    }

    private LitemallAiGovernanceObservation base(Map<String, Object> governance) { LitemallAiGovernanceObservation row = new LitemallAiGovernanceObservation(); row.setWorkflowVersion(value(governance, "workflowVersion", "agentic-review-v1")); row.setGovernanceSchemaVersion(value(governance, "governanceSchemaVersion", value(governance, "schemaVersion", "review-governance-v2"))); row.setPolicyIndexVersion(value(governance, "policyIndexVersion", "policy-rag-real-v1")); row.setEmbeddingModel(value(governance, "embeddingModel", "Qwen3-Embedding-0.6B")); return row; }
    private Map<String, Object> nested(Map<String, Object> map, String key) { Object item = map == null ? null : map.get(key); return item instanceof Map ? (Map<String, Object>) item : Collections.<String, Object>emptyMap(); }
    private String value(Map<String, Object> map, String key, String fallback) { Object item = map == null ? null : map.get(key); return item == null || String.valueOf(item).trim().length() == 0 ? fallback : String.valueOf(item); }
    private List<String> list(Map<String, Object> map, String key, List<String> fallback) { Object item = map == null ? null : map.get(key); if (item instanceof List) { List<String> result = new ArrayList<String>(); for (Object value : (List<?>) item) result.add(String.valueOf(value)); return result; } return fallback == null ? Collections.<String>emptyList() : fallback; }
    private String json(Object value) { try { return objectMapper.writeValueAsString(value); } catch (Exception ignored) { return "[]"; } }
    private String retrievalMode(Map<String, Object> governance) { Object citations = governance == null ? null : governance.get("evidenceCitations"); if (citations instanceof List && !((List) citations).isEmpty()) { Object first = ((List) citations).get(0); if (first instanceof Map) { Object retrieval = ((Map) first).get("retrieval"); if (retrieval instanceof Map) return value((Map) retrieval, "mode", "hybrid"); } } return "none"; }
    private String evidenceRefs(Map<String, Object> governance) { Object citations = governance == null ? null : governance.get("evidenceCitations"); if (!(citations instanceof List)) return ""; List<String> refs = new ArrayList<String>(); for (Object item : (List<?>) citations) { if (item instanceof Map) { Map citation=(Map)item; refs.add(value(citation,"id","E") + ":" + value(citation,"sourceName","-") + ":" + value(citation,"contentHash", "-").substring(0, Math.min(16, value(citation,"contentHash","-").length()))); } if (refs.size() == 3) break; } return String.join("|", refs); }
    private String normalizeReason(String code, String decision) { if (HUMAN_REASON_CODES.contains(code)) return code; return "accept_ai_suggestion".equals(decision) ? "OTHER" : "OTHER"; }
    private List<LitemallAiGovernanceObservation> byType(List<LitemallAiGovernanceObservation> rows, String type) { List<LitemallAiGovernanceObservation> out = new ArrayList<LitemallAiGovernanceObservation>(); for (LitemallAiGovernanceObservation row: rows) if (type.equals(row.getEventType())) out.add(row); return out; }
    private int count(List<LitemallAiGovernanceObservation> rows,String property,String expected) { int total=0; for(LitemallAiGovernanceObservation row:rows) if(expected.equals(prop(row,property))) total++; return total; }
    private int countNot(List<LitemallAiGovernanceObservation> rows,String property,String expected) { int total=0; for(LitemallAiGovernanceObservation row:rows) if(!expected.equals(prop(row,property))) total++; return total; }
    private int countPrefix(List<LitemallAiGovernanceObservation> rows,String property,String expected) { int total=0; for(LitemallAiGovernanceObservation row:rows) if(prop(row,property).startsWith(expected)) total++; return total; }
    private int countBoolean(List<LitemallAiGovernanceObservation> rows,String property) { int total=0; for(LitemallAiGovernanceObservation row:rows) if(Boolean.TRUE.equals(row.getShadowDisagreement())) total++; return total; }
    private String prop(LitemallAiGovernanceObservation row,String property) { if("route".equals(property)) return safe(row.getRoute()); if("decision".equals(property)) return safe(row.getDecision()); if("evidenceStatus".equals(property)) return safe(row.getEvidenceStatus()); if("retrievalMode".equals(property)) return safe(row.getRetrievalMode()); if("humanDecision".equals(property)) return safe(row.getHumanDecision()); if("auditResult".equals(property)) return safe(row.getAuditResult()); return ""; }
    private String safe(String value) { return value == null ? "" : value; } private double ratio(int top,int bottom) { return bottom == 0 ? 0D : Math.round(top * 10000D / bottom) / 10000D; }
    private List<Map<String,Object>> top(List<LitemallAiGovernanceObservation> decisions,List<LitemallAiGovernanceObservation> humans,boolean overrides) { Map<String,Integer> counts=new LinkedHashMap<String,Integer>(); for(LitemallAiGovernanceObservation human:humans) if("override".equals(human.getHumanDecision()) || "no_action".equals(human.getHumanDecision())) for(String risk:parseRiskTypes(human)) counts.put(risk,counts.containsKey(risk)?counts.get(risk)+1:1); return sorted(counts); }
    private List<Map<String,Object>> topReasons(List<LitemallAiGovernanceObservation> humans) { Map<String,Integer> counts=new LinkedHashMap<String,Integer>(); for(LitemallAiGovernanceObservation human:humans) if(!"accept_ai_suggestion".equals(human.getHumanDecision())) { String reason=safe(human.getHumanReasonCode()); counts.put(reason,counts.containsKey(reason)?counts.get(reason)+1:1); } return sorted(counts); }
    private List<Map<String,Object>> riskTypeMetrics(List<LitemallAiGovernanceObservation> decisions,List<LitemallAiGovernanceObservation> humans) { Map<String,int[]> values=new LinkedHashMap<String,int[]>(); for(LitemallAiGovernanceObservation row:decisions) for(String risk:parseRiskTypes(row)) { int[] a=values.containsKey(risk)?values.get(risk):new int[3]; a[0]++; if("supported".equals(row.getEvidenceStatus()))a[1]++; values.put(risk,a); } for(LitemallAiGovernanceObservation row:humans) for(String risk:parseRiskTypes(row)) { int[] a=values.containsKey(risk)?values.get(risk):new int[3]; if("override".equals(row.getHumanDecision())||"no_action".equals(row.getHumanDecision()))a[2]++; values.put(risk,a); } List<Map<String,Object>> out=new ArrayList<Map<String,Object>>(); for(Map.Entry<String,int[]> e:values.entrySet()){Map<String,Object> row=new LinkedHashMap<String,Object>();row.put("riskType",e.getKey());row.put("taskCount",e.getValue()[0]);row.put("supportedRate",ratio(e.getValue()[1],e.getValue()[0]));row.put("overrideOrNoActionCount",e.getValue()[2]);out.add(row);} return out; }
    private List<String> parseRiskTypes(LitemallAiGovernanceObservation row) { try{return objectMapper.readValue(safe(row.getRiskTypesJson()),new TypeReference<List<String>>(){});}catch(Exception ignored){return Collections.emptyList();} }
    private List<Map<String,Object>> sorted(Map<String,Integer> counts) { List<Map.Entry<String,Integer>> entries=new ArrayList<Map.Entry<String,Integer>>(counts.entrySet()); Collections.sort(entries,(a,b)->b.getValue()-a.getValue()); List<Map<String,Object>> out=new ArrayList<Map<String,Object>>(); for(Map.Entry<String,Integer> entry:entries){Map<String,Object> row=new LinkedHashMap<String,Object>();row.put("name",entry.getKey());row.put("value",entry.getValue());out.add(row);}return out; }
    private List<Map<String,Object>> alerts(Map<String,Object> totals,Map<String,Object> rates) { List<Map<String,Object>> out=new ArrayList<Map<String,Object>>(); if((Integer)totals.get("retrievalFailureTotal")>0) alert(out,"RETRIEVAL_FAILURE_OBSERVED","检测到检索失败，请检查 AI 服务与本地索引。"); if((Integer)totals.get("shadowDisagreementTotal")>0) alert(out,"SHADOW_ROUTER_DISAGREEMENT","抽样 shadow audit 发现路由差异，已进入 bad-case 复盘队列。"); return out; }
    private void alert(List<Map<String,Object>> out,String code,String message){Map<String,Object> item=new LinkedHashMap<String,Object>();item.put("code",code);item.put("message",message);out.add(item);}
    private boolean shouldSample(String reviewId) { int percent = shadowSamplePercent == null ? 5 : Math.max(0, Math.min(shadowSamplePercent, 100)); return percent > 0 && Math.floorMod(String.valueOf(reviewId).hashCode(), 100) < percent; }
}
