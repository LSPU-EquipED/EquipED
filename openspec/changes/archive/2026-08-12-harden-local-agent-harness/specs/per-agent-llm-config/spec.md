## MODIFIED Requirements

### Requirement: Per-agent model configuration preserves truthful routing
Agent aliases MAY resolve to the same model and SHALL NOT imply independent quota pools. Clients sharing provider, endpoint, and model SHALL share one provider gate. Implicit global and same-target fallback SHALL be removed; only explicitly configured distinct endpoint/model/privacy-compatible fallback is allowed. Configuration examples SHALL be provider-generic and not assume stale Llama models.

#### Scenario: Shared alias quota
- **WHEN** two agents resolve to the same provider, endpoint, and model
- **THEN** both requests use the same gate and quota accounting

#### Scenario: Fallback boundary
- **WHEN** a request fails without an explicit distinct compatible fallback
- **THEN** it fails without silently selecting another target
