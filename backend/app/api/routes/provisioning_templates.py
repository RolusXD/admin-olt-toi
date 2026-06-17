from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import ProvisioningTemplate
from app.schemas.entities import ProvisioningTemplateCreate, ProvisioningTemplateRead, ProvisioningTemplateUpdate

router = APIRouter(prefix="/provisioning-templates", tags=["provisioning-templates"])


@router.get("", response_model=list[ProvisioningTemplateRead])
def list_provisioning_templates(
    db: DbSession,
    vendor: str | None = None,
    model: str | None = None,
    firmware: str | None = None,
    is_active: bool | None = Query(default=None),
) -> list[ProvisioningTemplate]:
    statement = select(ProvisioningTemplate)
    if vendor:
        statement = statement.where(ProvisioningTemplate.vendor == vendor)
    if model:
        statement = statement.where(ProvisioningTemplate.model == model)
    if firmware:
        statement = statement.where(ProvisioningTemplate.firmware == firmware)
    if is_active is not None:
        statement = statement.where(ProvisioningTemplate.is_active.is_(is_active))
    return list(db.scalars(statement.order_by(ProvisioningTemplate.vendor, ProvisioningTemplate.model, ProvisioningTemplate.template_name)))


@router.post("", response_model=ProvisioningTemplateRead, status_code=status.HTTP_201_CREATED)
def create_provisioning_template(payload: ProvisioningTemplateCreate, db: DbSession) -> ProvisioningTemplate:
    template = ProvisioningTemplate(
        name=payload.template_name,
        commands=payload.template_body,
        **payload.model_dump(),
    )
    if template.is_default:
        _clear_defaults(db, template)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=ProvisioningTemplateRead)
def get_provisioning_template(template_id: int, db: DbSession) -> ProvisioningTemplate:
    template = db.get(ProvisioningTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Provisioning template not found")
    return template


@router.put("/{template_id}", response_model=ProvisioningTemplateRead)
def update_provisioning_template(template_id: int, payload: ProvisioningTemplateUpdate, db: DbSession) -> ProvisioningTemplate:
    template = db.get(ProvisioningTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Provisioning template not found")
    data = payload.model_dump(exclude_unset=True)
    if "template_name" in data:
        template.name = data["template_name"]
    if "template_body" in data:
        template.commands = data["template_body"]
    for key, value in data.items():
        setattr(template, key, value)
    if template.is_default:
        _clear_defaults(db, template)
    db.commit()
    db.refresh(template)
    return template


@router.put("/{template_id}/activate", response_model=ProvisioningTemplateRead)
def activate_template(template_id: int, db: DbSession) -> ProvisioningTemplate:
    return _set_active(template_id, True, db)


@router.put("/{template_id}/deactivate", response_model=ProvisioningTemplateRead)
def deactivate_template(template_id: int, db: DbSession) -> ProvisioningTemplate:
    return _set_active(template_id, False, db)


@router.put("/{template_id}/set-default", response_model=ProvisioningTemplateRead)
def set_default_template(template_id: int, db: DbSession) -> ProvisioningTemplate:
    template = db.get(ProvisioningTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Provisioning template not found")
    _clear_defaults(db, template)
    template.is_default = True
    template.is_active = True
    db.commit()
    db.refresh(template)
    return template


def _set_active(template_id: int, active: bool, db: DbSession) -> ProvisioningTemplate:
    template = db.get(ProvisioningTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Provisioning template not found")
    template.is_active = active
    if not active:
        template.is_default = False
    db.commit()
    db.refresh(template)
    return template


def _clear_defaults(db: DbSession, template: ProvisioningTemplate) -> None:
    db.execute(
        select(ProvisioningTemplate).where(
            ProvisioningTemplate.vendor == template.vendor,
            ProvisioningTemplate.model == template.model,
            ProvisioningTemplate.firmware == template.firmware,
        )
    )
    for existing in db.scalars(
        select(ProvisioningTemplate).where(
            ProvisioningTemplate.vendor == template.vendor,
            ProvisioningTemplate.model == template.model,
            ProvisioningTemplate.firmware == template.firmware,
            ProvisioningTemplate.id != (template.id or 0),
        )
    ):
        existing.is_default = False
