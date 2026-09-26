"""apps/server/modules/training_data/router.py"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from server.core.config import get_settings
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin
from server.modules.auth.service import AuthenticatedUser
from server.modules.training_data.adapters import (
    list_trained_adapters,
    store_adapter_upload,
)
from server.modules.training_data.exceptions import (
    AdapterUploadError,
    EmptyTrainingDatasetError,
    InvalidAgentIdError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.job_packages import preview_dataset_manifest
from server.modules.training_data.jobs import (
    create_training_job,
    get_job_download_package,
    list_training_jobs,
)
from server.modules.training_data.paths import MAX_ADAPTER_UPLOAD_BYTES
from server.modules.training_data.schemas import (
    TrainedAdapterListResponse,
    TrainedAdapterResponse,
    TrainingDatasetReadinessResponse,
    TrainingJobCreateResponse,
    TrainingJobListItem,
    TrainingJobListResponse,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/training-data", tags=["training-data"])


def _build_url(request: Request, path: str) -> str:
    """Build an absolute URL for the given API-relative path.

    Uses the configured api_prefix directly rather than
    ``request.scope["root_path"]``: this router is mounted onto an
    ``APIRouter(prefix=settings.api_prefix)`` included into the app, not
    behind an ASGI sub-application, so ``root_path`` stays empty in both
    the test client and production and cannot be relied on here.
    """
    base = str(request.base_url).rstrip("/")
    api_prefix = get_settings().api_prefix
    return f"{base}{api_prefix}{path}"


@router.post(
    "/{agent_id}/jobs",
    response_model=TrainingJobCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_training_job(
    agent_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainingJobCreateResponse:
    try:
        result = create_training_job(db, agent_id, current_user.id)
    except InvalidAgentIdError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except EmptyTrainingDatasetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    download_path = (
        f"/admin/training-data/jobs/{result.job.job_id}/download"
        f"?token={result.raw_download_token}"
    )
    upload_path = (
        f"/admin/training-data/jobs/{result.job.job_id}/adapter"
        f"?token={result.raw_upload_token}"
    )

    return TrainingJobCreateResponse(
        job_id=result.job.job_id,
        agent_id=result.job.agent_id,
        status=result.job.status,
        download_url=_build_url(request, download_path),
        upload_url=_build_url(request, upload_path),
        download_expires_at=result.job.download_expires_at,
        upload_expires_at=result.job.upload_expires_at,
        created_at=result.job.created_at,
    )


@router.get("/jobs/{job_id}/download")
def download_training_job_package(
    job_id: uuid.UUID,
    token: str = Query(...),
    db: Session = Depends(get_db_session),
) -> Response:
    try:
        zip_bytes = get_job_download_package(db, job_id, token)
    except TrainingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc

    return Response(content=zip_bytes, media_type="application/zip")


@router.post(
    "/jobs/{job_id}/adapter",
    response_model=TrainedAdapterResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_trained_adapter(
    job_id: uuid.UUID,
    token: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterResponse:
    # This metadata check is only an early rejection. The artifact layer
    # independently enforces the authoritative limit while streaming.
    if file.size is not None and file.size > MAX_ADAPTER_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"file exceeds max size of {MAX_ADAPTER_UPLOAD_BYTES} bytes",
        )
    try:
        adapter = store_adapter_upload(
            db, job_id, token, filename=file.filename or "", source=file.file
        )
    except TrainingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc
    except AdapterUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return TrainedAdapterResponse.model_validate(adapter)


@router.get("/{agent_id}/jobs", response_model=TrainingJobListResponse)
def get_training_jobs(
    agent_id: str,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainingJobListResponse:
    jobs = list_training_jobs(db, agent_id)
    return TrainingJobListResponse(
        agent_id=agent_id,
        jobs=[TrainingJobListItem.from_job(j) for j in jobs],
    )


@router.get("/{agent_id}/readiness", response_model=TrainingDatasetReadinessResponse)
def get_dataset_readiness(
    agent_id: str,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainingDatasetReadinessResponse:
    try:
        manifest = preview_dataset_manifest(db, agent_id)
    except InvalidAgentIdError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return TrainingDatasetReadinessResponse(
        agent_id=agent_id,
        pair_count=manifest.pair_count,
        evaluation_count=manifest.evaluation_count,
        reviewer_count=manifest.reviewer_count,
        skipped_counts=manifest.skipped_counts,
        pairs_sha256=manifest.pairs_sha256,
        export_timestamp=manifest.export_timestamp,
    )


@router.get("/{agent_id}/adapters", response_model=TrainedAdapterListResponse)
def get_trained_adapters(
    agent_id: str,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterListResponse:
    adapters = list_trained_adapters(db, agent_id)
    return TrainedAdapterListResponse(
        agent_id=agent_id,
        adapters=[TrainedAdapterResponse.model_validate(a) for a in adapters],
    )


__all__ = ["router"]
