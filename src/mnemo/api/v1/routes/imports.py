"""
CSV import routes.
Per spec section 10: CSV Import.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token, require_user_scope
from mnemo.api.utils import _error_response
from mnemo.core.config import get_settings
from mnemo.core.constants import ErrorCode, ImportMode, PermissionScope
from mnemo.core.exceptions import DeckNameConflictError
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.import_job import ImportJobCreateResponse, ImportJobStatusResponse
from mnemo.services import deck as deck_service
from mnemo.services import import_job as import_service
from mnemo.utils.local_time import to_local_time

router = APIRouter(prefix="/import", tags=["import"])
_db_dep = Depends(get_db)
_current_user_dep = Depends(get_current_user_from_token)
_file_dep = File(...)
_deck_id_form = Form(None)
_deck_name_form = Form(None)
_mode_form = Form(ImportMode.MERGE)
settings = get_settings()


@router.post(
    "/csv",
    status_code=202,
    response_model=ImportJobCreateResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.IMPORT_WRITE))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Upload CSV and start import job",
)
async def import_csv(
    file: UploadFile = _file_dep,
    deck_id: str | None = _deck_id_form,
    deck_name: str | None = _deck_name_form,
    mode: ImportMode = _mode_form,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> ImportJobCreateResponse | JSONResponse:
    raw = await file.read()
    await file.close()

    if len(raw) > settings.csv_max_size_bytes:
        return _error_response(
            ErrorCode.INVALID_CSV_FORMAT,
            f"CSV exceeds max size of {settings.csv_max_size_bytes} bytes.",
            400,
        )

    try:
        file_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _error_response(
            ErrorCode.INVALID_CSV_FORMAT,
            "CSV must be UTF-8 encoded.",
            400,
        )

    if not file_text.strip():
        return _error_response(
            ErrorCode.INVALID_CSV_FORMAT,
            "CSV file is empty.",
            400,
        )

    deck = None
    if deck_id:
        deck = await deck_service.get_deck_by_id(db, current_user.id, deck_id)
        if deck is None:
            return _error_response(
                ErrorCode.DECK_NOT_FOUND, f"No deck found with ID {deck_id}.", 404
            )
    else:
        if not deck_name:
            return _error_response(
                ErrorCode.VALIDATION_ERROR,
                "deck_name is required when deck_id is not provided.",
                400,
            )
        try:
            deck = await deck_service.create_deck(
                db,
                user_id=current_user.id,
                name=deck_name,
                description=None,
                tags=[],
            )
        except DeckNameConflictError as exc:
            return _error_response(ErrorCode.DECK_NAME_CONFLICT, str(exc), 409)

    resolved_deck_id = deck.id if deck is not None else deck_id
    if resolved_deck_id is None:
        return _error_response(
            ErrorCode.VALIDATION_ERROR,
            "deck_id could not be resolved for import.",
            400,
        )
    job = await import_service.create_import_job(
        db,
        user_id=current_user.id,
        deck_id=resolved_deck_id,
        mode=mode,
        file_text=file_text,
        original_filename=file.filename,
    )

    enqueued = await import_service.enqueue_import_job(job.id)
    if not enqueued and settings.is_production:
        await db.rollback()
        return _error_response(
            ErrorCode.IMPORT_SERVICE_DOWN,
            "Import queue is unavailable. Try again shortly.",
            503,
        )

    return ImportJobCreateResponse(
        job_id=job.id,
        status=job.status,
        deck_id=job.deck_id,
    )


@router.get(
    "/{job_id}",
    response_model=ImportJobStatusResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.IMPORT_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Get import job status",
)
async def get_import_job(
    job_id: str,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> ImportJobStatusResponse | JSONResponse:
    job = await import_service.get_import_job(db, user_id=current_user.id, job_id=job_id)
    if job is None:
        return _error_response(ErrorCode.VALIDATION_ERROR, f"No job found with ID {job_id}.", 404)

    completed_local = (
        to_local_time(job.completed_at, current_user.timezone) if job.completed_at else None
    )
    return ImportJobStatusResponse(
        job_id=job.id,
        status=job.status,
        cards_imported=job.cards_imported,
        cards_skipped=job.cards_skipped,
        errors=job.errors,
        completed_at=job.completed_at,
        completed_at_local=completed_local,
    )
