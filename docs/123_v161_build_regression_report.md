# v1.6.1 构建回归报告

## 结论

本轮已补充执行生产构建回归。构建命令均返回成功，但该结果不改变 v1.6.1 final gate 的真实结论：当前仍为 `V161_FINAL_GATE_BLOCKED`，不得打 `v1.6.1-realworld-multimodal-evaluation` release tag。

## 构建命令

| 模块 | 命令 | 结果 | 备注 |
| --- | --- | --- | --- |
| Java / Spring Boot | `mvn -DskipTests package` | PASS | Reactor 7 个模块全部 `SUCCESS`，最终 `BUILD SUCCESS` |
| litemall-admin | `npm run build:prod` | PASS | 构建完成，存在既有 webpack 体积警告和 `rmNotice` 导出警告 |
| litemall-vue | `npm run build:prod` | PASS | 构建完成，存在既有 Sass `@import` deprecation 与 Vant CSS order 警告 |

## Maven 摘要

- `litemall-db`: SUCCESS
- `litemall-core`: SUCCESS
- `litemall-wx-api`: SUCCESS
- `litemall-admin-api`: SUCCESS
- `litemall-all`: SUCCESS
- `litemall-all-war`: SUCCESS
- 总结果：`BUILD SUCCESS`

## 前端 warning 说明

1. `litemall-admin` 的 `rmNotice` 导出 warning 来自既有 profile notice 页面/API 边界，本轮未改业务逻辑。
2. `litemall-admin` 的 asset size warning 属于 webpack 推荐阈值提示，不导致构建失败。
3. `litemall-vue` 的 Sass legacy JS API、`@import` deprecation 和 Vant CSS order warning 属于旧 Vue 2/Vant 2 技术栈的兼容性提示，本轮按“不大版本升级依赖”的约束保留。

## 与 v1.6.1 final gate 的关系

构建通过只能证明当前代码可以打包，不能证明真实外部文本集、真实图文集、VLM 推理和 SFT 准入已经完成。release 仍受以下 gate 阻塞：

- `REALWORLD_EXTERNAL_EVAL_BLOCKED`
- `MULTIMODAL_VLM_EVAL_BLOCKED`
- `REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED`
- `SFT_DATA_NOT_READY`
- `VLM_SFT_DATA_NOT_READY`

因此当前版本建议继续作为 v1.6.1 审计与多模态接入准备分支保留，不建议打 release tag。
