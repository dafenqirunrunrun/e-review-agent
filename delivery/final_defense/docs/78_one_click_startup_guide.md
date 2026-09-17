# v1.3 一键启动与现场检查指南

## 目标

本指南用于毕业答辩现场快速启动、停止、重启和检查 E-Review Agent。v1.3 的目标是减少人工启动多个服务时的出错概率，让系统可以稳定进入演示状态。

## 服务清单

| 服务 | 端口 | 说明 |
| --- | ---: | --- |
| AI 服务 | 8008 | FastAPI 本地规则/Mock/可选框架 fallback 分析服务 |
| wx-api | 8080 | H5 用户端接口 |
| admin-api | 8083 | 管理后台接口 |
| H5 用户端 | 6255 | litemall-vue 前台页面 |
| 管理后台 | 9527 | litemall-admin 后台页面 |

## 一键启动

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-start-all.ps1
```

成功标记：

```text
START_ALL_PASS
```

如果需要启动前重新构建 Java 模块，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-start-all.ps1 -BuildBeforeStart
```

## 一键停止

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-stop-all.ps1
```

成功标记：

```text
STOP_ALL_PASS
```

## 一键重启

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-restart-all.ps1
```

成功标记：

```text
RESTART_ALL_PASS
```

## 一键检查

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-check-all.ps1
```

检查内容包括端口监听、H5 页面、后台页面、wx-api 首页、AI health、Dashboard summary、风险任务数量和后台核心接口。成功标记：

```text
CHECK_ALL_PASS
```

## 打开演示页面

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-open-demo-pages.ps1
```

成功标记：

```text
OPEN_DEMO_PAGES_READY
```

该脚本会打开：

- H5 用户端：`http://localhost:6255`
- 管理后台：`http://localhost:9527`

## 答辩前推荐顺序

1. 启动 MySQL。
2. 执行 `e-review-db-check.ps1`，确认数据库可用。
3. 执行 `e-review-start-all.ps1`。
4. 执行 `e-review-check-all.ps1`。
5. 执行 `e-review-demo-data-reset.ps1`。
6. 执行 `e-review-full-ui-flow-check.ps1` 做一次全链路预热。
7. 执行 `e-review-open-demo-pages.ps1` 打开 H5 和后台。

## 常见失败与处理

| 现象 | 可能原因 | 建议处理 |
| --- | --- | --- |
| 端口未监听 | 服务未启动或启动失败 | 查看对应服务终端窗口，重新执行一键启动 |
| 端口被占用 | 上一次服务未停止 | 执行一键停止后再启动 |
| AI health 失败 | AI 服务未启动或 Python 环境异常 | 单独进入 `ai-service` 检查 `python -m pytest` |
| admin-api 登录失败 | 后端未就绪或数据库不可用 | 先执行 `e-review-db-check.ps1`，再检查 8083 |
| H5 首页为空 | wx-api 未就绪或 8080 异常 | 检查 `/wx/home/index` |
| Dashboard 无数据 | 演示数据未重置或巡检未执行 | 执行演示数据重置和 Full UI Flow |

## 安全边界

脚本不会在文档中记录数据库密码，也不会要求外部 OpenAI Key、外部 MCP 服务或 Qdrant。演示支付和演示发货仍是答辩演示模式，不调用真实支付或真实物流。
