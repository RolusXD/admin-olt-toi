from __future__ import annotations

import json
import re
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    GponProfile,
    Nap,
    Olt,
    Onu,
    ProvisioningPlan,
    ProvisioningTemplate,
    UnauthorizedOnu,
    Vlan,
    Zone,
)
from app.schemas.entities import ProvisioningPlanCreate


VALID_PLAN_STATUSES = {"draft", "validated", "approved", "executed", "cancelled"}
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
    warnings: list[str]
    errors: list[str]


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
            speed_profile_up=payload.speed_profile_up,
            speed_profile_down=payload.speed_profile_down,
            status="draft",
        )
        plan.generated_cli = self.generate_cli(plan, unauthorized=unauthorized)
        result = self.validate(plan)
        plan.validation_warnings_json = json.dumps(result.warnings)
        plan.validation_errors_json = json.dumps(result.errors)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def validate_and_update(self, plan_id: int) -> tuple[ProvisioningPlan, ValidationResult]:
        plan = self.require_plan(plan_id)
        if plan.status in {"approved", "executed", "cancelled"}:
            raise HTTPException(status_code=409, detail=f"No se puede validar un plan en estado {plan.status}")
        unauthorized = self.db.get(UnauthorizedOnu, plan.unauthorized_onu_id)
        plan.generated_cli = self.generate_cli(plan, unauthorized=unauthorized)
        result = self.validate(plan)
        plan.validation_warnings_json = json.dumps(result.warnings)
        plan.validation_errors_json = json.dumps(result.errors)
        if result.errors:
            plan.status = "draft"
        else:
            plan.status = "validated"
        self.db.commit()
        self.db.refresh(plan)
        return plan, result

    def approve(self, plan_id: int) -> ProvisioningPlan:
        plan = self.require_plan(plan_id)
        if plan.status in {"executed", "cancelled"}:
            raise HTTPException(status_code=409, detail=f"No se puede aprobar un plan en estado {plan.status}")
        result = self.validate(plan)
        plan.validation_warnings_json = json.dumps(result.warnings)
        plan.validation_errors_json = json.dumps(result.errors)
        if result.errors:
            self.db.commit()
            raise HTTPException(status_code=409, detail={"message": "El plan tiene errores de validacion", "errors": result.errors})
        plan.generated_cli = self.generate_cli(plan)
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
        counts = {"draft": 0, "validated": 0, "approved": 0, "cancelled": 0}
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

        olt = self.db.get(Olt, plan.olt_id)
        unauthorized = self.db.get(UnauthorizedOnu, plan.unauthorized_onu_id)
        zone = self.db.get(Zone, plan.zone_id)
        nap = self.db.get(Nap, plan.nap_id)

        if not olt:
            errors.append("La OLT no existe.")
        if not unauthorized:
            errors.append("La ONU pendiente no existe.")
        elif unauthorized.status != "pending":
            errors.append(f"La ONU pendiente esta en estado {unauthorized.status}.")
        elif unauthorized.olt_id != plan.olt_id:
            errors.append("La ONU pendiente no pertenece a la OLT del plan.")
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

        vlan = self.db.scalar(select(Vlan).where(Vlan.olt_id == plan.olt_id, Vlan.vlan_id == plan.vlan))
        if not vlan:
            errors.append(f"La VLAN {plan.vlan} no existe para esta OLT.")

        up_profile = self.db.scalar(
            select(GponProfile).where(
                GponProfile.olt_id == plan.olt_id,
                GponProfile.profile_type == "tcont",
                GponProfile.name == plan.speed_profile_up,
            )
        )
        if not up_profile:
            errors.append(f"El perfil UP {plan.speed_profile_up} no existe para esta OLT.")

        down_profile = self.db.scalar(
            select(GponProfile).where(
                GponProfile.olt_id == plan.olt_id,
                GponProfile.profile_type == "traffic",
                GponProfile.name == plan.speed_profile_down,
            )
        )
        if not down_profile:
            errors.append(f"El perfil DOWN {plan.speed_profile_down} no existe para esta OLT.")

        registered = self.db.scalar(select(Onu).where(Onu.olt_id == plan.olt_id, Onu.serial_number == plan.serial_number))
        if registered:
            errors.append(f"La ONU {plan.serial_number} ya esta registrada en esta OLT.")

        registered_elsewhere = self.db.scalar(select(Onu).where(Onu.olt_id != plan.olt_id, Onu.serial_number == plan.serial_number))
        if registered_elsewhere:
            warnings.append(f"La ONU {plan.serial_number} existe en otra OLT ({registered_elsewhere.olt_code_snapshot or registered_elsewhere.olt_id}).")

        if nap and plan.nap_port > nap.capacity:
            warnings.append(f"El puerto NAP {plan.nap_port} supera la capacidad registrada ({nap.capacity}).")
        if not plan.pon_port_interface:
            warnings.append("La ONU pendiente no tiene puerto PON detectado.")

        return ValidationResult(warnings=warnings, errors=errors)

    def generate_cli(self, plan: ProvisioningPlan, unauthorized: UnauthorizedOnu | None = None) -> str:
        unauthorized = unauthorized or self.db.get(UnauthorizedOnu, plan.unauthorized_onu_id)
        zone = self.db.get(Zone, plan.zone_id)
        nap = self.db.get(Nap, plan.nap_id)
        olt = self.db.get(Olt, plan.olt_id)
        template = self._default_template(olt)
        onu_index = self._onu_index(unauthorized)
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
        return template.format(**context)

    def _default_template(self, olt: Olt | None) -> str:
        statement = select(ProvisioningTemplate).where(ProvisioningTemplate.is_default.is_(True))
        if olt:
            statement = statement.where(
                ProvisioningTemplate.vendor == olt.vendor,
                ProvisioningTemplate.model == olt.model,
            )
        template = self.db.scalar(statement.order_by(ProvisioningTemplate.id.desc()).limit(1))
        return (template.template_body or template.commands) if template else DEFAULT_TEMPLATE_BODY

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
        "generated_cli": plan.generated_cli,
        "validation_warnings": _loads(plan.validation_warnings_json),
        "validation_errors": _loads(plan.validation_errors_json),
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
