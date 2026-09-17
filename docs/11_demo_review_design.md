# 11 Demo Review Design

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

## v1.0.3 Encoding Note

Historical mojibake content was removed or rewritten in UTF-8-safe text. This document should remain free of BOM, private local paths, external links, leaked keys, and unreadable characters.
