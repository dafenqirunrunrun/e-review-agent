package org.linlinjava.litemall.admin.web;

import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.LitemallAiCaseKnowledge;
import org.linlinjava.litemall.db.service.LitemallAiCaseKnowledgeService;
import org.linlinjava.litemall.db.service.LitemallAiCaseRetrievalLogService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/admin/ai/case")
@Validated
public class AdminAiCaseController {
    @Autowired
    private LitemallAiCaseKnowledgeService caseKnowledgeService;

    @Autowired
    private LitemallAiCaseRetrievalLogService retrievalLogService;

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/list")
    public Object list(@RequestParam(value = "keyword", required = false) String keyword,
                       @RequestParam(value = "riskLevel", required = false) String riskLevel,
                       @RequestParam(value = "sentimentLabel", required = false) String sentimentLabel,
                       @RequestParam(value = "page", defaultValue = "1") Integer page,
                       @RequestParam(value = "limit", defaultValue = "10") Integer limit) {
        List<LitemallAiCaseKnowledge> cases = caseKnowledgeService.querySelective(keyword, riskLevel, sentimentLabel, page, limit);
        return ResponseUtil.okList(cases);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/detail/{id}")
    public Object detail(@PathVariable("id") Integer id) {
        LitemallAiCaseKnowledge item = caseKnowledgeService.findById(id);
        if (item == null) {
            return ResponseUtil.badArgumentValue();
        }
        return ResponseUtil.ok(item);
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/build-from-history")
    public Object buildFromHistory() {
        return ResponseUtil.ok(caseKnowledgeService.buildFromHistory());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/rebuild-from-history")
    public Object rebuildFromHistory() {
        return ResponseUtil.ok(caseKnowledgeService.buildFromHistory());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/retrieval/logs")
    public Object retrievalLogs() {
        return ResponseUtil.okList(retrievalLogService.recent());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/stats")
    public Object stats() {
        return ResponseUtil.ok(caseKnowledgeService.stats());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/retrieve")
    public Object retrieve(@RequestParam(value = "queryText", required = false) String queryText,
                           @RequestParam(value = "query", required = false) String query,
                           @RequestParam(value = "productId", required = false) Integer productId,
                           @RequestParam(value = "riskTypes", required = false) String riskTypes,
                           @RequestParam(value = "riskType", required = false) String riskType,
                           @RequestParam(value = "sentimentLabel", required = false) String sentimentLabel,
                           @RequestParam(value = "topK", defaultValue = "3") Integer topK,
                           @RequestParam(value = "sourceType", required = false) String sourceType,
                           @RequestParam(value = "sourceId", required = false) Integer sourceId) {
        if ((queryText == null || queryText.trim().length() == 0) && query != null) {
            queryText = query;
        }
        if ((riskTypes == null || riskTypes.trim().length() == 0) && riskType != null) {
            riskTypes = riskType;
        }
        return ResponseUtil.ok(caseKnowledgeService.retrieveSimilarCases(queryText, productId, riskTypes,
                sentimentLabel, topK, null, sourceType, sourceId));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/retrieve-v2")
    public Object retrieveV2(@RequestParam(value = "query", required = false) String query,
                             @RequestParam(value = "riskType", required = false) String riskType,
                             @RequestParam(value = "goodsId", required = false) Integer goodsId,
                             @RequestParam(value = "strategy", defaultValue = "hybrid") String strategy,
                             @RequestParam(value = "topK", defaultValue = "5") Integer topK) {
        return ResponseUtil.ok(caseKnowledgeService.retrieveV2(query, riskType, goodsId, strategy, topK));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/retrieve-compare")
    public Object retrieveCompare(@RequestParam(value = "query", required = false) String query,
                                  @RequestParam(value = "riskType", required = false) String riskType,
                                  @RequestParam(value = "goodsId", required = false) Integer goodsId,
                                  @RequestParam(value = "topK", defaultValue = "5") Integer topK) {
        return ResponseUtil.ok(caseKnowledgeService.retrieveCompare(query, riskType, goodsId, topK));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/retrieval/failures")
    public Object retrievalFailures() {
        return ResponseUtil.ok(caseKnowledgeService.retrievalFailures());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/retrieval/metrics")
    public Object retrievalMetrics() {
        return ResponseUtil.ok(caseKnowledgeService.retrievalMetrics());
    }
}
