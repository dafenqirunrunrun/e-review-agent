# Interview Q&A

## What problem does it solve?

It demonstrates how ecommerce review analysis can be governed with evidence, bounded tools, human review routing, and privacy-safe audit trails.

## Why Hybrid RAG?

Sparse retrieval gives explainable lexical matches. Dense retrieval improves semantic recall. RRF combines both without relying on one score scale.

## How is the Agent bounded?

The Agent has fixed nodes, maximum steps, maximum tool calls, read-only tools, no shell or dynamic code execution, and policy guards.

## What is the adapter boundary?

The v2.3 adapter is local and private. It is not published, merged, retrained, or used by default. Base remains the default model mode.
