# v1.6.1.8 Delegated Real-World Source Approval

## Conclusion

`DELEGATED_SOURCE_APPROVAL_COMPLETE`

The user delegated conservative project-internal source review to the assistant.
This is not legal certification. Training, commercial use, redistribution, and
formal external-test use remain disallowed.

## Official Evidence Recheck

| Source | HTTP | Strength | Official URL | Unresolved issue |
| --- | ---: | --- | --- | --- |
| `amazon_reviews_2023` | 200 | official_research_release | https://amazon-reviews-2023.github.io/ | No explicit dataset license or terms were found on the official project page during this delegated audit. |
| `asap_chinese_reviews` | 200 | explicit | https://github.com/Meituan-Dianping/ASAP | Repository code/data license needs to remain separated from any broader redistribution or training claim. |
| `asap_chinese_reviews` | 200 | explicit | https://api.github.com/repos/Meituan-Dianping/ASAP/contents/data | Pilot must keep raw text outside Git and must not be promoted to formal external test. |
| `jddc_2_multimodal` | 200 | official_research_release | https://github.com/hrlinlp/jddc2.1 | No data access approval has been obtained in this project, so all actual data acquisition rights remain unavailable. |

## Conditional Approval

| Source | Decision | Scope | Text | Images | Training | Redistribution |
| --- | --- | --- | --- | --- | --- | --- |
| `amazon_reviews_2023` | conditionally_approved | private_internal_pilot | True | True | False | False |
| `asap_chinese_reviews` | conditionally_approved | private_internal_pilot | True | False | False | False |
| `jddc_2_multimodal` | unavailable | auxiliary_development_only | false | false | false | false |

## Gate Effects

- `REAL_TEXT_PILOT_ACQUISITION_ALLOWED`
- `REAL_MULTIMODAL_PILOT_ACQUISITION_ALLOWED`
- Formal external test: not approved
- SFT/DPO/VLM fine-tuning: not approved
- Raw pilot data must stay outside Git under `D:\EReviewAgent\data-private\realworld-pilot`
