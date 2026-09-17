# E-Review Agent Project Readme

## Current Accepted Demo

The current delivery is a local-first, evidence-backed review-governance demo. The reviewer-facing admin navigation is intentionally limited to three business entries: 审核工作台、人工复核、判定依据库. The main path is:

```text
真实评论 -> 风险识别 -> Policy Evidence -> Reflection -> 人工复核 -> 审计记录
```

The implementation uses a governed Planner -> Execution -> Reflection loop, local Qwen3 Embedding, FAISS, BM25, RRF, optional BGE reranking, structure-aware document ingestion, and a BM25 fallback. Evidence mismatch or insufficiency triggers one bounded replan; unresolved and high-risk cases enter human review. AI output is an operational recommendation rather than an automatically executed punishment.

The knowledge module accepts common text, table, Office, digital PDF, and scanned PDF inputs through format-aware parsers. Upload jobs are processed by bounded workers, build an isolated candidate index, and require quality checks before an atomic release. The playground can query either the current or candidate index without changing production state.

See `docs/LOCAL_RUNBOOK.md` for startup commands, `docs/STEP22_FINAL_ACCEPTANCE_REPORT.md` for the frozen governance baseline, and `docs/agent-rag/V25_AGENTIC_POLICY_RAG.md` for the Agentic Policy RAG contract.

## Quick Start

```powershell
Copy-Item ai-service/.env.example ai-service/.env
./scripts/local/e-review-start.ps1 -NoMigration
./scripts/local/e-review-status.ps1
./scripts/local/e-review-step25-acceptance.ps1
```

Open `http://127.0.0.1:9527` after all services report ready. Local model weights, credentials, downloaded source documents, generated indexes, checkpoints, and runtime logs are intentionally excluded from Git.

## v1.4 AI Product UX Refinement

v1.4-ai-product-ux-refinement was the earlier five-entry information architecture. The accepted Step 22 reviewer UI supersedes that layout with three business-facing entries while retaining advanced diagnostics outside the primary reviewer workflow.

Existing backend APIs, database tables, legacy routes, and implemented modules are retained. Advanced Agent capabilities are folded into platform governance and knowledge-quality pages, while delivery checks, database backup, and final acceptance remain in scripts, docs, and delivery/final_defense instead of becoming admin business menus.

## Purpose

This file was normalized during v1.0.3-agent-product-polish to remove historical Chinese mojibake and keep the delivery package readable. It preserves the current project position: E-Review Agent is a graduation-defense oriented AI Agent review governance prototype built on top of existing e-commerce flows.

## Current System Scope

- H5 customer frontend supports product browsing, order submission, demo payment, demo shipping, receipt confirmation, and review submission.
- Admin frontend supports dashboard, product comments, AI analysis, Agent patrol, risk center, operation center, Agent Trace, Agent Eval, case knowledge, diagnostics, and quality evaluation.
- AI service runs locally with rule/mock/fallback capabilities and does not require a real external API key for defense demo.
- Database stores AI analyses, risk tasks, operation logs, Agent runs, Agent steps, feedback, and case knowledge records.
- Automation covers service health, smoke tests, customer loop, full menu API matrix, doc link checks, encoding checks, quality checks, full UI flow, and final acceptance.

## Boundaries

- No real payment integration.
- No real logistics integration.
- No real refund integration.
- No claim of production-grade SaaS availability.
- No fake claim of vector database or real multimodal large-model deployment.
- AI suggestions are for operation assistance only; final action requires human confirmation.

## Local Demo URLs

- Optional customer API: http://localhost:8082
- Admin frontend: http://localhost:9527
- admin-api: http://localhost:8083
- AI service: http://127.0.0.1:8008

## One Command Acceptance

Follow `docs/LOCAL_RUNBOOK.md`, then use `docs/STEP22_FINAL_ACCEPTANCE_REPORT.md` and `ai-service/artifacts/step22/final_acceptance_gate.json` as the current acceptance record. Historical acceptance scripts remain for their original release lines and are not the Step 22 source of truth.

## v1.0.3 Encoding Note

Historical mojibake content was removed or rewritten in UTF-8-safe text. This document should remain free of BOM, private local paths, external links, leaked keys, and unreadable characters.

## v1.0.4 Agentic RAG Product Plus

v1.0.4 adds the final product-plus layer for Agentic RAG demonstration:

- Agent Trace includes state snapshots, lightweight multi-role steps, replay, and run comparison.
- Agent Eval includes service health, failure groups, quality cards, RAG metrics, and human feedback distribution.
- Case Knowledge exposes local retrieval stats and evidence-rich similar-case results.
- Quality evaluation uses 30 golden samples and writes `docs/58_agent_rag_quality_eval_report.md`.
- The system still does not require Qdrant, external LLM keys, real payment, real logistics, or real refund integration.

## v1.1 Experimental Enterprise Agent Platform

`v1.1-agent-platform-enterprise-gap` is an experimental enhancement line. It adds local Tool Registry, Tool Approval, Memory Center, Guardrails, AgentOps, Agent Registry, and RAG quality evaluation for product comparison and thesis outlook.

The v1.1 line does not replace the v1.0.4 defense baseline. It does not add real payment, real logistics, real refund, external MCP servers, Qdrant, or mandatory external API keys. AI suggestions remain operation assistance and require human confirmation for final handling.

## v1.2 智能体协议与检索质量实验增强

`v1.2-agent-protocol-and-rag-quality` 是本地实验增强线，重点补齐工具协议清单、OpenAPI 风格描述、本地 MCP 风格描述、工具结构校验、工具契约测试、RAG 多策略检索、RAG 质量失败样本分析、智能体运维趋势和审批状态流。

v1.2 不替代 v1.0.4 稳定答辩主线，也不覆盖 v1.1.1 中文化成果。系统仍然不接真实支付、真实物流、真实退款、外部 MCP 服务、Qdrant 或外部向量数据库。所有新增能力均以本地可运行、中文可展示、脚本可验收为边界。

v1.2 验收入口：

- `scripts/e-review-tool-protocol-check.ps1`
- `scripts/e-review-tool-schema-check.ps1`
- `scripts/e-review-agentops-trend-check.ps1`
- `scripts/e-review-v12-acceptance.ps1`
