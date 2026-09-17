# V1.6.1.12 Authorized Annotation Workflow

## Mode A: Double Annotation

Two annotators independently label each sample. Disagreements are resolved through adjudication.

Formal external test data must use either double independent annotation or one annotation plus independent review, followed by final adjudication.

Recommended agreement gates:

- Risk type Cohen's Kappa >= 0.70
- Risk level Cohen's Kappa >= 0.65
- Human review Cohen's Kappa >= 0.70
- Text-image consistency Cohen's Kappa >= 0.65

Evidence span F1 should be reported for text evidence when span labels exist.

## Mode B: Single Preliminary Annotation

Single-person or model-preliminary labels may be used for development exploration only. These labels must include `human_verified=false` and cannot be called gold labels, ground truth, or formal benchmark labels.
