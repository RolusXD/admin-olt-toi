import json
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Nap, Olt, Onu, OnuEventHistory, OnuPowerHistory, OnuServiceModeTemplate, SpeedProfile, Vlan, Zone
from app.repositories.entities import OnuRepository, PowerRepository
from app.schemas.entities import OnuBehaviorRead, OnuDataQualityRead, OnuEventRead, OnuInternalInfoUpdate, OnuRead, OnuSchema, PowerSampleCreate, PowerSampleRead
from app.services.onu_service import OnuService

router = APIRouter(prefix="/onus", tags=["onus"])


@router.get("", response_model=list[OnuRead])
def list_onus(
    db: DbSession,
    q: str | None = Query(default=None),
    olt_id: int | None = None,
    olt_code: str | None = None,
    environment: str | None = None,
    zone_id: int | None = None,
    nap_id: int | None = None,
    status: str | None = None,
    serial_number: str | None = None,
    customer_name: str | None = None,
    onu_interface: str | None = None,
) -> list[Onu]:
    statement = select(Onu)
    if olt_code:
        statement = statement.join(Olt, Onu.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if environment:
        if not olt_code:
            statement = statement.join(Olt, Onu.olt_id == Olt.id)
        statement = statement.where(Olt.environment == environment.strip().lower())
    if q:
        like = f"%{q}%"
        statement = statement.where(
            Onu.customer_name.ilike(like) | Onu.serial_number.ilike(like) | Onu.onu_interface.ilike(like)
        )
    if olt_id is not None:
        statement = statement.where(Onu.olt_id == olt_id)
    if zone_id is not None:
        statement = statement.where(Onu.zone_id == zone_id)
    if nap_id is not None:
        statement = statement.where(Onu.nap_id == nap_id)
    if status:
        statement = statement.where(Onu.status == status)
    if serial_number:
        statement = statement.where(Onu.serial_number.ilike(f"%{serial_number}%"))
    if customer_name:
        statement = statement.where(Onu.customer_name.ilike(f"%{customer_name}%"))
    if onu_interface:
        statement = statement.where(Onu.onu_interface.ilike(f"%{onu_interface}%"))
    return list(db.scalars(statement.order_by(Onu.customer_name, Onu.serial_number)))


@router.get("/data-quality", response_model=list[OnuDataQualityRead])
def list_onus_data_quality(
    db: DbSession,
    olt_id: int | None = None,
    status: str | None = Query(default=None, description="data_quality_status"),
    zone: str | None = None,
    nap: str | None = None,
) -> list[OnuDataQualityRead]:
    """Listado de ONUs con enfoque en calidad documental (Fase A2).

    No introduce validaciones obligatorias ni bloqueos; sólo expone el
    `data_quality_status` y la lista de campos faltantes registrados
    por `OnuDataQualityService`.
    """

    statement = select(Onu)
    if olt_id is not None:
        statement = statement.where(Onu.olt_id == olt_id)
    if status:
        # Filtra por estado de calidad documental, no por estado operativo.
        statement = statement.where(Onu.data_quality_status == status)
    if zone:
        statement = statement.where(Onu.zone_name == zone)
    if nap:
        statement = statement.where(Onu.nap_name == nap)

    onus = list(db.scalars(statement.order_by(Onu.customer_name, Onu.serial_number)))
    results: list[OnuDataQualityRead] = []

    for onu in onus:
        missing: list[str] = []
        raw = getattr(onu, "data_quality_missing_fields", None)
        if raw:
            try:
                data = json.loads(raw)
            except Exception:
                missing = [str(raw)]
            else:
                if isinstance(data, list):
                    missing = [str(item) for item in data]
                else:
                    missing = [str(data)]

        results.append(
            OnuDataQualityRead(
                id=onu.id,
                olt_id=onu.olt_id,
                serial_number=onu.serial_number,
                customer_name=onu.customer_name,
                zone_name=onu.zone_name,
                nap_name=onu.nap_name,
                nap_port=onu.nap_port,
                data_quality_status=onu.data_quality_status,
                missing_fields=missing,
            )
        )

    return results


@router.post("", response_model=OnuRead, status_code=status.HTTP_201_CREATED)
def create_onu(payload: OnuSchema, db: DbSession) -> Onu:
    return OnuRepository(db).create(payload.model_dump())


@router.patch("/{onu_id}", response_model=OnuRead)
def update_onu(onu_id: int, payload: OnuSchema, db: DbSession) -> Onu:
    onu = db.get(Onu, onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")
    return OnuRepository(db).update(onu, payload.model_dump())


@router.patch("/{onu_id}/internal-info", response_model=OnuRead)
def update_onu_internal_info(onu_id: int, payload: OnuInternalInfoUpdate, db: DbSession) -> Onu:
    onu = db.get(Onu, onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("zone_id") is not None:
        zone = db.get(Zone, data["zone_id"])
        if not zone or zone.olt_id != onu.olt_id:
            raise HTTPException(status_code=422, detail="Zone does not belong to ONU OLT")
    if data.get("nap_id") is not None:
        nap = db.get(Nap, data["nap_id"])
        if not nap or nap.olt_id != onu.olt_id:
            raise HTTPException(status_code=422, detail="NAP does not belong to ONU OLT")
    for key, value in data.items():
        setattr(onu, key, value)
    db.commit()
    db.refresh(onu)
    return onu


@router.get("/{onu_id}", response_model=OnuRead)
def get_onu(onu_id: int, db: DbSession) -> Onu:
    """Detalle de ONU con bloque de comportamiento operacional de solo lectura.

    No ejecuta Telnet ni modifica datos; el bloque ``behavior`` se deriva a
    partir de Onu + catálogos internos (OnuServiceModeTemplate, Vlan,
    SpeedProfile, calidad documental).
    """

    onu = db.get(Onu, onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    # Reglas de mapeo de service_mode_code → modo simple / etiqueta
    service_mode_code = onu.service_mode_code or None
    mode_simple = "unknown"
    mode_label = "Desconocido/importado"

    if service_mode_code in {None, "", "unknown"}:
        mode_simple = "unknown"
        mode_label = "Desconocido/importado"
    elif service_mode_code == "router_iphost":
        mode_simple = "router"
        mode_label = "Router"
    elif service_mode_code == "bridge_tag_internet":
        mode_simple = "bridge"
        mode_label = "Bridge"
    elif service_mode_code == "transparent_special":
        mode_simple = "transparent"
        mode_label = "Transparente"

    behavior_warnings: list[str] = []
    behavior_template: OnuServiceModeTemplate | None = None

    if service_mode_code:
        behavior_template = db.scalar(
            select(OnuServiceModeTemplate).where(
                OnuServiceModeTemplate.olt_id == onu.olt_id,
                OnuServiceModeTemplate.mode_code == service_mode_code,
                OnuServiceModeTemplate.is_active.is_(True),
            )
        )
        if behavior_template is None:
            # Si no existe plantilla para el modo informado, degradar a modo desconocido
            # y registrar un aviso suave para UI.
            mode_simple = "unknown"
            mode_label = "Desconocido/importado"
            behavior_warnings.append(
                "Plantilla de modo de servicio no definida para este service_mode_code; comportamiento clasificado como desconocido/importado."
            )

    # Resolver VLAN y perfiles opcionales para enriquecer la vista
    behavior_vlan_name: str | None = None
    if onu.vlan:
        vlan = db.scalar(
            select(Vlan).where(
                Vlan.olt_id == onu.olt_id,
                Vlan.vlan_id == onu.vlan,
            )
        )
        if vlan and vlan.name:
            behavior_vlan_name = vlan.name

    behavior_speed_profile: SpeedProfile | None = None
    if onu.speed_profile_up and onu.speed_profile_down:
        behavior_speed_profile = db.scalar(
            select(SpeedProfile).where(
                SpeedProfile.olt_id == onu.olt_id,
                SpeedProfile.upstream_profile_name == onu.speed_profile_up,
                SpeedProfile.downstream_profile_name == onu.speed_profile_down,
            )
        )

    # Calidad documental: reinterpretar lista JSON de campos faltantes si existe
    missing_fields: list[str] = []
    raw_missing = getattr(onu, "data_quality_missing_fields", None)
    if raw_missing:
        try:
            data = json.loads(raw_missing)
        except Exception:
            missing_fields = [str(raw_missing)]
        else:
            if isinstance(data, list):
                missing_fields = [str(item) for item in data]
            else:
                missing_fields = [str(data)]

    # Adjuntar un atributo dinámico para que Pydantic pueda serializar OnuBehaviorRead
    setattr(
        onu,
        "behavior",
        OnuBehaviorRead(
            service_mode_code=service_mode_code,
            mode_simple=mode_simple,
            mode_label=mode_label,
            template_name=behavior_template.name if behavior_template else None,
            mode_code=behavior_template.mode_code if behavior_template else service_mode_code,
            vlan_id=onu.vlan,
            vlan_name=behavior_vlan_name,
            speed_profile_up=onu.speed_profile_up,
            speed_profile_down=onu.speed_profile_down or onu.speed_profile,
            speed_profile_code=behavior_speed_profile.profile_code if behavior_speed_profile else None,
            dhcp_source=behavior_template.dhcp_source if behavior_template else None,
            use_iphost=behavior_template.use_iphost if behavior_template else False,
            use_veip=behavior_template.use_veip if behavior_template else False,
            use_vlan_filter=behavior_template.use_vlan_filter if behavior_template else False,
            use_loop_detect=behavior_template.use_loop_detect if behavior_template else False,
            disable_wifi=behavior_template.disable_wifi if behavior_template else False,
            data_quality_status=onu.data_quality_status,
            data_quality_missing_fields=missing_fields,
            warnings=behavior_warnings,
        ),
    )

    return onu


@router.delete("/{onu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_onu(onu_id: int, db: DbSession) -> None:
    onu = db.get(Onu, onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")
    OnuRepository(db).delete(onu)


@router.post("/{onu_id}/power", response_model=PowerSampleRead)
def add_power(onu_id: int, payload: PowerSampleCreate, db: DbSession):
    return OnuService(db).add_power_sample(onu_id, payload.rx_power, payload.tx_power)


@router.get("/{onu_id}/power", response_model=list[PowerSampleRead])
def power_history(onu_id: int, db: DbSession):
    return [sample for sample in PowerRepository(db).list() if sample.onu_id == onu_id]


@router.get("/{onu_id}/power-history", response_model=list[PowerSampleRead])
def onu_power_history(onu_id: int, db: DbSession) -> list[OnuPowerHistory]:
    return list(
        db.scalars(
            select(OnuPowerHistory)
            .where(OnuPowerHistory.onu_id == onu_id)
            .order_by(OnuPowerHistory.created_at.desc())
        )
    )


@router.get("/{onu_id}/events", response_model=list[OnuEventRead])
def onu_events(onu_id: int, db: DbSession) -> list[OnuEventHistory]:
    return list(
        db.scalars(
            select(OnuEventHistory)
            .where(OnuEventHistory.onu_id == onu_id)
            .order_by(OnuEventHistory.created_at.desc())
            .limit(50)
        )
    )
