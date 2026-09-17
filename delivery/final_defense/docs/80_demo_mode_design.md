# v1.3 答辩演示模式设计

## 为什么需要演示模式

E-Review Agent 面向毕业答辩展示，需要稳定演示“浏览商品、提交订单、演示支付、演示发货、确认收货、发布评价、后台 Agent 巡检、风险中心和运营闭环”的完整流程。真实支付、真实物流和真实退款会引入第三方依赖，不适合答辩现场，因此系统明确提供答辩演示模式。

演示模式的目标是说明业务闭环和 AI Agent 治理能力，而不是宣称系统已经接入真实支付或真实物流。

## 配置项

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `demo.mode.enabled` | `true` | 是否启用答辩演示模式 |
| `demo.payment.enabled` | `true` | 是否启用演示支付入口 |
| `demo.shipping.enabled` | `true` | 是否启用演示发货入口 |
| `demo.product.main` | `1181000` | 主演示商品 |
| `demo.product.backup` | `1006007,1006013` | 备用演示商品 |

## 新增接口

| 接口 | 说明 |
| --- | --- |
| `GET /admin/ai/demo/status` | 后台查询演示模式状态 |
| `POST /admin/ai/demo/reset` | 返回演示重置说明，实际重置由脚本执行 |
| `GET /wx/ai-demo/status` | H5 用户端查询演示模式状态 |

## 前端展示

H5 用户端：

- 支付页显示“答辩演示模式：不调用真实支付，仅推进订单状态”；
- 演示支付按钮受 `demo.mode.enabled` 和 `demo.payment.enabled` 控制；
- 订单列表中的演示发货按钮受 `demo.mode.enabled` 和 `demo.shipping.enabled` 控制。

管理后台：

- AI 工作台总览展示当前演示模式状态；
- 展示主演示商品、AI 服务地址和数据库状态；
- 明确提示演示支付不调用真实支付，演示发货不调用真实物流。

## 答辩前检查

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-demo-mode-check.ps1
```

成功标记：

```text
DEMO_MODE_CHECK_PASS
```

## 边界说明

1. 演示支付只推进本地订单状态，不调用微信支付、支付宝或任何第三方支付。
2. 演示发货只推进本地订单状态，不调用真实物流接口。
3. 演示重置由脚本完成，后台接口不直接清空数据库。
4. 关闭演示模式后，演示支付和演示发货入口应隐藏或不可用。
5. 演示模式不改变系统“不接真实支付、不接真实物流、不接真实退款”的答辩边界。
