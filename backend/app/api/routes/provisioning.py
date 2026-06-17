from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.entities import (
    ProvisioningPlanCounts,
    ProvisioningPlanCreate,
    ProvisioningPlanRead,
    ProvisioningPlanValidationResponse,
    ProvisioningValidationResultRead,
)
from app.services.provisioning_service import ProvisioningService, plan_to_dict, validation_result_to_dict

router = APIRouter(tags=["provisioning"])


@router.post("/provisioning-plans", response_model=ProvisioningPlanRead)
def create_provisioning_plan(payload: ProvisioningPlanCreate, db: DbSession) -> dict:
    plan = ProvisioningService(db).create_plan(payload)
    return plan_to_dict(plan)


@router.get("/provisioning-plans", response_model=list[ProvisioningPlanRead])
def list_provisioning_plans(
    db: DbSession,
    olt_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    serial_number: str | None = Query(default=None),
) -> list[dict]:
    plans = ProvisioningService(db).list_plans(olt_id=olt_id, status=status, serial_number=serial_number)
    return [plan_to_dict(plan) for plan in plans]


@router.get("/provisioning-plans/counts", response_model=ProvisioningPlanCounts)
def provisioning_plan_counts(db: DbSession) -> dict[str, int]:
    return ProvisioningService(db).counts()


@router.get("/provisioning-plans/{plan_id}", response_model=ProvisioningPlanRead)
def get_provisioning_plan(plan_id: int, db: DbSession) -> dict:
    plan = ProvisioningService(db).require_plan(plan_id)
    return plan_to_dict(plan)


@router.get("/provisioning-plans/{plan_id}/validation-result", response_model=ProvisioningValidationResultRead)
def get_provisioning_validation_result(plan_id: int, db: DbSession) -> dict:
    plan = ProvisioningService(db).require_plan(plan_id)
    if not plan.validation_result:
        _, result = ProvisioningService(db).validate_and_update(plan_id)
        plan = ProvisioningService(db).require_plan(plan_id)
    return validation_result_to_dict(plan.validation_result)


@router.put("/provisioning-plans/{plan_id}/revalidate", response_model=ProvisioningPlanValidationResponse)
def revalidate_provisioning_plan(plan_id: int, db: DbSession) -> dict:
    plan, result = ProvisioningService(db).validate_and_update(plan_id)
    return {
        "plan": plan_to_dict(plan),
        "warnings": result.warnings,
        "errors": result.errors,
        "is_valid": result.is_valid,
        "suggested_onu_id": result.suggested_onu_id,
        "cli_preview": result.cli_preview,
    }


@router.put("/provisioning-plans/{plan_id}/validate", response_model=ProvisioningPlanValidationResponse)
def validate_provisioning_plan(plan_id: int, db: DbSession) -> dict:
    return revalidate_provisioning_plan(plan_id, db)


@router.put("/provisioning-plans/{plan_id}/approve", response_model=ProvisioningPlanRead)
def approve_provisioning_plan(plan_id: int, db: DbSession) -> dict:
    plan = ProvisioningService(db).approve(plan_id)
    return plan_to_dict(plan)


@router.put("/provisioning-plans/{plan_id}/cancel", response_model=ProvisioningPlanRead)
def cancel_provisioning_plan(plan_id: int, db: DbSession) -> dict:
    plan = ProvisioningService(db).cancel(plan_id)
    return plan_to_dict(plan)


@router.get("/provisioning/unauthorized")
def unauthorized_onus() -> list[dict[str, str]]:
    return []
