package org.linlinjava.litemall.admin.web;

import org.apache.commons.lang3.StringUtils;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.annotation.RequiresPermissionsDesc;
import org.linlinjava.litemall.admin.service.AiOperationService;
import org.linlinjava.litemall.admin.vo.AiOperationHandleRequest;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;
import org.linlinjava.litemall.db.service.LitemallAiReviewRiskTaskService;
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
@RequestMapping("/admin/ai/operation")
@Validated
public class AdminAiOperationController {
    @Autowired
    private AiOperationService operationService;

    @Autowired
    private LitemallAiReviewRiskTaskService riskTaskService;

    @RequiresPermissions("admin:ai:review:list")
    @RequiresPermissionsDesc(menu = {"AI工作台", "运营处理中心"}, button = "查询")
    @GetMapping("/list")
    public Object list(@RequestParam(value = "status", required = false) String status,
                       @RequestParam(value = "page", defaultValue = "1") Integer page,
                       @RequestParam(value = "limit", defaultValue = "10") Integer limit) {
        List<LitemallAiReviewRiskTask> tasks = operationService.list(status, page, limit);
        return ResponseUtil.okList(tasks);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/detail/{id}")
    public Object detail(@PathVariable("id") Integer id) {
        return ResponseUtil.ok(operationService.detail(id));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/handle")
    public Object handle(@RequestBody AiOperationHandleRequest request) {
        if (request == null || request.getRiskTaskId() == null || StringUtils.isBlank(request.getNewStatus())) {
            return ResponseUtil.badArgumentValue();
        }
        if (StringUtils.isBlank(request.getActionType())) {
            request.setActionType("update_status");
        }
        if (StringUtils.isBlank(request.getOperator())) {
            request.setOperator("admin");
        }
        if (riskTaskService.findById(request.getRiskTaskId()) == null) {
            return ResponseUtil.badArgumentValue();
        }
        operationService.handle(request);
        return ResponseUtil.ok();
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/logs/{riskTaskId}")
    public Object logs(@PathVariable("riskTaskId") Integer riskTaskId) {
        return ResponseUtil.ok(operationService.logs(riskTaskId));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/summary")
    public Object summary() {
        return ResponseUtil.ok(operationService.summary());
    }
}
