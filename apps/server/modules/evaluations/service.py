"""Evaluations business logic layer and backward-compatible facade."""

from __future__ import annotations

from .admission import (
    _duration_seconds,
    _validate_evaluation_target,
    admission_schema_ready,
    create_evaluation,
)
from .agent_schedule import VALID_TARGET_AGENTS
from .desk import get_specialist_desk_queue
from .exceptions import (
    EvaluationExecutionOwnershipError,
    EvaluationNotFoundError,
    EvaluationPipelineUnavailableError,
    ForbiddenEvaluationAccessError,
    InvalidEvaluationTargetError,
    InvalidStatusTransitionError,
)
from .execution import (
    _TERMINAL_STATUSES,
    acquire_evaluation_execution,
    acquire_next_evaluation_execution,
    heartbeat_evaluation_execution,
    recover_stale_evaluation_execution,
    seconds_until_stale_evaluation_execution,
    transition_evaluation_status,
)
from .models import (
    EvaluationJob,
    EvaluationStatus,
    can_transition_status,
)
from .queries import (
    _check_ownership_or_404,
    get_evaluation,
    get_evaluation_status,
    get_latest_evaluations,
    list_evaluations,
)
from .schemas import (
    DeskQueueItem,
    DeskQueueListResponse,
    EvaluationListItem,
    EvaluationListResponse,
    EvaluationResponse,
    EvaluationStatusResponse,
    EvaluationSubmitRequest,
    LatestEvaluationItem,
    LatestEvaluationsResponse,
)

__all__ = [
    "DeskQueueItem",
    "DeskQueueListResponse",
    "EvaluationExecutionOwnershipError",
    "EvaluationJob",
    "EvaluationListItem",
    "EvaluationListResponse",
    "EvaluationNotFoundError",
    "EvaluationPipelineUnavailableError",
    "EvaluationResponse",
    "EvaluationStatus",
    "EvaluationStatusResponse",
    "EvaluationSubmitRequest",
    "ForbiddenEvaluationAccessError",
    "InvalidEvaluationTargetError",
    "InvalidStatusTransitionError",
    "LatestEvaluationItem",
    "LatestEvaluationsResponse",
    "VALID_TARGET_AGENTS",
    "_TERMINAL_STATUSES",
    "_check_ownership_or_404",
    "_duration_seconds",
    "_validate_evaluation_target",
    "acquire_evaluation_execution",
    "acquire_next_evaluation_execution",
    "admission_schema_ready",
    "can_transition_status",
    "create_evaluation",
    "get_evaluation",
    "get_evaluation_status",
    "get_latest_evaluations",
    "get_specialist_desk_queue",
    "heartbeat_evaluation_execution",
    "list_evaluations",
    "recover_stale_evaluation_execution",
    "seconds_until_stale_evaluation_execution",
    "transition_evaluation_status",
]
