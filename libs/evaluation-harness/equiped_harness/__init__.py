"""In-process specialist evaluation library with explicit input/transport/config."""

from equiped_harness.api import EvaluationRequest, evaluate
from equiped_harness.contracts.results import (
    AdvisoryOutput,
    AgentEvaluationResult,
    CapturedGeneration,
    CriterionScore,
    UngroundedCriterionAdvisory,
    parse_advisory_output,
)
from equiped_harness.envelope_map import envelope_criteria_map_from_snapshot
from equiped_harness.runtime.config import ExecutionConfig, execution_scope
from equiped_harness.runtime.control import ExecutionControl
from equiped_harness.runtime.model import (
    CompletionResult,
    ModelClient,
    ResponseContract,
    parse_json_payload,
)
from equiped_harness.tools.config import ToolConfig

__all__ = [
    "ExecutionConfig",
    "ExecutionControl",
    "execution_scope",
    "EvaluationRequest",
    "ToolConfig",
    "evaluate",
    "SPECIALIST_CLASSES",
    "SME",
    "Coordinator",
    "GAD",
    "ITSO",
    "AdvisoryOutput",
    "AgentEvaluationResult",
    "CapturedGeneration",
    "CoordinatorAlignmentAdvisory",
    "CriterionScore",
    "CurriculumObjectiveMatch",
    "UngroundedCriterionAdvisory",
    "parse_advisory_output",
    "envelope_criteria_map_from_snapshot",
    "COORDINATOR_SCORING_RULES",
    "CompletionResult",
    "ResponseContract",
    "ModelClient",
    "parse_json_payload",
]


def __getattr__(name: str):
    from equiped_harness.registry import get_agent_class, specialist_classes

    if name in {"CoordinatorAlignmentAdvisory", "CurriculumObjectiveMatch"}:
        from equiped_harness.agents.coordinator import contracts

        return getattr(contracts, name)
    if name == "SPECIALIST_CLASSES":
        return specialist_classes()
    names = {"SME": "sme", "Coordinator": "coordinator", "GAD": "gad", "ITSO": "itso"}
    if name in names:
        return get_agent_class(names[name])
    if name == "COORDINATOR_SCORING_RULES":
        from equiped_harness.agents.coordinator.scoring_rules import (
            COORDINATOR_SCORING_RULES,
        )

        return COORDINATOR_SCORING_RULES
    raise AttributeError(name)
