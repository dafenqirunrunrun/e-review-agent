# v1.6.1.6 Real-World Source And License Audit

## Conclusion

`REALWORLD_SOURCE_LICENSE_AUDIT_BLOCKED`

## Source Audit

| source_id | source_name | license | approval_status | audit_reason |
| --- | --- | --- | --- | --- |
| `banglishrev_hf` | BanglishRev: Bangla-English and Code-mixed E-commerce Review Dataset | requires_manual_verification_before_use | blocked_pending_manual_license_verification | license and redistribution terms must be verified from the official dataset card before use |
| `amazon_reviews_2023_mccauley` | Amazon Reviews 2023 | not_found | blocked_license_unclear | explicit redistribution and derivative-data permission not confirmed |
| `amazon_berkeley_objects_abo` | Amazon Berkeley Objects Dataset | CC BY 4.0 reported by project documentation | blocked_not_review_dataset | does not contain user review text or review-image pairs |
| `yelp_open_dataset` | Yelp Open Dataset | educational terms, no open redistribution | blocked_not_ecommerce_or_redistributable | business reviews are not e-commerce product reviews and redistribution is restricted |

## Boundary

Only `approval_status=approved` sources with explicit research permission may
enter the downstream pipeline. If redistribution is restricted, Git stores only
hashes, manifests, statistics, scripts, and aggregate audit results.
