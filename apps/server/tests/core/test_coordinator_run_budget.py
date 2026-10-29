"""Whole-run packet budgets remain separate from model-request deadlines."""

import pytest
from equiped_harness import ExecutionConfig
from server.core.config import get_settings
from server.core.exceptions import ConfigurationError
from server.modules.evaluations.harness_adapter import execution_config_from_settings


@pytest.mark.parametrize("value", ["0", "-1", "3601", "abc"])
def test_invalid_coordinator_run_budget_is_rejected(monkeypatch, value):
    monkeypatch.setenv("COORDINATOR_RUN_TIMEOUT_SECONDS", value)
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigurationError, match="COORDINATOR_RUN_TIMEOUT_SECONDS"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_configured_run_budget_reaches_harness_without_changing_request_timeout(
    monkeypatch,
):
    monkeypatch.setenv("COORDINATOR_RUN_TIMEOUT_SECONDS", "480")
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")
    get_settings.cache_clear()
    try:
        config = execution_config_from_settings(get_settings())
        assert config.coordinator_run_timeout_seconds == 480
        assert config.llm_request_timeout_seconds == 30
    finally:
        get_settings.cache_clear()
    with pytest.raises(ValueError, match="coordinator_run_timeout_seconds"):
        ExecutionConfig(coordinator_run_timeout_seconds=3601)
