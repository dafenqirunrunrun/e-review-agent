package org.linlinjava.litemall.admin.web;

import org.apache.commons.lang3.StringUtils;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.annotation.RequiresPermissionsDesc;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.LitemallAiDemoReview;
import org.linlinjava.litemall.db.service.LitemallAiDemoReviewService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/ai/demo-review")
@Validated
public class AdminAiDemoReviewController {
    @Autowired
    private LitemallAiDemoReviewService demoReviewService;

    @RequiresPermissions("admin:ai:review:analyze")
    @RequiresPermissionsDesc(menu = {"AI工作台", "模拟评论提交"}, button = "提交")
    @PostMapping("/create")
    public Object create(@RequestBody LitemallAiDemoReview review) {
        if (review == null || review.getProductId() == null || StringUtils.isBlank(review.getProductName()) || StringUtils.isBlank(review.getReviewText())) {
            return ResponseUtil.badArgumentValue();
        }
        demoReviewService.add(review);
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("id", review.getId());
        data.put("analysisStatus", review.getAnalysisStatus());
        data.put("message", "评论提交成功，等待 Agent 巡检分析");
        return ResponseUtil.ok(data);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/list")
    public Object list(@RequestParam(value = "productId", required = false) Integer productId,
                       @RequestParam(value = "analysisStatus", required = false) String analysisStatus,
                       @RequestParam(value = "page", defaultValue = "1") Integer page,
                       @RequestParam(value = "limit", defaultValue = "10") Integer limit) {
        List<LitemallAiDemoReview> reviews = demoReviewService.querySelective(productId, analysisStatus, page, limit);
        return ResponseUtil.okList(reviews);
    }

    @RequiresPermissions("admin:ai:review:list")
    @GetMapping("/pending")
    public Object pending(@RequestParam(value = "limit", defaultValue = "20") Integer limit) {
        return ResponseUtil.ok(demoReviewService.queryPending(limit));
    }
}
