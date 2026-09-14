"""Tests for server.modules.agents public facade and PEP 562 lazy loading."""

from __future__ import annotations

import subprocess
import sys

import pytest
import server.modules.agents as agents_facade
from server.modules.agents.contracts import (
    AdvisoryOutput as CanonicalAdvisoryOutput,
)
from server.modules.agents.contracts import (
    AgentEvaluationResult as CanonicalAgentEvaluationResult,
)
from server.modules.agents.contracts import (
    CriterionScore as CanonicalCriterionScore,
)
from server.modules.agents.contracts import (
    UngroundedCriterionAdvisory as CanonicalUngroundedCriterionAdvisory,
)
from server.modules.agents.coordinator.agent import Coordinator as CanonicalCoordinator
from server.modules.agents.gad.agent import GAD as CanonicalGAD
from server.modules.agents.itso.agent import ITSO as CanonicalITSO
from server.modules.agents.sme.agent import SME as CanonicalSME
from server.modules.agents.supervision.supervisor import (
    Supervisor as CanonicalSupervisor,
)

EXPECTED_EXPORTS = {
    "AdvisoryOutput": CanonicalAdvisoryOutput,
    "AgentEvaluationResult": CanonicalAgentEvaluationResult,
    "Coordinator": CanonicalCoordinator,
    "CriterionScore": CanonicalCriterionScore,
    "GAD": CanonicalGAD,
    "ITSO": CanonicalITSO,
    "SME": CanonicalSME,
    "Supervisor": CanonicalSupervisor,
    "UngroundedCriterionAdvisory": CanonicalUngroundedCriterionAdvisory,
}


def test_facade_all_exact() -> None:
    assert sorted(agents_facade.__all__) == sorted(EXPECTED_EXPORTS.keys())


def test_facade_exports_resolve_and_identity_match() -> None:
    for name, canonical in EXPECTED_EXPORTS.items():
        resolved = getattr(agents_facade, name)
        assert resolved is canonical
        # Ensure cached in globals
        assert name in agents_facade.__dict__
        assert agents_facade.__dict__[name] is canonical


def test_facade_dir_includes_all() -> None:
    dir_contents = dir(agents_facade)
    for name in EXPECTED_EXPORTS:
        assert name in dir_contents


def test_facade_unknown_attribute_raises() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'NonExistent'"):
        _ = getattr(agents_facade, "NonExistent")


def test_no_forbidden_exports_in_all() -> None:
    assert "SupervisorResult" not in agents_facade.__all__
    with pytest.raises(AttributeError):
        _ = getattr(agents_facade, "SupervisorResult")


def test_lazy_import_does_not_load_specialists_or_supervisor() -> None:
    code = """
import sys
import server.modules.agents

loaded = set(sys.modules.keys())
prohibited_substrings = [
    "server.modules.agents.sme",
    "server.modules.agents.coordinator",
    "server.modules.agents.gad",
    "server.modules.agents.itso",
    "server.modules.agents.supervision",
]

for mod in loaded:
    for prohibited in prohibited_substrings:
        if mod == prohibited or mod.startswith(prohibited + "."):
            raise AssertionError(f"Module eagerly loaded: {mod}")

print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Subprocess failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert result.stdout.strip() == "OK"
