package org.linlinjava.litemall.wx.web;

import org.linlinjava.litemall.core.util.ResponseUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/wx/ai-demo")
@Validated
public class WxAiDemoController {
    @Value("${demo.mode.enabled:true}")
    private Boolean demoModeEnabled;
    @Value("${demo.payment.enabled:true}")
    private Boolean demoPaymentEnabled;
    @Value("${demo.shipping.enabled:true}")
    private Boolean demoShippingEnabled;
    @Value("${demo.product.main:1181000}")
    private Integer mainProductId;

    @GetMapping("/status")
    public Object status() {
        Map<String, Object> data = new HashMap<>();
        data.put("demoModeEnabled", Boolean.TRUE.equals(demoModeEnabled));
        data.put("demoPaymentEnabled", Boolean.TRUE.equals(demoPaymentEnabled));
        data.put("demoShippingEnabled", Boolean.TRUE.equals(demoShippingEnabled));
        data.put("mainProductId", mainProductId);
        data.put("message", Boolean.TRUE.equals(demoModeEnabled)
                ? "当前为答辩演示模式：演示支付不调用真实支付，演示发货不调用真实物流。"
                : "当前未开启演示模式。");
        data.put("paymentNotice", "演示支付不调用真实支付，仅推进本地订单状态。");
        data.put("shippingNotice", "演示发货不调用真实物流，仅推进本地订单状态。");
        return ResponseUtil.ok(data);
    }
}
