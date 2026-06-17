from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    GponProfile,
    Nap,
    NapPort,
    Olt,
    Onu,
    OnuType,
    ProfileCatalog,
    ProvisioningPlan,
    ProvisioningTemplate,
    ProvisioningValidationResult,
    SpeedProfile,
    UnauthorizedOnu,
    Vlan,
    Zone,
)
from app.schemas.entities import ProvisioningPlanCreate


VALID_PLAN_STATUSES = {"draft", "validated", "validation_failed", "approved", "executed", "cancelled"}
DEFAULT_TEMPLATE_BODY = """interface {pon_port_interface}
onu {onu_index} type {onu_type} sn {serial_number}
exit
interface {onu_interface}
name {customer_name_cli}
description zone_{zone_name}_descr_Nap_{nap_name}_Puerto_{nap_port}
tcont 1 profile {speed_profile_up}
gemport 1 traffic-limit downstream {speed_profile_down}
switchport vlan {vlan} tag vport 1
exit"""


@dataclass
class ValidationResult:
    is_valid: bool
    warnings: list[str]
    errors: list[str]
    suggested_onu_id: int | None
    selected_onu_id: int | None
    occupied_onu_ids: list[int]
    cli_preview: str
    validated_at: datetime


class ProvisioningService:
    """Dry-run provisioning planner.

    This service intentionally does not import OLT drivers and never opens
    Telnet/SSH sessions. It only reads inventory tables and generates CLI text.
    """

    def __init__(self, db: Session):
        self.db = db

    def can_provision(self, olt_id: int) -> bool:
        olt = self.db.get(Olt, olt_id)
        return bool(olt and olt.initial_import_status == "confirmed")

    def list_plans(
        self,
        *,
        olt_id: int | None = None,
        status: str | None = None,
        serial_number: str | None = None,
    ) -> list[ProvisioningPlan]:
        statement = select(ProvisioningPlan).order_by(ProvisioningPlan.created_at.desc())
        if olt_id is not None:
            statement = statement.where(ProvisioningPlan.olt_id == olt_id)
        if status:
            statement = statement.where(ProvisioningPlan.status == status)
        if serial_number:
            statement = statement.where(ProvisioningPlan.serial_number.ilike(f"%{serial_number.strip()}%"))
        return list(self.db.scalars(statement))

    def get_plan(self, plan_id: int) -> ProvisioningPlan | None:
        return self.db.get(ProvisioningPlan, plan_id)

    def create_plan(self, payload: ProvisioningPlanCreate) -> ProvisioningPlan:
        unauthorized = self.db.get(UnauthorizedOnu, payload.unauthorized_onu_id)
        if not unauthorized:
            raise HTTPException(status_code=404, detail="ONU pendiente no encontrada")
        olt = self.db.get(Olt, unauthorized.olt_id)
        if not olt:
            raise HTTPException(status_code=404, detail="OLT no encontrada")
        speed_profile = self.db.get(SpeedProfile, payload.speed_profile_id) if payload.speed_profile_id else None
        upload_profile = self.db.get(ProfileCatalog, payload.upload_profile_id) if payload.upload_profile_id else None
        download_profile = self.db.get(ProfileCatalog, payload.download_profile_id) if payload.download_profile_id else None
        speed_profile_up = upload_profile.name if upload_profile else speed_profile.upstream_profile_name if speed_profile else payload.speed_profile_up
        speed_profile_down = (
            download_profile.name if download_profile else speed_profile.downstream_profile_name if speed_profile else payload.speed_profile_down
        )

        plan = ProvisioningPlan(
            olt_id=olt.id,
            olt_code=olt.olt_code,
            unauthorized_onu_id=unauthorized.id,
            serial_number=unauthorized.serial_number,
            pon_port_interface=unauthorized.pon_port_interface,
            customer_name=payload.customer_name,
            customer_reference=payload.customer_reference,
            technical_comment=payload.technical_comment,
            address=payload.address,
            notes=payload.notes,
            zone_id=payload.zone_id,
            nap_id=payload.nap_id,
            nap_port=payload.nap_port,
            onu_type=payload.onu_type,
            vlan=payload.vlan,
            speed_profile_up=speed_profile_up,
            speed_profile_down=speed_profile_down,
            speed_profile_id=speed_profile.id if speed_profile else None,
            upload_profile_id=upload_profile.id if upload_profile else None,
            download_profile_id=download_profile.id if download_profile else None,
            selected_onu_id=payload.selected_onu_id,
            status="draft",
        )
        result = self.validate(plan)
        self._apply_validation(plan, result, update_status=False)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def validate_and_update(self, plan_id: int) -> tuple[ProvisioningPlan, ValidationResult]:
        plan = self.require_plan(plan_id)
        if plan.status in {"executed", "cancelled"}:
            raise HTTPException(status_code=409, detail=f"No se puede validar un plan en estado {plan.status}")
        result = self.validate(plan)
        self._apply_validation(plan, result, update_status=True)
        self.db.commit()
        self.db.refresh(plan)
        return plan, result

    def approve(self, plan_id: int) -> ProvisioningPlan:
        plan = self.require_plan(plan_id)
        if plan.status in {"executed", "cancelled"}:
            raise HTTPException(status_code=409, detail=f"No se puede aprobar un plan en estado {plan.status}")
        result = self.validate(plan)
        self._apply_validation(plan, result, update_status=True)
        if not result.is_valid:
            self.db.commit()
            raise HTTPException(status_code=409, detail={"message": "El plan tiene errores de validacion", "errors": result.errors})
        plan.status = "approved"
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def cancel(self, plan_id: int) -> ProvisioningPlan:
        plan = self.require_plan(plan_id)
        if plan.status == "executed":
            raise HTTPException(status_code=409, detail="No se puede cancelar un plan ejecutado")
        plan.status = "cancelled"
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def counts(self) -> dict[str, int]:
        rows = self.db.execute(
            select(ProvisioningPlan.status, func.count(ProvisioningPlan.id)).group_by(ProvisioningPlan.status)
        ).all()
        counts = {"draft": 0, "validated": 0, "validation_failed": 0, "approved": 0, "cancelled": 0}
        for status, count in rows:
            if status in counts:
                counts[status] = count
        return counts

    def require_plan(self, plan_id: int) -> ProvisioningPlan:
        plan = self.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan de aprovisionamiento no encontrado")
        return plan

    def validate(self, plan: ProvisioningPlan) -> ValidationResult:
        warnings: list[str] = []
        errors: list[str] = []
        validated_at = datetime.now(timezone.utc)

        olt = self.db.get(Olt, plan.olt_id)
        unauthorized = self.db.get(UnauthorizedOnu, plan.unauthorized_onu_id)
        zone = self.db.get(Zone, plan.zone_id)
        nap = self.db.get(Nap, plan.nap_id)
        template = self._default_template_object(olt)
        occupied_onu_ids = self.occupied_onu_ids(plan.olt_id, plan.pon_port_interface)
        suggested_onu_id = self.next_available_onu_id(occupied_onu_ids)
        selected_onu_id = plan.selected_onu_id or suggested_onu_id

        if not olt:
            errors.append("La OLT no existe.")
        if not unauthorized:
            errors.append("La ONU pendiente no existe.")
        elif unauthorized.status != "pending":
            errors.append(f"La ONU pendiente esta en estado {unauthorized.status}.")
        elif unauthorized.olt_id != plan.olt_id:
            errors.append("La ONU pendiente no pertenece a la OLT del plan.")
        elif unauthorized.pon_port_interface and plan.pon_port_interface != unauthorized.pon_port_interface:
            errors.append("El puerto PON del plan no coincide con la ONU pendiente.")
        if not zone:
            errors.append("La zona no existe.")
        if not nap:
            errors.append("La NAP no existe.")
        elif nap.zone_id != plan.zone_id:
            errors.append("La NAP no pertenece a la zona seleccionada.")

        occupied = self.db.scalar(
            select(Onu).where(
                Onu.olt_id == plan.olt_id,
                Onu.nap_id == plan.nap_id,
                Onu.nap_port == plan.nap_port,
            )
        )
        if occupied:
            errors.append(f"El puerto NAP {plan.nap_port} ya esta ocupado por {occupied.serial_number}.")
        nap_port = self.db.scalar(select(NapPort).where(NapPort.nap_id == plan.nap_id, NapPort.port_number == plan.nap_port))
        if not nap_port:
            errors.append(f"El puerto NAP {plan.nap_port} no existe en la NAP seleccionada.")
        elif nap_port.status not in {"free", "reserved"}:
            errors.append(f"El puerto NAP {plan.nap_port} esta en estado {nap_port.status}.")

        vlan = self.db.scalar(select(Vlan).where(Vlan.olt_id == plan.olt_id, Vlan.vlan_id == plan.vlan, Vlan.is_active.is_(True)))
        if not vlan:
            errors.append(f"La VLAN {plan.vlan} no existe o no esta activa para esta OLT.")

        if plan.speed_profile_id:
            speed_profile = self.db.get(SpeedProfile, plan.speed_profile_id)
            if not speed_profile or speed_profile.olt_id != plan.olt_id or not speed_profile.is_active:
                errors.append("El perfil de velocidad no existe, no pertenece a la OLT o no esta activo.")
            else:
                plan.speed_profile_up = speed_profile.upstream_profile_name
                plan.speed_profile_down = speed_profile.downstream_profile_name
                plan.upload_profile_id = plan.upload_profile_id or speed_profile.upload_profile_id
                plan.download_profile_id = plan.download_profile_id or speed_profile.download_profile_id

        up_catalog = self._resolve_profile_catalog(
            plan,
            olt,
            profile_id=plan.upload_profile_id,
            name=plan.speed_profile_up,
            direction="upload",
            profile_kind="tcont",
        )
        if up_catalog:
            plan.upload_profile_id = up_catalog.id
            plan.speed_profile_up = up_catalog.name
        else:
            errors.append(f"El perfil UP {plan.speed_profile_up or '-'} no existe, no esta activo o no es compatible con esta OLT.")

        down_catalog = self._resolve_profile_catalog(
            plan,
            olt,
            profile_id=plan.download_profile_id,
            name=plan.speed_profile_down,
            direction="download",
            profile_kind="traffic",
        )
        if down_catalog:
            plan.download_profile_id = down_catalog.id
            plan.speed_profile_down = down_catalog.name
        else:
            errors.append(f"El perfil DOWN {plan.speed_profile_down or '-'} no existe, no esta activo o no es compatible con esta OLT.")

        registered = self.db.scalar(select(Onu).where(Onu.olt_id == plan.olt_id, Onu.serial_number == plan.serial_number))
        if registered:
            errors.append(f"La ONU {plan.serial_number} ya esta registrada en esta OLT.")

        production_duplicate = self.db.scalar(
            select(Onu)
            .join(Olt, Onu.olt_id == Olt.id)
            .where(Onu.serial_number == plan.serial_number, Onu.olt_id != plan.olt_id, Olt.environment == "production")
        )
        if production_duplicate:
            errors.append(f"La ONU {plan.serial_number} ya existe en otra OLT de produccion.")

        lab_duplicate = self.db.scalar(
            select(Onu)
            .join(Olt, Onu.olt_id == Olt.id)
            .where(Onu.serial_number == plan.serial_number, Onu.olt_id != plan.olt_id, Olt.environment == "lab")
        )
        if lab_duplicate:
            warnings.append(f"La ONU {plan.serial_number} existe en laboratorio ({lab_duplicate.olt_code_snapshot or lab_duplicate.olt_id}).")

        if nap and plan.nap_port > nap.capacity:
            errors.append(f"El puerto NAP {plan.nap_port} supera la capacidad registrada ({nap.capacity}).")
        if not plan.pon_port_interface:
            errors.append("La ONU pendiente no tiene puerto PON detectado.")

        if selected_onu_id in occupied_onu_ids:
            errors.append(f"El ONU ID {selected_onu_id} ya esta ocupado en {plan.pon_port_interface}.")
        if suggested_onu_id is None:
            errors.append(f"No hay ONU ID disponible en {plan.pon_port_interface}.")
        elif plan.selected_onu_id and plan.selected_onu_id != suggested_onu_id and plan.selected_onu_id not in occupied_onu_ids:
            warnings.append(f"El ONU ID seleccionado ({plan.selected_onu_id}) difiere del sugerido ({suggested_onu_id}).")

        selected_type = (plan.onu_type or "").strip().upper()
        detected_type = ((unauthorized.detected_type or unauthorized.detected_vendor or "") if unauthorized else "").strip().upper()
        if not detected_type:
            warnings.append("No hay tipo ONU detectado en Discovery.")
        elif selected_type and detected_type and selected_type != detected_type:
            warnings.append(f"Tipo ONU detectado {detected_type} difiere del seleccionado {selected_type}.")

        onu_type = self._resolve_onu_type(plan, olt)
        if not onu_type:
            errors.append(f"El tipo ONU {plan.onu_type} no existe, no esta activo o no es compatible con vendor/model/firmware de la OLT.")

        if not template:
            errors.append("No existe ProvisioningTemplate activo compatible con vendor/model/firmware de la OLT.")

        cli_preview = self.generate_cli(plan, unauthorized=unauthorized, onu_id=selected_onu_id, template=template)
        return ValidationResult(
            is_valid=not errors,
            warnings=warnings,
            errors=errors,
            suggested_onu_id=suggested_onu_id,
            selected_onu_id=selected_onu_id,
            occupied_onu_ids=occupied_onu_ids,
            cli_preview=cli_preview,
            validated_at=validated_at,
        )

    def generate_cli(
        self,
        plan: ProvisioningPlan,
        unauthorized: UnauthorizedOnu | None = None,
        onu_id: int | None = None,
        template: ProvisioningTemplate | None = None,
    ) -> str:
        unauthorized = unauthorized or self.db.get(UnauthorizedOnu, plan.unauthorized_onu_id)
        zone = self.db.get(Zone, plan.zone_id)
        nap = self.db.get(Nap, plan.nap_id)
        olt = self.db.get(Olt, plan.olt_id)
        template_body = self._template_body(template) if template else self._default_template(olt)
        onu_index = onu_id or plan.selected_onu_id or plan.suggested_onu_id or self._onu_index(unauthorized)
        pon_interface = plan.pon_port_interface or (unauthorized.pon_port_interface if unauthorized else "gpon-olt_0/0/0")
        onu_interface = self._onu_interface(pon_interface, onu_index)
        context = {
            "pon_port_interface": pon_interface,
            "onu_index": onu_index,
            "onu_interface": onu_interface,
            "onu_type": plan.onu_type,
            "serial_number": plan.serial_number,
            "customer_name": plan.customer_name,
            "customer_name_cli": self._cli_name(plan.customer_name),
            "zone_name": self._cli_name(zone.name if zone else "SIN_ZONA"),
            "nap_name": self._cli_name(nap.name if nap else "SIN_NAP"),
            "nap_port": plan.nap_port,
            "vlan": plan.vlan,
            "speed_profile_up": plan.speed_profile_up,
            "speed_profile_down": plan.speed_profile_down,
        }
        return template_body.format(**context)

    def _default_template(self, olt: Olt | None) -> str:
        template = self._default_template_object(olt)
        return self._template_body(template) if template else DEFAULT_TEMPLATE_BODY

    def _default_template_object(self, olt: Olt | None) -> ProvisioningTemplate | None:
        statement = select(ProvisioningTemplate).where(ProvisioningTemplate.is_default.is_(True), ProvisioningTemplate.is_active.is_(True))
        if olt:
            statement = statement.where(
                ProvisioningTemplate.vendor == olt.vendor,
                ProvisioningTemplate.model == olt.model,
            )
            if olt.firmware:
                statement = statement.where(
                    (ProvisioningTemplate.firmware == olt.firmware) | (ProvisioningTemplate.firmware.is_(None))
                )
        return self.db.scalar(statement.order_by(ProvisioningTemplate.id.desc()).limit(1))

    @staticmethod
    def _template_body(template: ProvisioningTemplate | None) -> str:
        if not template:
            return DEFAULT_TEMPLATE_BODY
        return template.template_body or template.commands or DEFAULT_TEMPLATE_BODY

    def occupied_onu_ids(self, olt_id: int, pon_port_interface: str | None) -> list[int]:
        if not pon_port_interface:
            return []
        onu_prefix = pon_port_interface.replace("gpon-olt_", "gpon-onu_", 1)
        interfaces = self.db.scalars(
            select(Onu.onu_interface).where(
                Onu.olt_id == olt_id,
                Onu.onu_interface.like(f"{onu_prefix}:%"),
            )
        ).all()
        ids: set[int] = set()
        for onu_interface in interfaces:
            match = re.search(r":(\d+)$", onu_interface or "")
            if match:
                ids.add(int(match.group(1)))
        return sorted(ids)

    def _resolve_profile_catalog(
        self,
        plan: ProvisioningPlan,
        olt: Olt | None,
        *,
        profile_id: int | None,
        name: str | None,
        direction: str,
        profile_kind: str,
    ) -> ProfileCatalog | None:
        statement = select(ProfileCatalog).where(
            ProfileCatalog.olt_id == plan.olt_id,
            ProfileCatalog.direction == direction,
            ProfileCatalog.profile_kind == profile_kind,
            ProfileCatalog.is_active.is_(True),
        )
        if olt:
            statement = statement.where(
                ProfileCatalog.vendor == olt.vendor,
                ProfileCatalog.model == olt.model,
                ProfileCatalog.firmware == olt.firmware,
            )
        if profile_id:
            statement = statement.where(ProfileCatalog.id == profile_id)
        else:
            if not name:
                return None
            statement = statement.where(ProfileCatalog.name == name)
        return self.db.scalar(statement.limit(1))

    def _resolve_onu_type(self, plan: ProvisioningPlan, olt: Olt | None) -> OnuType | None:
        statement = select(OnuType).where(
            OnuType.olt_id == plan.olt_id,
            OnuType.name == plan.onu_type,
            OnuType.is_active.is_(True),
        )
        if olt:
            statement = statement.where(
                OnuType.vendor == olt.vendor,
                OnuType.model == olt.model,
                OnuType.firmware == olt.firmware,
            )
        return self.db.scalar(statement.limit(1))

    @staticmethod
    def next_available_onu_id(occupied_onu_ids: list[int], max_onu_id: int = 128) -> int | None:
        occupied = set(occupied_onu_ids)
        for onu_id in range(1, max_onu_id + 1):
            if onu_id not in occupied:
                return onu_id
        return None

    def _apply_validation(self, plan: ProvisioningPlan, result: ValidationResult, update_status: bool) -> None:
        plan.suggested_onu_id = result.suggested_onu_id
        plan.selected_onu_id = result.selected_onu_id
        plan.generated_cli = result.cli_preview
        plan.validation_warnings_json = json.dumps(result.warnings)
        plan.validation_errors_json = json.dumps(result.errors)
        plan.validation_result_json = json.dumps(validation_result_to_payload(result, plan.id, result_id=None), default=str)
        plan.validated_at = result.validated_at
        if update_status:
            if result.is_valid:
                plan.status = "approved" if plan.status == "approved" else "validated"
            else:
                plan.status = "validation_failed"

        validation_result = plan.validation_result
        if not validation_result:
            validation_result = ProvisioningValidationResult()
            plan.validation_result = validation_result
        validation_result.is_valid = result.is_valid
        validation_result.warnings_json = json.dumps(result.warnings)
        validation_result.errors_json = json.dumps(result.errors)
        validation_result.suggested_onu_id = result.suggested_onu_id
        validation_result.selected_onu_id = result.selected_onu_id
        validation_result.occupied_onu_ids_json = json.dumps(result.occupied_onu_ids)
        validation_result.cli_preview = result.cli_preview
        validation_result.validated_at = result.validated_at

    @staticmethod
    def _onu_index(unauthorized: UnauthorizedOnu | None) -> int:
        if not unauthorized or not unauthorized.raw_output:
            return 1
        match = re.search(r"gpon-onu_\d+/\d+/\d+:(\d+)", unauthorized.raw_output, re.IGNORECASE)
        return int(match.group(1)) if match else 1

    @staticmethod
    def _onu_interface(pon_interface: str, onu_index: int) -> str:
        if pon_interface.startswith("gpon-olt_"):
            return pon_interface.replace("gpon-olt_", "gpon-onu_", 1) + f":{onu_index}"
        return f"{pon_interface}:{onu_index}"

    @staticmethod
    def _cli_name(value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
        return normalized.strip("_") or "SIN_NOMBRE"


def plan_to_dict(plan: ProvisioningPlan) -> dict:
    return {
        "id": plan.id,
        "olt_id": plan.olt_id,
        "olt_code": plan.olt_code,
        "unauthorized_onu_id": plan.unauthorized_onu_id,
        "serial_number": plan.serial_number,
        "pon_port_interface": plan.pon_port_interface,
        "customer_name": plan.customer_name,
        "customer_reference": plan.customer_reference,
        "technical_comment": plan.technical_comment,
        "address": plan.address,
        "notes": plan.notes,
        "zone_id": plan.zone_id,
        "nap_id": plan.nap_id,
        "nap_port": plan.nap_port,
        "onu_type": plan.onu_type,
        "vlan": plan.vlan,
        "speed_profile_up": plan.speed_profile_up,
        "speed_profile_down": plan.speed_profile_down,
        "speed_profile_id": plan.speed_profile_id,
        "upload_profile_id": plan.upload_profile_id,
        "download_profile_id": plan.download_profile_id,
        "selected_onu_id": plan.selected_onu_id,
        "suggested_onu_id": plan.suggested_onu_id,
        "generated_cli": plan.generated_cli,
        "validation_warnings": _loads(plan.validation_warnings_json),
        "validation_errors": _loads(plan.validation_errors_json),
        "validation_result": validation_result_to_dict(plan.validation_result) if plan.validation_result else None,
        "validated_at": plan.validated_at,
        "status": plan.status,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


def _loads(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def validation_result_to_dict(result: ProvisioningValidationResult) -> dict:
    return {
        "id": result.id,
        "provisioning_plan_id": result.provisioning_plan_id,
        "is_valid": result.is_valid,
        "warnings": _loads(result.warnings_json),
        "errors": _loads(result.errors_json),
        "suggested_onu_id": result.suggested_onu_id,
        "selected_onu_id": result.selected_onu_id,
        "occupied_onu_ids": _loads_ints(result.occupied_onu_ids_json),
        "cli_preview": result.cli_preview,
        "validated_at": result.validated_at,
    }


def validation_result_to_payload(result: ValidationResult, plan_id: int, result_id: int | None) -> dict:
    return {
        "id": result_id,
        "provisioning_plan_id": plan_id,
        "is_valid": result.is_valid,
        "warnings": result.warnings,
        "errors": result.errors,
        "suggested_onu_id": result.suggested_onu_id,
        "selected_onu_id": result.selected_onu_id,
        "occupied_onu_ids": result.occupied_onu_ids,
        "cli_preview": result.cli_preview,
        "validated_at": result.validated_at,
    }


def _loads_ints(value: str | None) -> list[int]:
    loaded = _loads(value)
    return [int(item) for item in loaded if isinstance(item, int | float | str) and str(item).isdigit()]
