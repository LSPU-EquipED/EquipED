"""Shared fixtures for GAD agent tests.

The GAD pipeline now reads per-criterion counting rules from the active
rubric via ``GADScoredAgent._rubric_scoring_rules``. That call reaches the
DB session factory, which is unavailable under the test environment's
empty ``DATABASE_URL``. Default it to "no DB rules" so every existing GAD
test exercises the fallback instructions; tests that need specific rules
override this with their own ``monkeypatch.setattr``.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_db_rubric_scoring_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.gad.pipeline.GADScoredAgent._rubric_scoring_rules",
        lambda self, db=None: {},
    )
