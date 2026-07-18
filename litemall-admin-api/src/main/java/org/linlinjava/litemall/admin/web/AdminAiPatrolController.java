package org.linlinjava.litemall.admin.web;

import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.annotation.RequiresPermissionsDesc;
import org.linlinjava.litemall.admin.service.AiReviewPatrolService;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/admin/ai/patrol")
@Validated
public class AdminAiPatrolController {
    @Autowired
    private AiReviewPatrolService patrolService;

    @RequiresPermissions("admin:ai:review:list")
    @RequiresPermissionsDesc(menu = {"AI工作台", "Agent巡检中心"}, button = "查询")
    @GetMapping("/status")
    public Object status() {
        return ResponseUtil.ok(patrolService.status());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @RequiresPermissionsDesc(menu = {"AI工作台", "Agent巡检中心"}, button = "立即巡检")
    @PostMapping("/run-once")
    public Object runOnce() {
        return ResponseUtil.ok(patrolService.runOnce());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/enable")
    public Object enable() {
        patrolService.enable();
        return ResponseUtil.ok(patrolService.status());
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/disable")
    public Object disable() {
        patrolService.disable();
        return ResponseUtil.ok(patrolService.status());
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/logs")
    public Object logs() {
        return ResponseUtil.ok(patrolService.logs());
    }
}
