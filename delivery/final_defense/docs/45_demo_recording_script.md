# 45 Demo Recording Script

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

## Screenshot and Recording Focus

Capture the H5 homepage, product detail, order submit, demo payment, demo shipping, receipt confirmation, review submit, admin dashboard, comment list, patrol center, risk center, operation center, Agent Trace, Agent Eval, case knowledge, quality summary, and final PASS output.

## v1.0.3 Encoding Note

Historical mojibake content was removed or rewritten in UTF-8-safe text. This document should remain free of BOM, private local paths, external links, leaked keys, and unreadable characters.

## v1.0.4 Recording Insert

After the risk task is generated, open Agent Trace and show:

1. The selected run source type and trigger type.
2. The Agent State Snapshot collapse panel.
3. The role summary cards and step timeline.
4. The Replay button and compare result.

Then open Agent Eval and show:

1. Service health cards.
2. Failure groups and fix suggestions.
3. Quality cards based on 30 golden samples.
4. Human feedback distribution.
