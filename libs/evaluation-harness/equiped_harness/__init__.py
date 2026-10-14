"""In-process specialist evaluation library with explicit input/transport/config."""

from .config import ExecutionConfig, execution_scope
from .coordinator import Coordinator
from .coordinator.scoring_rules import COORDINATOR_SCORING_RULES
from .envelope_map import envelope_criteria_map_from_snapshot
from .evaluation import SPECIALIST_CLASSES, EvaluationRequest, evaluate
from .gad import GAD
from .itso import ITSO
from .itso.precheck import run_itso_precheck
from .result_contracts import (
    AdvisoryOutput,
    AgentEvaluationResult,
    CapturedGeneration,
    CoordinatorAlignmentAdvisory,
    CriterionScore,
    CurriculumObjectiveMatch,
    UngroundedCriterionAdvisory,
    parse_advisory_output,
)
from .sme import SME
from .transport import (
    CompletionResult,
    ModelClient,
    ResponseContract,
    parse_json_payload,
)

__all__ = [
    "ExecutionConfig",
    "execution_scope",
    "EvaluationRequest",
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
    "run_itso_precheck",
    "COORDINATOR_SCORING_RULES",
    "CompletionResult",
    "ResponseContract",
    "ModelClient",
    "parse_json_payload",
]
