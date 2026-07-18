package org.linlinjava.litemall.admin.web;

import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.service.AiReviewService;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/admin/ai/rag-v2")
public class AdminAiRagV2Controller {
    @Autowired
    private AiReviewService aiReviewService;

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/status")
    public Object status() {
        return ResponseUtil.ok(aiReviewService.ragV2Status());
    }

    @RequiresPermissions("admin:ai:review:list")
    @PostMapping("/search")
    public Object search(@RequestBody Map request) {
        return ResponseUtil.ok(aiReviewService.ragV2Search(request));
    }

    @RequiresPermissions("admin:ai:review:analyze")
    @PostMapping("/evaluate")
    public Object evaluate(@RequestBody Map request) {
        return ResponseUtil.ok(aiReviewService.ragV2Evaluate(request));
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/report")
    public Object report() {
        return ResponseUtil.ok(aiReviewService.ragV2Report());
    }
}
