package org.linlinjava.litemall.admin.web;

import org.apache.shiro.SecurityUtils;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.service.DocumentJobService;
import org.linlinjava.litemall.admin.service.AiReviewService;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.LitemallAdmin;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/admin/ai/documents")
public class AdminDocumentController {
    private final DocumentJobService jobs;
    private final org.linlinjava.litemall.admin.service.DocumentIndexService indexes;
    private final AiReviewService aiReviewService;
    public AdminDocumentController(DocumentJobService jobs,
            org.linlinjava.litemall.admin.service.DocumentIndexService indexes,
            AiReviewService aiReviewService) {
        this.jobs = jobs;
        this.indexes = indexes;
        this.aiReviewService = aiReviewService;
    }

    private String operator() {
        LitemallAdmin admin = (LitemallAdmin) SecurityUtils.getSubject().getPrincipal();
        return admin.getUsername();
    }

    @GetMapping
    @RequiresPermissions("admin:ai:review:list")
    public Object list(@RequestParam(defaultValue="1") int page, @RequestParam(defaultValue="20") int limit) {
        return ResponseUtil.ok(jobs.list(page, limit));
    }

    @PostMapping
    @RequiresPermissions("admin:ai:review:analyze")
    public Object upload(@RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue="") String sourceName, @RequestParam(defaultValue="") String sourceUrl,
            @RequestParam(defaultValue="reference") String usageType) throws Exception {
        return ResponseUtil.ok(jobs.upload(file, sourceName, sourceUrl, usageType, operator()));
    }

    @GetMapping("/{id}")
    @RequiresPermissions("admin:ai:review:list")
    public Object detail(@PathVariable String id) throws Exception { return ResponseUtil.ok(jobs.preview(id)); }

    @PostMapping("/{id}/retry")
    @RequiresPermissions("admin:ai:review:analyze")
    public Object retry(@PathVariable String id) { return ResponseUtil.ok(jobs.retry(id)); }

    @DeleteMapping("/{id}")
    @RequiresPermissions("admin:ai:review:analyze")
    public Object remove(@PathVariable String id) { return ResponseUtil.ok(jobs.remove(id, operator())); }

    @GetMapping("/index/status")
    @RequiresPermissions("admin:ai:review:list")
    public Object indexStatus() {
        java.util.Map<String, Object> summary = indexes.summary();
        try {
            summary.put("runtime", aiReviewService.policyIndexRuntime());
        } catch (AiReviewService.AiReviewServiceException failure) {
            java.util.Map<String, Object> unavailable = new java.util.LinkedHashMap<String, Object>();
            unavailable.put("status", "unavailable");
            unavailable.put("reloadStatus", "unknown");
            summary.put("runtime", unavailable);
        }
        return ResponseUtil.ok(summary);
    }

    @PostMapping("/index/build")
    @RequiresPermissions("admin:ai:review:analyze")
    public Object buildIndex() throws Exception { return ResponseUtil.ok(indexes.createCandidate(operator())); }

    @PostMapping("/index/{id}/publish")
    @RequiresPermissions("admin:ai:review:analyze")
    public Object publishIndex(@PathVariable String id) throws Exception { return ResponseUtil.ok(indexes.publish(id, operator())); }

    @PostMapping("/index/{id}/rollback")
    @RequiresPermissions("admin:ai:review:analyze")
    public Object rollbackIndex(@PathVariable String id) throws Exception { return ResponseUtil.ok(indexes.rollback(id, operator())); }

    @PostMapping("/index/base/restore")
    @RequiresPermissions("admin:ai:review:analyze")
    public Object restoreBaseIndex() throws Exception { return ResponseUtil.ok(indexes.restoreBase(operator())); }

    @ExceptionHandler(IllegalArgumentException.class)
    public Object invalid(IllegalArgumentException failure) { return ResponseUtil.fail(401, failure.getMessage()); }
}
