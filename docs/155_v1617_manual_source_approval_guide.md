# v1.6.1.7 Manual Source Approval Guide

## Purpose

This guide explains how the user, not Codex, can approve real-world data sources
for a minimal pilot. The current gate is:

`REALWORLD_SOURCE_APPROVAL_REQUIRED`

Codex must stop before data acquisition while
`data/real_world/source_manifest/manual_source_approval.yaml` has
`approved_by_user: false`.

## Approval File

Path:

`data/real_world/source_manifest/manual_source_approval.yaml`

The file separates rights by scope:

- Text internal research
- Text model training
- Text redistribution
- Image download
- Image internal VLM inference
- Image model training
- Image redistribution
- Derived feature storage

Do not use one general approval to cover every right. For example, approving
text internal evaluation does not approve image download, model training, or
redistribution.

## How To Review A Source

1. Open `docs/154_v1617_realworld_source_candidate_dossier.md`.
2. Check the official project page, license page, paper, and download entry.
3. Decide each right separately.
4. If any important right is unclear, leave that right as `false`.
5. If the source is valuable but unclear, contact the authors or publisher using
   `docs/156_v1617_dataset_permission_inquiry_templates.md`.
6. Only after the user explicitly approves, update
   `approved_by_user: true` and the exact source rights that are approved.

## Strict Boundaries

- Public access is not the same as permission to download, train, or redistribute.
- Research use is not the same as commercial use.
- Text permission is not image permission.
- Internal evaluation permission is not model training permission.
- Training permission is not redistribution permission.
- Pilot data must stay outside Git under
  `D:\EReviewAgent\data-private\realworld-pilot\`.

## Current Recommendation

- `amazon_reviews_2023`: contact authors before any use.
- `asap_chinese_reviews`: potentially useful for Chinese text-only internal
  validation after user approval; not multimodal.
- `jddc_2_multimodal`: application-controlled auxiliary dialogue source; not a
  review dataset and not approved for image use or training.

## After Approval

Run the source approval audit again:

```powershell
D:\anaconda\envs\torchtest\python.exe ai-service\scripts\audit_realworld_source_approval.py
```

If approval remains incomplete, the pipeline must stay blocked.
