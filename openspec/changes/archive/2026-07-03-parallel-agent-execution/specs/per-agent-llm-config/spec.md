## ADDED Requirements

### Requirement: Per-agent LLM model configuration
The system SHALL support assigning a distinct LLM model to each evaluation agent (SME, Coordinator, GAD, ITSO) via environment variables `LLM_MODEL_SME`, `LLM_MODEL_COORD`, `LLM_MODEL_GAD`, and `LLM_MODEL_ITSO`. When a per-agent model is not set, the system SHALL fall back to the global `LLM_MODEL_NAME`.

#### Scenario: Per-agent model is set
- **WHEN** `LLM_MODEL_SME` is set to `llama-3.1-8b-instant`
- **THEN** the SME agent SHALL use `llama-3.1-8b-instant` for its LLM calls

#### Scenario: Per-agent model is not set
- **WHEN** `LLM_MODEL_COORD` is not set but `LLM_MODEL_NAME` is set to `llama-3.1-8b-instant`
- **THEN** the Coordinator agent SHALL fall back to `llama-3.1-8b-instant`

#### Scenario: All per-agent models are set
- **WHEN** all four per-agent model env vars are set to different models
- **THEN** each agent SHALL use its assigned model, creating four independent TPM pools

### Requirement: Per-agent LLM client factory
The system SHALL provide a `get_llm_client_for_agent(agent_name)` function that returns a cached `LocalLLMClient` configured with the agent's assigned model. The factory SHALL cache clients per agent name to avoid recreating clients on every evaluation.

#### Scenario: Client is created for an agent
- **WHEN** `get_llm_client_for_agent("sme")` is called
- **THEN** a `LocalLLMClient` with the SME model SHALL be returned

#### Scenario: Client is cached
- **WHEN** `get_llm_client_for_agent("sme")` is called twice
- **THEN** the same `LocalLLMClient` instance SHALL be returned both times

#### Scenario: Different agents get different clients
- **WHEN** `get_llm_client_for_agent("sme")` and `get_llm_client_for_agent("coordinator")` are called
- **THEN** two distinct `LocalLLMClient` instances with different models SHALL be returned

### Requirement: Model-failure fallback
The system SHALL retry an agent's LLM call with the global fallback model (`LLM_MODEL_NAME`) if the agent's assigned model returns a persistent error after exhausting retries. If the fallback also fails, the agent SHALL be marked as failed.

#### Scenario: Assigned model fails, fallback succeeds
- **WHEN** an agent's assigned model returns HTTP 429 after all retries are exhausted
- **THEN** the system SHALL retry the LLM call with the global fallback model
- **AND** if the fallback succeeds, the agent SHALL produce a successful result

#### Scenario: Assigned model fails, fallback also fails
- **WHEN** both the assigned model and the fallback model fail
- **THEN** the agent SHALL be marked as failed with an error message describing both failures

#### Scenario: Model deprecation (HTTP 404)
- **WHEN** an agent's assigned model returns HTTP 404 (model not found / deprecated)
- **THEN** the system SHALL retry with the fallback model without consuming retry attempts on the deprecated model
