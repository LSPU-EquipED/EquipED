"""apps/server/modules/training_data/router.py"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from server.core.config import get_settings
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin
from server.modules.auth.service import AuthenticatedUser
from server.modules.training_data.adapters import (
    list_trained_adapters,
    store_adapter_upload,
)
from server.modules.training_data.exceptions import (
    AdapterAgentMismatchError,
    AdapterNotFoundError,
    AdapterNotLoadedError,
    AdapterUploadError,
    EmptyTrainingDatasetError,
    GgufAlreadyExistsError,
    GgufInUseError,
    GgufNotFoundError,
    GgufUploadError,
    HostKeyInvalidError,
    InvalidAgentIdError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.gguf_files import (
    MAX_GGUF_BYTES,
    build_download_link,
    issue_gguf_upload_token,
    open_gguf_stream,
    remove_gguf,
    store_gguf,
    verify_gguf_upload_token,
)
from server.modules.training_data.host_keys import (
    authenticate_host_key,
    create_host_key,
    get_active_key,
    list_host_manifest,
    revoke_host_key,
)
from server.modules.training_data.job_packages import preview_dataset_manifest
from server.modules.training_data.jobs import (
    create_training_job,
    get_job_download_package,
    list_training_jobs,
    mark_run_stage,
    report_run_status,
)
from server.modules.training_data.models import TrainedAdapter
from server.modules.training_data.notebook import build_job_notebook
from server.modules.training_data.paths import MAX_ADAPTER_UPLOAD_BYTES
from server.modules.training_data.publication import (
    get_adapter_for_agent,
    get_publication,
    publish_adapter,
    unpublish_adapter,
)
from server.modules.training_data.schemas import (
    GgufDownloadLinkResponse,
    HostKeyCreatedResponse,
    HostManifestResponse,
    HostStateResponse,
    PublishAdapterRequest,
    RunStatusRequest,
    TrainedAdapterListItem,
    TrainedAdapterListResponse,
    TrainedAdapterResponse,
    TrainedAdapterUploadResponse,
    TrainingDatasetReadinessResponse,
    TrainingJobCreateResponse,
    TrainingJobListItem,
    TrainingJobListResponse,
    adapter_gguf_info,
)
from server.modules.training_data.serving import (
    get_server_adapter_state,
    gguf_filename,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/training-data", tags=["training-data"])


class GgufDownloadLinkRequest(BaseModel):
    expires_in_hours: int = Field(default=24, ge=1, le=168)


def _adapter_response(adapter: TrainedAdapter) -> TrainedAdapterResponse:
    response = TrainedAdapterResponse.model_validate(adapter)
    response.gguf = adapter_gguf_info(adapter)
    return response


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")


def _get_owned_adapter(db: Session, agent_id: str, adapter_id: uuid.UUID):
    adapter = db.get(TrainedAdapter, adapter_id)
    if adapter is None or adapter.agent_id != agent_id:
        raise _not_found()
    return adapter


def _check_gguf_upload(file: UploadFile) -> None:
    """Cheap early rejection; store_gguf enforces the real limits while reading."""
    if not (file.filename or "").lower().endswith(".gguf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="file must have a .gguf extension",
        )
    if file.size is not None and file.size > MAX_GGUF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"file exceeds max size of {MAX_GGUF_BYTES} bytes",
        )


def _gguf_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, GgufUploadError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, GgufNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    else:  # GgufAlreadyExistsError, GgufInUseError
        code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(exc))


_GGUF_ERRORS = (
    GgufUploadError,
    GgufAlreadyExistsError,
    GgufNotFoundError,
    GgufInUseError,
)


def _build_url(request: Request, path: str) -> str:
    """Build an absolute URL for the given API-relative path.

    The host comes from PUBLIC_BASE_URL when set, so links handed to Colab work
    through a tunnel. Otherwise it is the incoming request's own base URL, which
    is always local behind the admin dev proxy (it rewrites the Host header).

    Uses the configured api_prefix directly rather than
    ``request.scope["root_path"]``: this router is mounted onto an
    ``APIRouter(prefix=settings.api_prefix)`` included into the app, not
    behind an ASGI sub-application, so ``root_path`` stays empty in both
    the test client and production and cannot be relied on here.
    """
    settings = get_settings()
    base = settings.public_base_url or str(request.base_url).rstrip("/")
    return f"{base}{settings.api_prefix}{path}"


def _host_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")


def _require_host_key(
    db: Session = Depends(get_db_session),
    x_host_sync_key: str | None = Header(default=None, alias="X-Host-Sync-Key"),
):
    try:
        return authenticate_host_key(db, x_host_sync_key)
    except HostKeyInvalidError as exc:
        raise _host_not_found() from exc


@router.get("/host", response_model=HostStateResponse)
def get_host_state(
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> HostStateResponse:
    key = get_active_key(db)
    if key is None:
        return HostStateResponse(has_active_key=False)
    return HostStateResponse(
        has_active_key=True, created_at=key.created_at, last_seen_at=key.last_seen_at
    )


@router.post(
    "/host/key",
    response_model=HostKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_host_sync_key(
    current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> HostKeyCreatedResponse:
    row, raw = create_host_key(db, current_user.id)
    return HostKeyCreatedResponse(key=raw, created_at=row.created_at)


@router.delete("/host/key", status_code=status.HTTP_204_NO_CONTENT)
def revoke_host_sync_key(
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> Response:
    revoke_host_key(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/host/manifest", response_model=HostManifestResponse)
def get_host_manifest(
    _key=Depends(_require_host_key),
    db: Session = Depends(get_db_session),
) -> HostManifestResponse:
    return HostManifestResponse(adapters=list_host_manifest(db))


@router.get("/host/gguf/{adapter_id}")
def stream_host_gguf(
    adapter_id: uuid.UUID,
    _key=Depends(_require_host_key),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    adapter = db.get(TrainedAdapter, adapter_id)
    if adapter is None or not adapter.gguf_storage_key:
        raise _host_not_found()
    try:
        chunks, size = open_gguf_stream(adapter)
    except (GgufNotFoundError, FileNotFoundError) as exc:
        raise _host_not_found() from exc
    name = gguf_filename(adapter.agent_id, adapter.version)
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}
    if size is not None:
        headers["Content-Length"] = str(size)
    return StreamingResponse(
        chunks, media_type="application/octet-stream", headers=headers
    )


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

    status_path = (
        f"/admin/training-data/jobs/{result.job.job_id}/status"
        f"?token={result.raw_status_token}"
    )

    download_url = _build_url(request, download_path)
    upload_url = _build_url(request, upload_path)
    status_url = _build_url(request, status_path)

    notebook: str | None = None
    notebook_filename: str | None = None
    try:
        notebook = build_job_notebook(download_url, upload_url, status_url=status_url)
        notebook_filename = (
            f"equiped-{result.job.agent_id}-run-{str(result.job.job_id)[:8]}.ipynb"
        )
    except Exception:
        # The notebook is a convenience; the links alone are enough to train.
        logger.warning("could not build the training notebook", exc_info=True)
        notebook = None

    return TrainingJobCreateResponse(
        job_id=result.job.job_id,
        agent_id=result.job.agent_id,
        status=result.job.status,
        download_url=download_url,
        upload_url=upload_url,
        download_expires_at=result.job.download_expires_at,
        upload_expires_at=result.job.upload_expires_at,
        created_at=result.job.created_at,
        notebook=notebook,
        notebook_filename=notebook_filename,
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


@router.post("/jobs/{job_id}/status", status_code=status.HTTP_204_NO_CONTENT)
def report_training_status(
    job_id: uuid.UUID,
    body: RunStatusRequest,
    token: str = Query(...),
    db: Session = Depends(get_db_session),
) -> Response:
    try:
        report_run_status(
            db,
            job_id,
            token,
            body.stage,
            step=body.step,
            total=body.total,
            message=body.message,
        )
    except TrainingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/jobs/{job_id}/adapter",
    response_model=TrainedAdapterUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_trained_adapter(
    job_id: uuid.UUID,
    request: Request,
    token: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterUploadResponse:
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

    # Build the response first: issuing the token commits, and a dead
    # connection afterwards must not turn the stored upload into a 500.
    response_data = _adapter_response(adapter).model_dump()
    gguf_upload_url: str | None = None
    try:
        adapter_id = adapter.adapter_id
        raw = issue_gguf_upload_token(db, adapter)
        gguf_upload_url = _build_url(
            request,
            f"/admin/training-data/adapters/{adapter_id}/gguf?token={raw}",
        )
    except Exception:
        # The adapter zip is already stored; the GGUF link is a convenience.
        logger.warning("could not issue a GGUF upload link", exc_info=True)
        gguf_upload_url = None
        try:
            db.rollback()
        except Exception:
            logger.warning("rollback failed", exc_info=True)
    mark_run_stage(db, job_id, "converting")
    return TrainedAdapterUploadResponse(
        **response_data, gguf_upload_url=gguf_upload_url
    )


@router.post(
    "/adapters/{adapter_id}/gguf",
    response_model=TrainedAdapterResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_gguf_with_token(
    adapter_id: uuid.UUID,
    token: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterResponse:
    _check_gguf_upload(file)
    adapter = db.get(TrainedAdapter, adapter_id)
    if adapter is None or not verify_gguf_upload_token(adapter, token):
        raise _not_found()
    try:
        adapter = store_gguf(db, adapter, file.file, replace=False, token=token)
    except GgufNotFoundError as exc:
        raise _not_found() from exc
    except _GGUF_ERRORS as exc:
        raise _gguf_http_error(exc) from exc
    mark_run_stage(db, adapter.job_id, "finished")
    return _adapter_response(adapter)


@router.post(
    "/{agent_id}/adapters/{adapter_id}/gguf",
    response_model=TrainedAdapterResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_gguf_as_admin(
    agent_id: str,
    adapter_id: uuid.UUID,
    replace: bool = Query(False),
    file: UploadFile = File(...),
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterResponse:
    adapter = _get_owned_adapter(db, agent_id, adapter_id)
    _check_gguf_upload(file)
    try:
        adapter = store_gguf(db, adapter, file.file, replace=replace)
    except _GGUF_ERRORS as exc:
        raise _gguf_http_error(exc) from exc
    mark_run_stage(db, adapter.job_id, "finished")
    return _adapter_response(adapter)


@router.post(
    "/{agent_id}/adapters/{adapter_id}/gguf/download-link",
    response_model=GgufDownloadLinkResponse,
)
def create_gguf_download_link(
    agent_id: str,
    adapter_id: uuid.UUID,
    request: Request,
    body: GgufDownloadLinkRequest | None = None,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> GgufDownloadLinkResponse:
    adapter = _get_owned_adapter(db, agent_id, adapter_id)
    hours = (body or GgufDownloadLinkRequest()).expires_in_hours
    try:
        url = build_download_link(adapter, expires_in_seconds=hours * 3600)
    except _GGUF_ERRORS as exc:
        raise _gguf_http_error(exc) from exc
    if url is None:
        url = _build_url(
            request,
            f"/admin/training-data/{agent_id}/adapters/{adapter_id}/gguf/file",
        )
    return GgufDownloadLinkResponse(
        url=url,
        filename=gguf_filename(adapter.agent_id, adapter.version),
        sha256=adapter.gguf_sha256,
        size_bytes=adapter.gguf_size_bytes,
        expires_at=datetime.now(UTC) + timedelta(hours=hours),
    )


@router.get("/{agent_id}/adapters/{adapter_id}/gguf/file")
def stream_gguf_file(
    agent_id: str,
    adapter_id: uuid.UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    adapter = _get_owned_adapter(db, agent_id, adapter_id)
    try:
        chunks, size = open_gguf_stream(adapter)
    except (GgufNotFoundError, FileNotFoundError) as exc:
        raise _not_found() from exc
    name = gguf_filename(adapter.agent_id, adapter.version)
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}
    if size is not None:
        headers["Content-Length"] = str(size)
    return StreamingResponse(
        chunks, media_type="application/octet-stream", headers=headers
    )


@router.delete(
    "/{agent_id}/adapters/{adapter_id}/gguf",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_gguf_file(
    agent_id: str,
    adapter_id: uuid.UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> Response:
    adapter = _get_owned_adapter(db, agent_id, adapter_id)
    publication = get_publication(db, agent_id)
    try:
        remove_gguf(
            db,
            adapter,
            published_adapter_id=publication.adapter_id if publication else None,
        )
    except _GGUF_ERRORS as exc:
        raise _gguf_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


def _adapter_list_response(db: Session, agent_id: str) -> TrainedAdapterListResponse:
    adapters = list_trained_adapters(db, agent_id)
    state = get_server_adapter_state()
    publication = get_publication(db, agent_id)
    published_id = publication.adapter_id if publication else None
    items = []
    for adapter in adapters:
        base = _adapter_response(adapter).model_dump()
        items.append(
            TrainedAdapterListItem(
                **base,
                gguf_filename=gguf_filename(agent_id, adapter.version),
                loaded=(
                    state.find(agent_id, adapter.version) is not None
                    if state.reachable
                    else None
                ),
                published=adapter.adapter_id == published_id,
            )
        )
    return TrainedAdapterListResponse(
        agent_id=agent_id,
        adapters=items,
        published_adapter_id=published_id,
        server_reachable=state.reachable,
        unrecognized_server_adapters=list(state.unrecognized),
    )


@router.get("/{agent_id}/adapters", response_model=TrainedAdapterListResponse)
def get_trained_adapters(
    agent_id: str,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterListResponse:
    return _adapter_list_response(db, agent_id)


@router.put("/{agent_id}/published", response_model=TrainedAdapterListResponse)
def publish_trained_adapter(
    agent_id: str,
    body: PublishAdapterRequest,
    current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterListResponse:
    try:
        adapter = get_adapter_for_agent(db, agent_id, body.adapter_id)
        state = get_server_adapter_state()
        if not state.reachable or state.find(agent_id, adapter.version) is None:
            raise AdapterNotLoadedError(
                f"{gguf_filename(agent_id, adapter.version)} is not loaded on the "
                "model server (or the server cannot be reached)"
            )
        publish_adapter(db, agent_id, body.adapter_id, published_by=current_user.id)
    except AdapterNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except AdapterAgentMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except AdapterNotLoadedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _adapter_list_response(db, agent_id)


@router.delete("/{agent_id}/published", status_code=status.HTTP_204_NO_CONTENT)
def unpublish_trained_adapter(
    agent_id: str,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> Response:
    unpublish_adapter(db, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
