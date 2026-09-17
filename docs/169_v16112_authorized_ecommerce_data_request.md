# V1.6.1.12 Authorized Ecommerce Data Request

This request can be given to an enterprise, advisor, or data-governance owner.

## Requested Data

Recommended scale:

- Text reviews: development 800, validation 200, external test 200.
- Multimodal reviews: development 160, validation 40, external test 40.

Minimum acceptable scale:

- Text reviews: development 300, validation 100, external test 100.
- Multimodal reviews: development 50, validation 20, external test 20.

## Suggested Categories

- Normal review
- Damaged packaging
- Damaged product
- Missing parts
- Wrong item
- Leakage
- Contamination
- Not as described
- Suspected counterfeit
- Safety hazard
- After-sales dispute
- Irrelevant image
- Text-image conflict
- Insufficient evidence

## Privacy And Authorization Requirements

The project does not need plaintext user identifiers or real order numbers. Review images should remove shipping labels and personal information before delivery. The provider must explicitly state allowed uses: internal evaluation, formal external evaluation, model training, image use, retention period, and redistribution restrictions.
