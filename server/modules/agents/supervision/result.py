"""Results produced by the Layer 3 supervisor."""

import uuid
from dataclasses import dataclass, field

from ..contracts import AgentEvaluationResult


@dataclass(slots=True)
class SupervisorResult:
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    agent_results: list[AgentEvaluationResult] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)
