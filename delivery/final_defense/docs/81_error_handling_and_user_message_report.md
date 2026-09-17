# v1.3 错误兜底与用户提示检查报告

## 目标

本报告用于说明 v1.3 对答辩现场错误提示的检查策略。系统应避免在页面上直接暴露粗糙工程错误、堆栈、本机路径、`undefined`、`null`、`NaN` 或不可理解的英文异常。

## 已完成处理

1. 后台请求拦截器的 502 提示从“系统内部错误”调整为“服务暂时不可用，请稍后重试或先切换到备用演示路径”。
2. 后台网络超时提示调整为“服务连接暂时不可用，请确认本地服务已启动后重试”。
3. H5 演示支付和演示发货保留中文提示，并受演示模式开关控制。
4. 新增脚本 `scripts/e-review-error-message-check.ps1`，扫描前端、后端和 AI 服务源码中的高风险用户可见错误文本。

## 检查命令

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-error-message-check.ps1
```

成功标记：

```text
ERROR_MESSAGE_CHECK_PASS
```

## 检查范围

- `litemall-admin/src/**/*.vue`
- `litemall-admin/src/**/*.js`
- `litemall-vue/src/**/*.vue`
- `litemall-vue/src/**/*.js`
- `litemall-admin-api/src/main/java/**/*.java`
- `litemall-wx-api/src/main/java/**/*.java`
- `ai-service/**/*.py`

## 检查重点

| 检查项 | 说明 |
| --- | --- |
| 乱码字符 | 检查 `U+FFFD` 替换字符和典型乱码占位 |
| 粗糙错误提示 | 检查“系统内部错误”等不适合答辩现场展示的提示 |
| 堆栈暴露 | 检查 `stacktrace` 等文本 |
| 本机路径 | 检查用户目录和 file URI |
| 友好提示 | 服务不可用时给出中文可操作建议 |

## 结论

v1.3 将错误提示检查纳入最终毕业答辩验收脚本。该检查不替代完整异常处理体系，但可以防止答辩现场出现明显影响观感的工程化错误文案。
