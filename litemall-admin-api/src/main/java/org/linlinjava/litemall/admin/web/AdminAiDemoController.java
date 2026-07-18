package org.linlinjava.litemall.admin.web;

import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.linlinjava.litemall.admin.annotation.RequiresPermissionsDesc;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/admin/ai/demo")
@Validated
public class AdminAiDemoController {
    @Value("${demo.mode.enabled:true}")
    private Boolean demoModeEnabled;
    @Value("${demo.payment.enabled:true}")
    private Boolean demoPaymentEnabled;
    @Value("${demo.shipping.enabled:true}")
    private Boolean demoShippingEnabled;
    @Value("${demo.product.main:1181000}")
    private Integer mainProductId;
    @Value("${demo.product.backup:1006007,1006013}")
    private String backupProductIds;
    @Value("${ai.service.base-url:http://127.0.0.1:8008}")
    private String aiServiceBaseUrl;

    @RequiresPermissions("admin:ai:review:list")
    @RequiresPermissionsDesc(menu = {"AI工作台", "演示模式"}, button = "查询")
    @GetMapping("/status")
    public Object status() {
        return ResponseUtil.ok(statusData());
    }

    @RequiresPermissions("admin:ai:review:list")
    @RequiresPermissionsDesc(menu = {"AI工作台", "演示模式"}, button = "重置")
    @PostMapping("/reset")
    public Object reset() {
        Map<String, Object> data = statusData();
        data.put("resetAction", "请使用 scripts/e-review-demo-data-reset.ps1 重置本地演示数据。后台接口仅提供答辩演示状态确认，不直接清空数据库。");
        data.put("result", "DEMO_RESET_READY");
        return ResponseUtil.ok(data);
    }

    private Map<String, Object> statusData() {
        Map<String, Object> data = new HashMap<>();
        data.put("demoModeEnabled", Boolean.TRUE.equals(demoModeEnabled));
        data.put("demoPaymentEnabled", Boolean.TRUE.equals(demoPaymentEnabled));
        data.put("demoShippingEnabled", Boolean.TRUE.equals(demoShippingEnabled));
        data.put("mainProductId", mainProductId);
        data.put("backupProductIds", Arrays.asList(backupProductIds.split(",")));
        data.put("aiServiceBaseUrl", aiServiceBaseUrl);
        data.put("database", "litemall");
        data.put("message", Boolean.TRUE.equals(demoModeEnabled)
                ? "当前为答辩演示模式：演示支付不调用真实支付，演示发货不调用真实物流。"
                : "当前未开启演示模式：演示支付和演示发货入口应隐藏或不可用。");
        data.put("boundary", "本系统不接真实支付、真实物流、真实退款、外部 MCP 服务或外部向量数据库。");
        return data;
    }
}
