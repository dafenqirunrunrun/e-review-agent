# E-Review Agent 系统部署章节材料

## 1. 部署目标

E-Review Agent 的部署目标是支持毕业设计答辩现场稳定启动、稳定演示和稳定恢复。系统采用本地多服务部署方式，将 AI 服务、用户端后端、管理端后端、H5 用户端、管理后台前端和 MySQL 数据库部署在同一台演示机器上。该部署方式减少外部依赖，便于答辩现场快速排查问题。

部署方案明确区分演示能力和真实业务能力。演示支付和演示发货只用于推进订单状态，不调用真实支付或真实物流服务。AI 服务可以在本地以规则模型运行，不强制要求外部 API Key。

## 2. 运行环境

系统运行环境包括：

| 组件 | 用途 |
| --- | --- |
| JDK 8 | 运行 Spring Boot 后端服务 |
| Maven | 构建 Java 多模块项目 |
| Node.js / npm | 运行和构建 Vue 前端项目 |
| Python | 运行 FastAPI AI 服务和测试 |
| MySQL | 保存商城、评论、AI 分析和智能体数据 |
| PowerShell | 执行一键启动、检查、备份和验收脚本 |
| Chrome / Edge | 进行真实浏览器回归测试 |

部署环境以本地演示为主，所有服务地址均使用 `localhost` 或 `127.0.0.1`。交付文档不包含数据库密码和用户私密路径。

## 3. 服务端口

系统默认端口如下：

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| AI 服务 | 8008 | FastAPI 健康检查和评价分析 |
| wx-api | 8080 | H5 用户端后端接口 |
| admin-api | 8083 | 管理后台后端接口 |
| H5 用户端 | 6255 | 顾客端浏览器入口 |
| 管理后台 | 9527 | 管理员端浏览器入口 |
| MySQL | 3306 | 本地数据库服务 |

端口检查由 `scripts/e-review-check-all.ps1` 完成。若端口被占用，应先确认占用进程，不建议直接强制结束未知进程。

## 4. 启动顺序

推荐启动顺序为：

1. 启动 MySQL。
2. 启动 AI 服务。
3. 启动 wx-api。
4. 启动 admin-api。
5. 启动 H5 用户端。
6. 启动管理后台前端。
7. 执行服务检查脚本。
8. 打开 H5 用户端和管理后台页面。

系统提供一键启动脚本 `scripts/e-review-start-all.ps1`，用于按顺序启动主要服务。启动后执行 `scripts/e-review-check-all.ps1`，看到 `CHECK_ALL_PASS` 后再进入演示。

## 5. 一键脚本

系统提供以下部署辅助脚本：

| 脚本 | 作用 | 成功标记 |
| --- | --- | --- |
| `scripts/e-review-start-all.ps1` | 一键启动全部演示服务 | `START_ALL_PASS` |
| `scripts/e-review-stop-all.ps1` | 一键停止全部演示服务 | `STOP_ALL_PASS` |
| `scripts/e-review-restart-all.ps1` | 一键重启演示服务 | `RESTART_ALL_PASS` |
| `scripts/e-review-check-all.ps1` | 检查端口和关键接口 | `CHECK_ALL_PASS` |
| `scripts/e-review-open-demo-pages.ps1` | 打开 H5 和后台页面 | `OPEN_DEMO_PAGES_READY` |

这些脚本基于项目目录定位服务，不在文档中写入本地数据库密码。脚本失败时会输出服务名、端口、失败原因和建议排查方向。

## 6. 数据库备份与恢复

为了保证答辩前数据安全，系统提供数据库备份、恢复、检查和演示数据重置脚本：

| 脚本 | 作用 | 成功标记 |
| --- | --- | --- |
| `scripts/e-review-db-backup.ps1` | 备份当前数据库到备份目录 | `DB_BACKUP_PASS` |
| `scripts/e-review-db-restore.ps1` | 从指定 SQL 文件恢复数据库 | `DB_RESTORE_PASS` |
| `scripts/e-review-demo-data-reset.ps1` | 重置演示商品和演示数据 | `DEMO_DATA_RESET_PASS` |
| `scripts/e-review-db-check.ps1` | 检查核心表、迁移字段和演示商品 | `DB_CHECK_PASS` |

数据库恢复属于高风险操作，执行前应确认备份文件来源和当前数据库状态。演示前通常只需要执行演示数据重置和数据库检查。

## 7. 演示模式配置

演示模式配置用于明确系统边界：

```yaml
demo:
  mode:
    enabled: true
  payment:
    enabled: true
  shipping:
    enabled: true
  product:
    main: 1181000
    backup: 1006007,1006013
```

管理后台和 H5 用户端均可展示演示模式状态。关闭演示支付或演示发货配置后，对应按钮不应继续推进订单状态。该设计让答辩演示可以清楚说明：系统展示的是业务闭环原型，不是实际支付和物流系统。

## 8. 部署验证

部署后建议依次执行：

1. `scripts/e-review-check-all.ps1`
2. `scripts/e-review-db-check.ps1`
3. `scripts/e-review-demo-mode-check.ps1`
4. `scripts/e-review-doc-link-check.ps1`
5. `scripts/e-review-encoding-check.ps1`
6. `scripts/e-review-error-message-check.ps1`
7. `scripts/e-review-security-hygiene-check.ps1`
8. `scripts/e-review-full-ui-flow-check.ps1`
9. `scripts/e-review-final-acceptance.ps1`
10. `scripts/e-review-graduation-final-check.ps1`

上述脚本通过后，系统具备较高的现场演示可信度。若任一脚本失败，应根据脚本输出定位具体模块，而不是跳过失败项。

## 9. 常见问题

### 9.1 服务无法访问

先检查端口是否监听，再检查对应服务日志。若前端页面可打开但数据为空，应继续检查后端接口和数据库。

### 9.2 H5 下单失败

优先确认演示商品是否已通过种子脚本重置，检查商品是否上架、货品是否存在、库存是否充足。必要时重新执行演示数据重置脚本。

### 9.3 后台 Dashboard 无数据变化

确认用户评价是否写入 `litemall_comment`，确认 Agent 巡检是否已执行，确认分析结果是否写入 `litemall_review_ai_analysis`，确认风险任务是否生成。

### 9.4 AI 服务不可用

检查 8008 端口和健康检查接口。当前 AI 服务可使用本地规则模型运行，不要求外部 API Key。

## 10. 小结

本部署方案以本地稳定演示为核心，通过固定端口、一键脚本、数据库备份恢复、演示数据重置和最终验收脚本，降低答辩现场操作复杂度。系统边界清晰，便于在论文和答辩中说明其工程实现与原型定位。
