# v1.3 数据库备份、恢复与演示数据重置指南

## 目标

本指南用于毕业答辩前保护和恢复本地 `litemall` 数据库，避免多次测试导致演示数据不可控。数据库脚本只服务本地答辩演示，不替代生产级备份系统。

## 数据库检查

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-db-check.ps1
```

成功标记：

```text
DB_CHECK_PASS
```

检查内容：

- 核心评论、AI 分析、风险任务、运营日志表是否存在；
- Agent Run、Agent Step、反馈、工具注册、记忆画像、安全护栏事件表是否存在；
- v1.0.4 到 v1.2 需要的来源字段、Trace 字段和工具字段是否存在；
- 主演示商品是否上架且有库存；
- AI 相关表是否具备基本读写能力。

## 数据库备份

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-db-backup.ps1
```

成功标记：

```text
DB_BACKUP_PASS
```

备份文件默认保存到：

```text
backups/db/
```

文件名包含时间戳，便于答辩前后区分。该目录不应提交到 Git。

## 数据库恢复

恢复前必须显式传入两次确认参数：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-db-restore.ps1 -SqlFile <backup.sql> -ConfirmRestore -SecondConfirm
```

成功标记：

```text
DB_RESTORE_PASS
```

注意：恢复会覆盖当前数据库状态。答辩现场不建议临时恢复，除非已经确认当前数据被破坏。

## 演示数据重置

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-demo-data-reset.ps1
```

成功标记：

```text
DEMO_DATA_RESET_PASS
```

默认动作：

- 重置主演示商品和备用商品的上架状态；
- 重置演示商品库存；
- 检查核心 AI 表和迁移字段；
- 不清空历史订单、评论、风险任务或运行记录。

如需清理最近 30 天部分演示 AI 结果，可加：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-demo-data-reset.ps1 -CleanGeneratedDemoRecords
```

如需生成一条标准演示评价，可加：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-demo-data-reset.ps1 -CreateStandardReview
```

## 主演示商品

| 用途 | 商品 ID |
| --- | ---: |
| 主演示商品 | 1181000 |
| 备用商品 | 1006007 |
| 备用商品 | 1006013 |

## 密码与安全边界

数据库脚本按以下优先级读取连接信息：

1. 命令行参数；
2. 环境变量 `EREVIEW_MYSQL_USER`、`EREVIEW_MYSQL_PASSWORD`；
3. 本地 Spring 数据库配置。

脚本不会把数据库密码写入文档，不会把密码打印到控制台，也不会把备份文件纳入最终交付包。备份、恢复和重置都只面向本地毕业设计演示环境。
