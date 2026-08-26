## MODIFIED Requirements

### Requirement: ITSO policy clause delivery is locality- and approval-gated
Policy clause delivery SHALL require both explicit approval and a technically local endpoint. A local-only sensitive request SHALL never fall back remotely. When blocked, the provider SHALL receive status-only evidence.

#### Scenario: Blocked policy delivery
- **WHEN** approval is absent or endpoint locality fails
- **THEN** no policy clauses are delivered and the request remains status-only
