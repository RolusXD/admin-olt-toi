from sqlalchemy.orm import Session

from app.models.entities import EventLog


class EventService:
    """Servicio de bitácora operativa y eventos técnicos.

    Esta clase encapsula la escritura en ``EventLog`` y sirve como base
    del Audit Trail transversal al sistema. No implementa todavía ningún
    workflow de aprobación ni lógica de permisos; sólo registra eventos.
    """

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        event_type: str,
        entity_type: str,
        entity_id: int | None,
        description: str,
        *,
        operation_id: str | None = None,
        user_id: int | None = None,
        user_name: str | None = None,
        role_code: str | None = None,
        origin: str | None = None,
        result: str | None = None,
        action: str | None = None,
        duration_ms: int | None = None,
        reason: str | None = None,
        error: str | None = None,
    ) -> EventLog:
        """Registra un evento en la bitácora operativa.

        Los cuatro primeros parámetros (`event_type`, `entity_type`,
        `entity_id`, `description`) mantienen compatibilidad hacia atrás
        con usos existentes. Los parámetros adicionales son opcionales y
        preparan el modelo para un Audit Trail más rico:

        - ``operation_id``: identificador OP-YYYY-XXXXXXXX.
        - ``user_id`` / ``user_name`` / ``role_code``: identidad del
          operador humano o sistema.
        - ``origin``: origen lógico (api, scheduler, cli, import, provisioning...).
        - ``result``: resumen del resultado (success, failed, partial...).
        - ``action``: acción de negocio (ej. "OLT.ADOPT", "ONU.UPDATE").
        - ``duration_ms``: duración estimada.
        - ``reason``: motivo declarado.
        - ``error``: detalle de error, si aplica.
        """

        event = EventLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            operation_id=operation_id,
            user_id=user_id,
            user_name=user_name,
            role_code=role_code,
            origin=origin,
            result=result,
            action=action,
            duration_ms=duration_ms,
            reason=reason,
            error=error,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event


__all__ = ["EventService"]
