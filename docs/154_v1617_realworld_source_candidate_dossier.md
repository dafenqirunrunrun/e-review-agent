# v1.6.1.7 Real-World Source Candidate Dossier

## Gate

`REALWORLD_SOURCE_APPROVAL_REQUIRED`

Codex generated this dossier for manual review only. It does not approve any
source, does not download data, and does not start a pilot.

## Decision Table

| Source | Text | Images | Language | Internal evaluation | Training | Redistribution | Main unresolved issue |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `amazon_reviews_2023` | yes | yes | en | pending user approval | not approved | not approved | No explicit license or terms found on the project page during this audit. |
| `asap_chinese_reviews` | yes | no | zh | pending user approval | not approved | not approved | Confirm whether the repository data contains any user identifiers or personal information. |
| `jddc_2_multimodal` | no | no | zh | pending user approval | not approved | not approved | Official access requires application; no local rights are granted by the public repository alone. |

## Candidate Details

## amazon_reviews_2023

- Official source: https://amazon-reviews-2023.github.io/
- Official paper: https://arxiv.org/abs/2403.03952
- License evidence: not found / not explicit
- Recommended use: Hold as high-value candidate for English text and multimodal internal validation after manual rights clarification only.
- Prohibited use: Do not download reviews or images, do not train, do not redistribute raw text/images, and do not store user IDs before user approval.
- Contact authors recommended: True
- External test suitability: not yet; source approval and pilot isolation are required first.
- SFT suitability: not yet; no training rights are approved.
- Missing evidence: No explicit license or terms found on the project page during this audit.; Need written confirmation for local review text storage, image download, VLM inference, model training, derived feature persistence, and redistribution boundaries.; Need policy for reviewer user_id deletion or hashing.
## asap_chinese_reviews

- Official source: https://github.com/Meituan-Dianping/ASAP
- Official paper: https://aclanthology.org/2021.naacl-main.167/
- License evidence: https://github.com/Meituan-Dianping/ASAP/blob/master/LICENSE
- Recommended use: After user approval, use only as Chinese text internal validation for sentiment/rating and language-noise coverage.
- Prohibited use: Do not mark as multimodal, do not infer image rights, and do not treat restaurant reviews as full product-risk coverage.
- Contact authors recommended: False
- External test suitability: not yet; source approval and pilot isolation are required first.
- SFT suitability: not yet; no training rights are approved.
- Missing evidence: Confirm whether the repository data contains any user identifiers or personal information.; Confirm whether Apache-2.0 is acceptable for the project's intended local evaluation and derived metric publication.; Domain is restaurant/O2O and may not cover physical product damage, wrong item, or image-text conflict taxonomy.
## jddc_2_multimodal

- Official source: https://github.com/hrlinlp/jddc2.1
- Official paper: https://arxiv.org/abs/2109.12913
- License evidence: not found / not explicit
- Recommended use: Only after application approval, consider as auxiliary Chinese after-sales multimodal dialogue cases for development diagnostics, not as review evaluation.
- Prohibited use: Do not call it review data, do not use without application approval, do not train or redistribute, and do not use as the final external review test set.
- Contact authors recommended: True
- External test suitability: not yet; source approval and pilot isolation are required first.
- SFT suitability: not yet; no training rights are approved.
- Missing evidence: Official access requires application; no local rights are granted by the public repository alone.; Need explicit approval for image download, local VLM inference, model training, derived feature persistence, and retention period.; PII and conversation privacy handling must be clarified before any pilot.
