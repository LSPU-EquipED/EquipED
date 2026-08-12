"""Tests for ITSO-specific temperature config and model attribution (1.4)."""

from __future__ import annotations

from uuid import uuid4

from server.core.config import get_settings
from server.core.exceptions import ConfigurationError
from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.itso.agent import ITSO
from server.tests.agents.helpers import _mock_settings
from server.tests.agents.itso.test_itso_execution import _response

_OK_RESPONSE = _response()


def _clear_settings_cache(monkeypatch) -> None:
    """Clear the lru_cache so each test gets a fresh parse."""
    from server.core import config as _config_mod

    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_TEMPERATURE_ITSO", "")
    monkeypatch.setenv("LLM_TEMPERATURE", "")
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")


def test_itso_temperature_default(monkeypatch) -> None:
    """LLM_TEMPERATURE_ITSO should default to 0.0."""
    _clear_settings_cache(monkeypatch)
    try:
        settings = get_settings()
        assert settings.llm_temperature_itso == 0.0
    finally:
        get_settings.cache_clear()


def test_itso_temperature_env_override(monkeypatch) -> None:
    """LLM_TEMPERATURE_ITSO env var should take effect."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("LLM_TEMPERATURE_ITSO", "0.5")
    try:
        settings = get_settings()
        assert settings.llm_temperature_itso == 0.5
    finally:
        get_settings.cache_clear()


def test_itso_temperature_rejects_ge_one(monkeypatch) -> None:
    """LLM_TEMPERATURE_ITSO >= 1.0 should raise ConfigurationError."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("LLM_TEMPERATURE_ITSO", "1.0")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "must be between 0.0" in str(exc)
    finally:
        get_settings.cache_clear()


def test_itso_temperature_rejects_negative(monkeypatch) -> None:
    """Negative ITSO temperatures should raise the actual config error."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("LLM_TEMPERATURE_ITSO", "-0.1")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "must be between 0.0" in str(exc)
    finally:
        get_settings.cache_clear()


def test_itso_temperature_rejects_non_numeric(monkeypatch) -> None:
    """Non-numeric LLM_TEMPERATURE_ITSO should raise."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("LLM_TEMPERATURE_ITSO", "hot")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "LLM_TEMPERATURE_ITSO must be a valid number" in str(exc)
    finally:
        get_settings.cache_clear()


def test_get_agent_temperature_returns_itso_value() -> None:
    """get_agent_temperature('itso') should return the ITSO-specific
    temperature rather than the global default."""
    settings = _mock_settings(llm_temperature=0.5, llm_temperature_itso=0.0)
    assert settings.get_agent_temperature("itso") == 0.0


def test_get_agent_temperature_returns_global_for_other() -> None:
    """get_agent_temperature('sme') should return the global temperature."""
    settings = _mock_settings(llm_temperature=0.3, llm_temperature_itso=0.0)
    assert settings.get_agent_temperature("sme") == 0.3


def test_itso_agent_run_uses_itso_temperature(monkeypatch) -> None:
    """ITSO should receive the ITSO-specific temperature when
    llm_temperature is passed explicitly (as the supervisor does)."""
    captured_temps: list[float] = []

    class _TempCaptureLLM:
        model = "test-model"

        def generate(self, prompt, *, temperature, max_new_tokens):
            captured_temps.append(temperature)
            return _OK_RESPONSE

        def generate_result(
            self,
            prompt,
            *,
            temperature,
            max_new_tokens,
            deadline=None,
            response_contract=None,
        ):
            assert response_contract == ResponseContract.json_object()
            return CompletionResult(
                content=self.generate(
                    prompt, temperature=temperature, max_new_tokens=max_new_tokens
                ),
                served_model=self.model,
            )

    monkeypatch.setattr(
        "server.modules.agents.itso.execution.get_settings",
        lambda: _mock_settings(llm_temperature=0.5, llm_temperature_itso=0.0),
    )

    agent = ITSO(llm_client=_TempCaptureLLM())
    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {
                "chunk_id": "c1",
                "page_number": 1,
                "text": "text with citations (Author, 2020)",
            }
        ],
        llm_temperature=0.0,
    )

    # The explicit llm_temperature=0.0 should be used for ITSO.
    assert captured_temps == [0.0]
    assert result.success
    assert result.provenance is not None
    assert result.provenance["requested_temperature"] == 0.0


def test_itso_agent_records_requested_vs_actual_model() -> None:
    """Provenance should capture both requested_model and actual_model."""
    requested_model = "test-model"

    class _ModelTrackingLLM:
        model = requested_model

        def generate(self, prompt, *, temperature, max_new_tokens):
            return _OK_RESPONSE

        def generate_result(
            self,
            prompt,
            *,
            temperature,
            max_new_tokens,
            deadline=None,
            response_contract=None,
        ):
            assert response_contract == ResponseContract.json_object()
            return CompletionResult(
                content=self.generate(
                    prompt, temperature=temperature, max_new_tokens=max_new_tokens
                ),
                served_model=self.model,
            )

    agent = ITSO(llm_client=_ModelTrackingLLM())
    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "content"}],
    )

    assert result.provenance is not None
    assert result.provenance["requested_model"] == requested_model
    assert result.provenance["actual_model"] == requested_model
    assert result.provenance["fallback_occurred"] is False
    assert result.provenance["repair_occurred"] is False
    assert result.model_name == requested_model
