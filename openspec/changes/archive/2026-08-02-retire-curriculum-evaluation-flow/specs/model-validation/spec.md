## ADDED Requirements

### Requirement: Validation preserves Admin SLM upload without curriculum selection
Model Validation SHALL retain its Admin SLM upload workflow but SHALL NOT offer
curriculum suggestions or require a curriculum selection for a new validation.
New validation runs without curriculum SHALL use explicit partial semantics and
truthfully omit Coordinator expectations.

#### Scenario: Admin validates an uploaded SLM
- **WHEN** an admin uploads an SLM for model validation after curriculum
  retirement
- **THEN** the validation workflow SHALL not request a curriculum suggestion and
  SHALL not require Coordinator expected scores
