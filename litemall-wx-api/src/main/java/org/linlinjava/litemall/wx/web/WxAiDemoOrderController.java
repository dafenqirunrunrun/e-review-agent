package org.linlinjava.litemall.wx.web;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.linlinjava.litemall.core.task.TaskService;
import org.linlinjava.litemall.core.util.JacksonUtil;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.LitemallOrder;
import org.linlinjava.litemall.db.service.LitemallOrderService;
import org.linlinjava.litemall.db.util.OrderUtil;
import org.linlinjava.litemall.wx.annotation.LoginUser;
import org.linlinjava.litemall.wx.task.OrderUnpaidTask;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/wx/ai-demo/order")
@Validated
public class WxAiDemoOrderController {
    private final Log logger = LogFactory.getLog(WxAiDemoOrderController.class);

    @Autowired
    private LitemallOrderService orderService;

    @Autowired
    private TaskService taskService;

    @Value("${demo.mode.enabled:true}")
    private Boolean demoModeEnabled;
    @Value("${demo.payment.enabled:true}")
    private Boolean demoPaymentEnabled;
    @Value("${demo.shipping.enabled:true}")
    private Boolean demoShippingEnabled;

    @PostMapping("mock-pay")
    @Transactional
    public Object mockPay(@LoginUser Integer userId, @RequestBody String body) {
        if (!Boolean.TRUE.equals(demoModeEnabled) || !Boolean.TRUE.equals(demoPaymentEnabled)) {
            return ResponseUtil.fail(743, "当前未开启答辩演示支付模式");
        }
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        Integer orderId = JacksonUtil.parseInteger(body, "orderId");
        if (orderId == null) {
            return ResponseUtil.badArgument();
        }
        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.fail(742, "Order not found or not owned by current user");
        }
        if (!OrderUtil.isCreateStatus(order)) {
            return ResponseUtil.fail(740, "Only unpaid orders can use demo payment");
        }

        order.setOrderStatus(OrderUtil.STATUS_PAY);
        order.setPayId("AI-DEMO-PAY-" + order.getOrderSn());
        order.setPayTime(LocalDateTime.now());
        if (orderService.updateWithOptimisticLocker(order) == 0) {
            return ResponseUtil.updatedDateExpired();
        }

        taskService.removeTask(new OrderUnpaidTask(order.getId()));
        logger.info("AI demo mock pay success, orderId=" + order.getId() + ", userId=" + userId);
        return ResponseUtil.ok(result(order));
    }

    @PostMapping("mock-ship")
    @Transactional
    public Object mockShip(@LoginUser Integer userId, @RequestBody String body) {
        if (!Boolean.TRUE.equals(demoModeEnabled) || !Boolean.TRUE.equals(demoShippingEnabled)) {
            return ResponseUtil.fail(744, "当前未开启答辩演示发货模式");
        }
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        Integer orderId = JacksonUtil.parseInteger(body, "orderId");
        if (orderId == null) {
            return ResponseUtil.badArgument();
        }
        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.fail(742, "Order not found or not owned by current user");
        }
        if (!OrderUtil.isPayStatus(order)) {
            return ResponseUtil.fail(741, "Only paid orders can use demo shipping");
        }

        order.setOrderStatus(OrderUtil.STATUS_SHIP);
        order.setShipChannel("AI-DEMO");
        order.setShipSn("AI-DEMO-SHIP-" + order.getOrderSn());
        order.setShipTime(LocalDateTime.now());
        if (orderService.updateWithOptimisticLocker(order) == 0) {
            return ResponseUtil.updatedDateExpired();
        }

        logger.info("AI demo mock ship success, orderId=" + order.getId() + ", userId=" + userId);
        return ResponseUtil.ok(result(order));
    }

    private Map<String, Object> result(LitemallOrder order) {
        Map<String, Object> data = new HashMap<>();
        data.put("orderId", order.getId());
        data.put("orderSn", order.getOrderSn());
        data.put("orderStatus", order.getOrderStatus());
        data.put("orderStatusText", OrderUtil.orderStatusText(order));
        return data;
    }
}
