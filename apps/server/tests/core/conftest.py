"""Test fixtures for server/core/ tests.

The cross-field validation added in
``server.core.config.get_settings()`` requires
``AGENT_PROMPT_BUDGET_CHARS < AGENT_TOTAL_PROMPT_BUDGET_CHARS``. With the
new defaults (chunk=5,000, total=8,000) the validation passes on
unpinned defaults. This autouse fixture pins the chunk budget to 5,000
for tests that override ``AGENT_TOTAL_PROMPT_BUDGET_CHARS`` so the
validation never fires mid-test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from server.core import llm


@pytest.fixture(autouse=True)
def _pin_prompt_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")


@pytest.fixture(autouse=True)
def _isolate_provider_gates() -> Iterator[None]:
    """Prevent quota/cooldown state from leaking between transport tests."""
    llm._GATES.clear()
    yield
    llm._GATES.clear()
