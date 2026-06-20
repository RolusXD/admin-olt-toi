from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession
from app.schemas.entities import ImportJobRead
from app.services.initial_import_service import ImportCriticalError, InitialImportService, SnapshotValidationError

router = APIRouter(tags=["import"])


@router.get("/import/jobs/{job_id}", response_model=ImportJobRead)
def get_initial_import_job(job_id: int, db: DbSession) -> dict:
    try:
        return InitialImportService(db).get_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/import-jobs/{job_id}", response_model=ImportJobRead)
def get_initial_import_job_alias(job_id: int, db: DbSession) -> dict:
    try:
        return InitialImportService(db).get_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/import-jobs/{import_job_id}/confirm")
def confirm_initial_import_job(import_job_id: int, db: DbSession) -> dict:
    try:
        return InitialImportService(db).confirm_import(import_job_id)
    except SnapshotValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ImportCriticalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
