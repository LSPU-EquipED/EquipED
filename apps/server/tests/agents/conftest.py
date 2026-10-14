"""Explicit immutable harness controls for backend regression fixtures."""

from contextlib import ExitStack
from dataclasses import fields

import pytest
from equiped_harness import ExecutionConfig, execution_scope


@pytest.fixture
def harness_config():
    """Translate legacy fixture controls once, scope them, and always restore."""
    with ExitStack() as stack:

        def activate(settings):
            values = {
                field.name: getattr(settings, field.name)
                for field in fields(ExecutionConfig)
                if hasattr(settings, field.name)
            }
            for agent, field in (
                ("sme", "llm_temperature"),
                ("itso", "llm_temperature_itso"),
            ):
                if field not in values and hasattr(settings, "get_agent_temperature"):
                    values[field] = settings.get_agent_temperature(agent)
            config = ExecutionConfig(**values)
            stack.enter_context(execution_scope(config))
            return config

        yield activate
