"""Fresh-process checks for pure contracts and capability import boundaries."""

from __future__ import annotations

import subprocess
import sys


def _run_isolated(source: str) -> None:
    subprocess.run([sys.executable, "-c", source], check=True)


def test_shared_result_contracts_do_not_import_specialists() -> None:
    _run_isolated(
        """
import sys
from equiped_harness.contracts.results import AgentEvaluationResult
assert not any(name in sys.modules for name in (
    'equiped_harness.agents.sme.agent',
    'equiped_harness.agents.sme.pipeline',
    'equiped_harness.agents.gad.agent',
    'equiped_harness.agents.gad.pipeline',
    'equiped_harness.agents.itso.agent',
    'equiped_harness.agents.itso.execution',
    'equiped_harness.agents.coordinator.agent',
    'equiped_harness.agents.coordinator.engine',
))
"""
    )


def test_capability_metadata_does_not_import_agent_implementations() -> None:
    _run_isolated(
        """
import sys
from equiped_harness.manifests import get_agent_manifest, uses_managed_prompt
assert get_agent_manifest('sme').agent_id == 'sme'
assert uses_managed_prompt('sme') is True
assert uses_managed_prompt('coordinator') is False
assert uses_managed_prompt('itso', 3) is False
assert not any(
    name.endswith(('.agent', '.pipeline', '.engine')) for name in sys.modules
)
"""
    )


def test_coordinator_advisory_parser_keeps_serialized_contract_lazy() -> None:
    _run_isolated(
        """
import sys
from equiped_harness.contracts.results import parse_advisory_output
assert 'equiped_harness.agents.coordinator.contracts' not in sys.modules
result = parse_advisory_output({'ungrounded_criteria': [
    {'criterion_id': 'C-01', 'reason': 'No evidence', 'advisory_only': True}
]})
assert result.to_dict()['ungrounded_criteria'][0]['advisory_only'] is True
assert 'equiped_harness.agents.coordinator.contracts' not in sys.modules
"""
    )


def test_each_specialist_loads_without_sibling_pipelines() -> None:
    for agent_id in ("sme", "coordinator", "gad", "itso"):
        _run_isolated(
            f"""
import sys
from equiped_harness.registry import get_agent_class
assert get_agent_class({agent_id!r}).agent_name == {agent_id!r}
for name in sys.modules:
    if name.startswith('equiped_harness.agents.'):
        parts = name.split('.')
        if name.endswith(('.agent', '.pipeline', '.engine', '.execution', '.legacy')):
            assert parts[2] == {agent_id!r}, name
assert 'server' not in sys.modules
"""
        )


def test_specialists_do_not_import_sibling_specialists() -> None:
    import ast
    from pathlib import Path

    import equiped_harness

    agents = Path(equiped_harness.__file__).parent / "agents"
    for source in agents.rglob("*.py"):
        own_agent = source.relative_to(agents).parts[0]
        for node in ast.walk(ast.parse(source.read_text())):
            names = []
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                if name.startswith("equiped_harness.agents."):
                    assert name.split(".")[2] == own_agent, (source, name)
