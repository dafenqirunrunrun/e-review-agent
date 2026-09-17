# E-Review Agent 最终答辩交付索引

## v1.4 体验收口材料

v1.4 新增以下答辩材料：

- docs/90_ai_product_ux_audit.md：AI 工作台体验审计。
- docs/91_ai_workbench_information_architecture.md：5 个主入口的信息架构说明。
- docs/92_ai_workbench_onboarding_design.md：新手引导和 5 分钟演示设计。
- docs/93_redundant_module_consolidation_report.md：冗余模块合并说明。
- docs/94_v14_browser_ux_regression_report.md：浏览器 UX 回归记录。
- docs/95_v14_ai_product_ux_refinement_report.md：v1.4 体验收口总报告。

演示主线建议以智能治理首页开始，再进入评论治理流程、运行观测与评估和平台治理设置。交付检查类能力继续通过脚本和文档完成，不作为后台业务菜单展示。

## 1. 推荐演示版本

当前推荐答辩版本为 `v1.3-graduation-defense-readiness`。该版本定位为毕业设计封版前的稳定演示版本，重点强化一键启动、数据库备份恢复、演示模式、错误提示、安全卫生、论文材料、交付目录、浏览器回归和最终验收脚本。

## 2. 当前分支与 tag 建议

| 项目 | 内容 |
| --- | --- |
| 当前开发分支 | `release/v1.3-graduation-defense-readiness` |
| 建议 tag | `v1.3-graduation-defense-readiness` |
| tag 前置条件 | 全量构建、脚本验收、浏览器回归和最终交付包检查均通过 |

旧 tag 不应移动或覆盖。若最终验收失败，应修复后重新执行验收，不建议在失败状态下打 tag。

## 3. 一键启动与检查脚本

| 脚本 | 作用 | 成功标记 |
| --- | --- | --- |
| `scripts/e-review-start-all.ps1` | 启动 AI 服务、wx-api、admin-api、H5 用户端和管理后台 | `START_ALL_PASS` |
| `scripts/e-review-stop-all.ps1` | 停止演示相关服务 | `STOP_ALL_PASS` |
| `scripts/e-review-restart-all.ps1` | 重启演示相关服务 | `RESTART_ALL_PASS` |
| `scripts/e-review-check-all.ps1` | 检查端口、HTTP 状态和关键接口 | `CHECK_ALL_PASS` |
| `scripts/e-review-open-demo-pages.ps1` | 打开 H5 用户端和管理后台 | `OPEN_DEMO_PAGES_READY` |

## 4. 数据库备份与演示数据脚本

| 脚本 | 作用 | 成功标记 |
| --- | --- | --- |
| `scripts/e-review-db-backup.ps1` | 备份当前数据库 | `DB_BACKUP_PASS` |
| `scripts/e-review-db-restore.ps1` | 从指定 SQL 文件恢复数据库 | `DB_RESTORE_PASS` |
| `scripts/e-review-demo-data-reset.ps1` | 重置演示商品和演示数据 | `DEMO_DATA_RESET_PASS` |
| `scripts/e-review-db-check.ps1` | 检查核心表、迁移字段和演示商品 | `DB_CHECK_PASS` |

数据库脚本不在文档中写入数据库密码。答辩前建议先备份，再重置演示数据，最后执行数据库检查。

## 5. PPT 与录屏材料位置

| 材料 | 推荐位置 | 说明 |
| --- | --- | --- |
| PPT 初稿 | `delivery/final_defense/docs/` | 可放置最终答辩 PPT 或 PPT 导出说明 |
| 录屏文件 | `delivery/final_defense/reports/` | 可放置录屏清单或压缩包说明 |
| 截图素材 | `delivery/final_defense/screenshots/` | 按 `docs/17_screenshot_plan.md` 命名保存 |

当前仓库不强制提交大体积视频文件。若录屏体积较大，可在提交材料时单独附带。

## 6. 核心截图清单

核心截图以 `docs/17_screenshot_plan.md` 为准，建议优先截图：

1. H5 用户端首页。
2. 商品详情页。
3. 演示支付成功按钮。
4. 订单列表演示发货与确认收货。
5. 评价提交页。
6. 管理后台 AI Dashboard。
7. 商品评论列表真实评价。
8. Agent 巡检中心。
9. 风险评论中心。
10. 运营处理中心。
11. Agent Trace。
12. RAG 质量评估。
13. 最终脚本 PASS 结果。

## 7. 核心测试报告

| 文档 | 用途 |
| --- | --- |
| `docs/25_fullstack_integration_test_report.md` | 全栈集成测试说明 |
| `docs/37_final_test_report.md` | 最终测试报告 |
| `docs/85_thesis_testing_material.md` | 论文测试章节材料 |
| `docs/89_final_browser_regression_report.md` | 最终浏览器回归报告 |

测试报告应以实际命令输出为依据，不伪造未执行的测试结论。

## 8. 答辩 Q&A 与论文材料

| 文档 | 用途 |
| --- | --- |
| `docs/47_defense_qna.md` | 答辩问答准备 |
| `docs/83_thesis_system_design_material.md` | 系统设计章节材料 |
| `docs/84_thesis_implementation_material.md` | 系统实现章节材料 |
| `docs/85_thesis_testing_material.md` | 系统测试章节材料 |
| `docs/86_thesis_deployment_material.md` | 系统部署章节材料 |
| `docs/87_thesis_innovation_summary.md` | 创新点总结 |

## 9. 系统边界说明

答辩时建议明确说明：

1. 演示支付只推进订单状态，不接真实支付。
2. 演示发货只推进订单状态，不接真实物流。
3. 系统不实现真实退款闭环。
4. AI 服务可使用本地规则模型运行，不强制外部 API Key。
5. RAG 质量评估使用本地案例和质量检查，不依赖外部向量数据库。
6. 本地 MCP 风格描述仅代表本地工具协议结构，不表示接入外部 MCP 服务。

## 10. 最终交付目录

最终交付目录为：

```text
delivery/final_defense/
```

该目录由 `scripts/e-review-build-final-delivery-package.ps1` 生成和检查。脚本成功时输出：

```text
FINAL_DELIVERY_PACKAGE_PASS
```

## 11. 答辩前注意事项

1. 先执行服务检查，再录屏。
2. 先重置演示数据，再演示 H5 购买评价闭环。
3. 若 Dashboard 数据没有变化，先执行 Agent 巡检，再刷新页面。
4. 若 H5 下单失败，先检查演示商品库存。
5. 若脚本失败，不要跳过，应根据失败模块修复后重新执行。
