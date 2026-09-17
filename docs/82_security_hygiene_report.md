# v1.3 安全与隐私自检报告

## 目标

本报告用于说明 v1.3 的交付安全边界。毕业设计项目不应在文档、脚本或前端页面中暴露 API Key、数据库密码、用户私有路径或不实能力声明。

## 检查命令

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-security-hygiene-check.ps1
```

成功标记：

```text
SECURITY_HYGIENE_CHECK_PASS
```

## 检查范围

- `README.md`
- `docs/**/*.md`
- `scripts/**/*.ps1`
- `ai-service/**/*.py`
- `litemall-admin/src/**/*.vue`
- `litemall-admin/src/**/*.js`
- `litemall-vue/src/**/*.vue`
- `litemall-vue/src/**/*.js`
- `litemall-admin-api/src/main/java/**/*.java`
- `litemall-wx-api/src/main/java/**/*.java`

## 检查内容

| 类别 | 说明 |
| --- | --- |
| 密钥 | 检查 OpenAI Key、长 token 和类似密钥文本 |
| 数据库密码 | 检查已知本地数据库密码是否出现在交付脚本或文档中 |
| 本机隐私路径 | 检查用户目录和 file URI |
| 外部能力声明 | 检查是否误称已经接入 Qdrant、外部 MCP 或真实支付 |
| SaaS 夸大 | 检查是否脱离毕业设计原型边界宣称生产级 SaaS |

## 允许内容

1. `localhost` 和 `127.0.0.1` 本地演示地址。
2. 接口路径，例如 `/admin/ai/demo/status`。
3. 明确写作“未接入”“不声明”“不代表”的边界说明。
4. 检查脚本内部用于检测风险词的规则文本。

## 当前处理

- 新增数据库脚本统一优先读取参数、环境变量或本地 Spring 配置，不在文档中写数据库密码。
- 已将旧演示商品种子脚本改为通过 `MYSQL_PWD` 临时环境变量调用 MySQL，避免命令行打印密码。
- v1.3 文档持续强调：不接真实支付、不接真实物流、不接真实退款、不强制外部 API Key、不接外部 MCP 服务、不接 Qdrant。

## 结论

安全卫生检查作为 v1.3 最终验收门禁之一。只有输出 `SECURITY_HYGIENE_CHECK_PASS` 后，才建议进入最终 PPT、录屏和论文定稿。
