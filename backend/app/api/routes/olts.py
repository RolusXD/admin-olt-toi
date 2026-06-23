from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import DbSession, get_olt_or_404
from app.drivers.errors import DriverCommandError
from app.core.config import settings
from app.models.entities import ConfigSnapshot, DriverCommandLog, GponProfile, ImportJob, Olt, OltCard, OltTechnicalSettings, OltUplink, Onu, PonPort, Vlan
from app.repositories.entities import OltRepository
from app.schemas.entities import (
    ImportConfirmResponse,
    DriverCommandLogRead,
    ImportJobRead,
    ImportPreviewResponse,
    ImportPreviewTextRequest,
    OltCreate,
    OltCardRead,
    OltPowerSyncResult,
    OltInventorySummary,
    OltDataQualitySummary,
    OltRead,
    OltSyncResult,
    OltTechnicalSettingsRead,
    OltUplinkRead,
    OltUpdate,
    PonPortTechnicalRead,
    TelnetDebugResult,
    TelnetTestResult,
    UnauthorizedOnuDiscoveryResult,
    VlanTechnicalRead,
)
from app.services.initial_import_service import ImportCriticalError, InitialImportService, SnapshotValidationError
from app.services.onu_discovery_service import OnuDiscoveryService
from app.services.olt_cli_service import OltCliService
from app.services.olt_service import OltService
from app.services.onu_data_quality_service import (
    DATA_QUALITY_BLOCKED,
    DATA_QUALITY_COMPLETE,
    DATA_QUALITY_LEGACY_INCOMPLETE,
    DATA_QUALITY_NEEDS_REVIEW,
)

router = APIRouter(prefix="/olts", tags=["olts"])


@router.get("", response_model=list[OltRead])
def list_olts(
    db: DbSession,
    environment: str | None = Query(default=None),
    include_incomplete: bool = Query(default=False),
) -> list:
    statement = select(Olt)
    if not include_incomplete:
        statement = statement.where(Olt.initial_import_status == "confirmed")
    if environment:
        statement = statement.where(Olt.environment == environment.strip().lower())
    return list(db.scalars(statement.order_by(Olt.environment.desc(), Olt.olt_code)))


@router.post("/{olt_id}/cancel-import", response_model=OltRead)
def cancel_olt_import(olt_id: int, db: DbSession):
    olt = get_olt_or_404(db, olt_id)
    if olt.initial_import_status == "confirmed":
        raise HTTPException(status_code=409, detail="No se puede cancelar una OLT con importacion confirmada")
    if olt.last_import_job_id:
        job = db.get(ImportJob, olt.last_import_job_id)
        if job and job.status != "confirmed":
            job.status = "cancelled"
            snapshot = db.get(ConfigSnapshot, job.raw_config_snapshot_id)
            if snapshot and snapshot.status != "confirmed":
                snapshot.status = "cancelled"
    olt.initial_import_status = "cancelled"
    db.commit()
    db.refresh(olt)
    return olt


@router.post("", response_model=OltRead, status_code=status.HTTP_201_CREATED)
def create_olt(payload: OltCreate, db: DbSession):
    try:
        return OltService(db).create(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{olt_id}", response_model=OltRead)
def get_olt(olt_id: int, db: DbSession):
    return get_olt_or_404(db, olt_id)


@router.get("/{olt_id}/cards", response_model=list[OltCardRead])
def olt_cards(olt_id: int, db: DbSession) -> list[OltCard]:
    get_olt_or_404(db, olt_id)
    return list(db.scalars(select(OltCard).where(OltCard.olt_id == olt_id).order_by(OltCard.slot_number)))


@router.get("/{olt_id}/uplinks", response_model=list[OltUplinkRead])
def olt_uplinks(olt_id: int, db: DbSession) -> list[OltUplink]:
    get_olt_or_404(db, olt_id)
    return list(db.scalars(select(OltUplink).where(OltUplink.olt_id == olt_id).order_by(OltUplink.interface_name)))


@router.get("/{olt_id}/advanced", response_model=OltTechnicalSettingsRead)
def olt_advanced(olt_id: int, db: DbSession) -> OltTechnicalSettings:
    get_olt_or_404(db, olt_id)
    settings = db.scalar(select(OltTechnicalSettings).where(OltTechnicalSettings.olt_id == olt_id))
    if not settings:
        settings = OltTechnicalSettings(olt_id=olt_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/{olt_id}/pon-ports", response_model=list[PonPortTechnicalRead])
def olt_pon_ports(olt_id: int, db: DbSession) -> list[dict]:
    get_olt_or_404(db, olt_id)
    ports = list(db.scalars(select(PonPort).where(PonPort.olt_id == olt_id).order_by(PonPort.slot, PonPort.port)))
    rows = []
    for port in ports:
        imported_total = db.scalar(select(func.count()).select_from(Onu).where(Onu.pon_port_id == port.id)) or 0
        imported_online = db.scalar(select(func.count()).select_from(Onu).where(Onu.pon_port_id == port.id, Onu.status.in_(["online", "working"]))) or 0
        total = port.total_count or imported_total
        online = port.online_count or imported_online
        avg_rx = db.scalar(select(func.avg(Onu.rx_power)).where(Onu.pon_port_id == port.id, Onu.rx_power.is_not(None)))
        data = PonPortTechnicalRead.model_validate(port).model_dump()
        data.update(
            {
                "online_onus": online,
                "total_onus": total,
                "load_percent": port.occupancy_percent or (round((total / 128) * 100, 2) if total else 0),
                "avg_rx_power": round(float(avg_rx), 2) if avg_rx is not None else None,
            }
        )
        rows.append(data)
    return rows


@router.post("/{olt_id}/sync-cards")
def sync_cards(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).sync_cards(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/sync-pon-status")
def sync_pon_status(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).sync_pon_status(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/discover-uplinks")
def discover_uplinks(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).discover_uplinks(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/sync-uplinks")
def sync_uplinks(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).sync_uplinks(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{olt_id}/vlans", response_model=list[VlanTechnicalRead])
def olt_vlans(olt_id: int, db: DbSession) -> list[dict]:
    get_olt_or_404(db, olt_id)
    rows = []
    for vlan in db.scalars(select(Vlan).where(Vlan.olt_id == olt_id).order_by(Vlan.vlan_id)):
        count = db.scalar(select(func.count()).select_from(Onu).where(Onu.olt_id == olt_id, Onu.vlan == vlan.vlan_id)) or 0
        data = VlanTechnicalRead.model_validate(vlan).model_dump()
        service = (vlan.service_type or "").lower()
        data.update(
            {
                "onu_count": count,
                "used_iptv": service == "iptv",
                "used_management_voip": service in {"management", "voip", "gestion"},
                "dhcp_snooping": False,
                "lan_to_lan": False,
            }
        )
        rows.append(data)
    return rows


@router.get("/{olt_id}/inventory-summary", response_model=OltInventorySummary)
def inventory_summary(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    last_confirmed_import = db.scalar(
        select(ImportJob.confirmed_at)
        .where(ImportJob.olt_id == olt_id, ImportJob.status == "confirmed")
        .order_by(ImportJob.confirmed_at.desc())
        .limit(1)
    )
    return {
        "olt_id": olt_id,
        "olt_code": olt.olt_code,
        "olt_name": olt.name,
        "environment": olt.environment,
        "initial_import_status": olt.initial_import_status,
        "last_import_confirmed_at": olt.last_import_confirmed_at,
        "onus": db.scalar(select(func.count()).select_from(Onu).where(Onu.olt_id == olt_id)) or 0,
        "pon_ports": db.scalar(select(func.count()).select_from(PonPort).where(PonPort.olt_id == olt_id)) or 0,
        "vlans": db.scalar(select(func.count()).select_from(Vlan).where(Vlan.olt_id == olt_id)) or 0,
        "profiles": db.scalar(select(func.count()).select_from(GponProfile).where(GponProfile.olt_id == olt_id)) or 0,
        "last_confirmed_import": last_confirmed_import,
    }


@router.get("/{olt_id}/data-quality-summary", response_model=OltDataQualitySummary)
def olt_data_quality_summary(olt_id: int, db: DbSession) -> dict:
    """Resumen de calidad documental por OLT (Fase A2 – observabilidad).

    No aplica validaciones duras ni bloquea provisión; sólo expone
    métricas agregadas por estado de calidad documental.
    """

    get_olt_or_404(db, olt_id)

    total_onus = db.scalar(select(func.count()).select_from(Onu).where(Onu.olt_id == olt_id)) or 0

    def _count_by_status(status: str) -> int:
        return (
            db.scalar(
                select(func.count()).select_from(Onu).where(
                    Onu.olt_id == olt_id,
                    Onu.data_quality_status == status,
                )
            )
            or 0
        )

    complete = _count_by_status(DATA_QUALITY_COMPLETE)
    needs_review = _count_by_status(DATA_QUALITY_NEEDS_REVIEW)
    legacy_incomplete = _count_by_status(DATA_QUALITY_LEGACY_INCOMPLETE)
    blocked = _count_by_status(DATA_QUALITY_BLOCKED)

    quality_score = float(round((complete / total_onus) * 100, 2)) if total_onus else 0.0

    return {
        "olt_id": olt_id,
        "total_onus": total_onus,
        "complete": complete,
        "needs_review": needs_review,
        "legacy_incomplete": legacy_incomplete,
        "blocked": blocked,
        "quality_score": quality_score,
    }


@router.put("/{olt_id}", response_model=OltRead)
def replace_olt(olt_id: int, payload: OltUpdate, db: DbSession):
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltService(db).update(olt, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{olt_id}", response_model=OltRead)
def update_olt(olt_id: int, payload: OltUpdate, db: DbSession):
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltService(db).update(olt, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{olt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_olt(olt_id: int, db: DbSession) -> None:
    olt = get_olt_or_404(db, olt_id)
    OltRepository(db).delete(olt)


@router.post("/{olt_id}/test-connection")
def test_connection(olt_id: int, db: DbSession) -> dict[str, bool]:
    olt = get_olt_or_404(db, olt_id)
    try:
        return {"healthy": OltService(db).test_connection(olt)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/telnet-test", response_model=TelnetTestResult)
def telnet_test(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).telnet_test(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/telnet-debug", response_model=TelnetDebugResult)
def telnet_debug(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).telnet_debug(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/sync-onus", response_model=OltSyncResult)
def sync_onus(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).sync_onus(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/sync-power", response_model=OltPowerSyncResult)
def sync_power(
    olt_id: int,
    db: DbSession,
    limit: int | None = Query(default=None, ge=1),
    only_onu_interfaces: list[str] | None = Body(default=None),
) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).sync_power(olt, limit=limit, only_onu_interfaces=only_onu_interfaces)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/discover-unauthorized-onus", response_model=UnauthorizedOnuDiscoveryResult)
def discover_unauthorized_onus(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OnuDiscoveryService(db).discover(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/read-only-check")
def read_only_check(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return OltCliService(db).read_only_check(olt)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{olt_id}/command-logs", response_model=list[DriverCommandLogRead])
def command_logs(
    olt_id: int,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=500),
    olt_code: str | None = Query(default=None),
    environment: str | None = Query(default=None),
) -> list[DriverCommandLog]:
    get_olt_or_404(db, olt_id)
    statement = select(DriverCommandLog).where(DriverCommandLog.olt_id == olt_id)
    if olt_code:
        statement = statement.join(Olt, DriverCommandLog.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if environment:
        if not olt_code:
            statement = statement.join(Olt, DriverCommandLog.olt_id == Olt.id)
        statement = statement.where(Olt.environment == environment.strip().lower())
    return list(db.scalars(statement.order_by(DriverCommandLog.created_at.desc()).limit(limit)))


@router.post("/{olt_id}/import/preview", response_model=ImportPreviewResponse)
def initial_import_preview(olt_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return InitialImportService(db).preview(olt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
@router.post("/{olt_id}/import/preview-from-telnet", response_model=ImportPreviewResponse)
def initial_import_preview_from_telnet(olt_id: int, db: DbSession) -> dict:
    try:
        return InitialImportService(db).create_preview_from_telnet(olt_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DriverCommandError as exc:
        # In diagnostic mode we expose a small sanitized excerpt of the
        # underlying CLI output to help identify prompt/pagination issues.
        if settings.telnet_diagnostic_mode:
            diagnostic = {
                "command": getattr(exc, "command", ""),
                "output_excerpt": (exc.output or "")[:500],
            }
            raise HTTPException(
                status_code=500,
                detail={
                    "message": str(exc),
                    "diagnostic": diagnostic,
                },
            )
        # Default behaviour (production): simple error message without
        # exposing CLI output.
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/import/preview-from-file", response_model=ImportPreviewResponse)
async def initial_import_preview_from_file(olt_id: int, db: DbSession, file: UploadFile = File(...)) -> dict:
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .txt")
    raw_bytes = await file.read()
    try:
        raw_config = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_config = raw_bytes.decode("latin-1")
    try:
        return InitialImportService(db).create_preview_from_text(olt_id, raw_config, source="file")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/import/preview-from-telnet", response_model=ImportPreviewResponse)
def initial_import_preview_from_telnet(olt_id: int, db: DbSession) -> dict:
    try:
        return InitialImportService(db).create_preview_from_telnet(olt_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{olt_id}/import/confirm/{import_job_id}", response_model=ImportConfirmResponse)
def initial_import_confirm(olt_id: int, import_job_id: int, db: DbSession) -> dict:
    olt = get_olt_or_404(db, olt_id)
    try:
        return InitialImportService(db).confirm(olt, import_job_id)
    except SnapshotValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ImportCriticalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{olt_id}/import/jobs", response_model=list[ImportJobRead])
def list_initial_import_jobs(olt_id: int, db: DbSession) -> list[dict]:
    olt = get_olt_or_404(db, olt_id)
    return InitialImportService(db).list_jobs(olt)


@router.get("/{olt_id}/import-jobs", response_model=list[ImportJobRead])
def list_initial_import_jobs_alias(olt_id: int, db: DbSession) -> list[dict]:
    olt = get_olt_or_404(db, olt_id)
    return InitialImportService(db).list_jobs(olt)


@router.post("/{olt_id}/backup")
def backup(olt_id: int, db: DbSession) -> dict[str, str]:
    olt = get_olt_or_404(db, olt_id)
    backup_file = OltService(db).backup(olt)
    return {"file_path": backup_file.file_path}
