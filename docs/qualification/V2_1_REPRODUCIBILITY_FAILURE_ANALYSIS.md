# v2.1 Reproducibility Failure Analysis

## Scope

This note freezes the two default Python regression failures observed during the v2.1 qualification run. The goal is to separate ordinary reproducibility tests from local runtime assets such as private FAISS indexes and local model directories.

## Failure 1: FAISS index file dependency

- Test node: `ai-service/tests/test_v180_real_retrieval_eval.py::test_v180_real_retrieval_eval_persistent_index_files_exist`
- Failure class: implicit local asset dependency
- Dependency: `data/private_research/enterprise_rag_v180/faiss_index/.../index.faiss`
- Root cause: the test asserted that a persisted FAISS binary from a prior local run exists in the repository checkout.
- Classification: default regression test should be self-contained unless explicitly marked as a real dense asset test.
- Remediation: the default test now builds a small FAISS fixture under `tmp_path`, publishes it with `VersionedFaissIndex`, and verifies load, metadata and checksum behavior without using untracked `index.faiss`.

## Failure 2: Provider selection gate dependency

- Test node: `ai-service/tests/test_v200_agent_rag_enterprise_maturity.py::test_v200_provider_selection_gate_reports_enterprise_tokens`
- Failure class: real provider runtime dependency in default tests
- Dependency: external BGE-M3 model asset and real provider gate artifacts
- Root cause: the default test executed the real provider selection gate, which requires a configured local model and dense runtime evidence.
- Classification: provider selection has two layers: contract behavior and real runtime behavior.
- Remediation: default tests now execute `run_agent_rag_provider_selection_contract_gate.py`, which validates target mode, provider selection metadata, retrieval default and fallback flags without loading real model assets. Real provider runtime remains separately gated by explicit qualification assets.

## External Asset Boundary

Real BGE-M3, dense FAISS indexes, rerankers and LLMs must be supplied through `AGENT_RAG_QUALIFICATION_ASSET_MANIFEST`. The manifest is intentionally external to the repository. The repository contains only the schema, an example manifest and a verifier that reports blocked assets without failing ordinary Python regression.

## Current Decision

These fixes do not promote v2.1 to a new release candidate. They only repair the reproducibility boundary. The candidate decision remains `RETAIN_FFD05F26_RC_BASELINE` until real reranker, real LLM quality, vulnerability database and remaining supply-chain gates are closed.
