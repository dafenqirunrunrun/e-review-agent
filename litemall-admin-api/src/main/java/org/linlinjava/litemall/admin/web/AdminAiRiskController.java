package org.linlinjava.litemall.admin.web;

import org.apache.commons.lang3.StringUtils;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.annotation.RequiresPermissionsDesc;
import org.linlinjava.litemall.admin.service.AiRiskTaskService;
import org.linlinjava.litemall.admin.service.GovernanceQualityService;
import org.linlinjava.litemall.admin.vo.AiRiskHumanReviewRequest;
import org.linlinjava.litemall.admin.vo.AiRiskHumanReviewResult;
import org.linlinjava.litemall.admin.vo.AiRiskStatusRequest;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/ai/risk")
@Validated
public class AdminAiRiskController {
    @Autowired
    private AiRiskTaskService riskTaskService;

    @Autowired
    private GovernanceQualityService governanceQualityService;

    @RequiresPermissions("admin:ai:review:list")
    @RequiresPermissionsDesc(menu = {"AI工作台", "风险评论中心"}, button = "查询")
    @GetMapping("/list")
    public Object list(@RequestParam(value = "riskLevel", required = false) String riskLevel,
                       @RequestParam(value = "riskType", required = false) String riskType,
                       @RequestParam(value = "status", required = false) String status,
                       @RequestParam(value = "page", defaultValue = "1") Integer page,
                       @RequestParam(value = "limit", defaultValue = "10") Integer limit) {
        List<LitemallAiReviewRiskTask> tasks = riskTaskService.list(riskLevel, riskType, status, page, limit);
        return ResponseUtil.okList(tasks);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/detail/{id}")
    public Object detail(@PathVariable("id") Integer id) {
        return ResponseUtil.ok(riskTaskService.detail(id));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/update-status")
    public Object updateStatus(@RequestBody AiRiskStatusRequest request) {
        if (request == null || request.getId() == null || StringUtils.isBlank(request.getStatus())) {
            return ResponseUtil.badArgumentValue();
        }
        riskTaskService.updateStatus(request.getId(), request.getStatus(), request.getHandler(), request.getHandleNote());
        return ResponseUtil.ok();
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/close")
    public Object close(@RequestBody AiRiskStatusRequest request) {
        if (request == null || request.getId() == null) {
            return ResponseUtil.badArgumentValue();
        }
        riskTaskService.updateStatus(request.getId(), "closed", request.getHandler(), request.getHandleNote());
        return ResponseUtil.ok();
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/human-review")
    public Object humanReview(@RequestBody AiRiskHumanReviewRequest request) {
        if (request == null || request.getId() == null || StringUtils.isBlank(request.getHumanDecision())) {
            return ResponseUtil.badArgumentValue();
        }
        AiRiskHumanReviewResult result = riskTaskService.humanReview(request);
        if (result == null) {
            return ResponseUtil.badArgumentValue();
        }
        return ResponseUtil.ok(result);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/summary")
    public Object summary() {
        return ResponseUtil.ok(riskTaskService.summary());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/quality-metrics")
    public Object qualityMetrics(@RequestParam(value = "hours", required = false) Integer hours) {
        return ResponseUtil.ok(governanceQualityService.metrics(hours));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/qa-sample")
    public Object qaSample(@RequestParam(value = "limit", required = false) Integer limit) {
        return ResponseUtil.ok(governanceQualityService.sampleAutoPass(limit));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/qa-result")
    public Object qaResult(@RequestBody Map<String, Object> request) {
        if (request == null || request.get("id") == null || request.get("auditResult") == null) {
            return ResponseUtil.badArgumentValue();
        }
        Long id;
        try { id = Long.valueOf(String.valueOf(request.get("id"))); } catch (Exception e) { return ResponseUtil.badArgumentValue(); }
        return governanceQualityService.recordQaResult(id, String.valueOf(request.get("auditResult"))) ? ResponseUtil.ok() : ResponseUtil.badArgumentValue();
    }
}
