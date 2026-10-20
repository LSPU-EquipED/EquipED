"""Authenticated ITSO result reads, including historical assessments."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.evaluations.exceptions import EvaluationNotFoundError
from server.modules.synthesis.exceptions import EvaluationResultsNotFoundError
from server.modules.synthesis.service import get_evaluation_results
from sqlalchemy.exc import IntegrityError

from .assessment_service import read_assessment
from .exceptions import ITSOError
from .verification import VerificationError


class SafeRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={"detail": {"code": "invalid_itso_request"}},
                )
            except ITSOError as exc:
                return JSONResponse(
                    status_code=exc.status, content={"detail": {"code": exc.code}}
                )
            except VerificationError as exc:
                return JSONResponse(
                    status_code=exc.http_status,
                    content={"detail": {"code": exc.code.value}},
                )
            except (
                LookupError,
                EvaluationNotFoundError,
                EvaluationResultsNotFoundError,
            ):
                return JSONResponse(
                    status_code=404, content={"detail": {"code": "not_found"}}
                )
            except IntegrityError:
                return JSONResponse(
                    status_code=409,
                    content={"detail": {"code": "concurrent_itso_update"}},
                )
            except ValueError:
                return JSONResponse(
                    status_code=422, content={"detail": {"code": "invalid_itso_scope"}}
                )

        return handler


router = APIRouter(tags=["itso"], route_class=SafeRoute)


@router.get("/evaluations/{evaluation_id}/assessment")
def assessment(
    evaluation_id: UUID,
    user=Depends(require_authenticated_user),
    db=Depends(get_db_session),
):
    result = read_assessment(
        db,
        evaluation_id=evaluation_id,
        actor_id=user.id,
        role=user.role.value,
        evaluator_permissions=user.evaluator_permissions,
    )
    if result is not None:
        return result
    legacy = get_evaluation_results(
        evaluation_id,
        user.id,
        db=db,
        evaluator_permissions=user.evaluator_permissions,
        current_user_role=user.role.value,
    )
    return {"contract": "legacy.v1", "result": legacy.model_dump(mode="json")}
