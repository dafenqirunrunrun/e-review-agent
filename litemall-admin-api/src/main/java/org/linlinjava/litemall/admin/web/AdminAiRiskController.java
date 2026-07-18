package org.linlinjava.litemall.admin.web;

import org.apache.commons.lang3.StringUtils;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.annotation.RequiresPermissionsDesc;
import org.linlinjava.litemall.admin.service.AiRiskTaskService;
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

@RestController
@RequestMapping("/admin/ai/risk")
@Validated
public class AdminAiRiskController {
    @Autowired
    private AiRiskTaskService riskTaskService;

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

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/summary")
    public Object summary() {
        return ResponseUtil.ok(riskTaskService.summary());
    }
}
