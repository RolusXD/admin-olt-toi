from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.services.event_service import EventService
from app.services.operation_id_service import OperationIdService
from app.services.operator_context_service import OperatorContext


@dataclass(slots=True)
class OperationContext:
    """Contexto de una operación lógica en curso.

    Se utiliza para encadenar los eventos de inicio/éxito/error bajo un
    mismo ``operation_id`` reutilizable en `EventLog`.
    """

    operation_id: str
    started_at: datetime
    operator: OperatorContext | None = None


class OperationLogService:
    """Helper de alto nivel para auditar operaciones con OperationId.

    Objetivos (Sprint 0.5):

    - Generar un ``operation_id`` estructurado reutilizable a través de
      :class:`OperationIdService`.
    - Registrar eventos de inicio/éxito/error en :class:`EventService`
      enriquecidos con contexto de operador cuando esté disponible.
    - Mantener compatibilidad total con código existente que llama
      directamente a ``EventService.record``.

    Este helper es deliberadamente delgado: no implementa lógica de
    autorización ni de Workflow/Apply; sólo registra auditoría.
    """

    def __init__(self, db: Session, origin: str = "api") -> None:
        self.db = db
        self._origin = origin
        self._events = EventService(db)
        self._operation_ids = OperationIdService(db)

    def _origin_for(self, operator: OperatorContext | None) -> str:
        return operator.origin if operator is not None else self._origin

    def start(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: int | None,
        description: str,
        operator: OperatorContext | None = None,
        action: str | None = None,
        reason: str | None = None,
    ) -> OperationContext:
        """Registra el inicio de una operación y devuelve su contexto.

        No lanza ``commit`` adicional sobre la sesión más allá del que
        ya realiza internamente :class:`EventService`.
        """

        op = self._operation_ids.generate()
        started_at = datetime.now(UTC)

        self._events.record(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            operation_id=op.code,
            user_id=operator.user_id if operator is not None else None,
            user_name=operator.user_name if operator is not None else None,
            role_code=operator.role_code if operator is not None else None,
            origin=self._origin_for(operator),
            result="started",
            action=action,
            duration_ms=None,
            reason=reason,
            error=None,
        )

        return OperationContext(operation_id=op.code, started_at=started_at, operator=operator)

    def success(
        self,
        ctx: OperationContext,
        *,
        event_type: str,
        entity_type: str,
        entity_id: int | None,
        description: str,
        action: str | None = None,
        reason: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Registra el éxito de una operación previamente iniciada."""

        if duration_ms is None:
            duration_ms = int((datetime.now(UTC) - ctx.started_at).total_seconds() * 1000)

        operator = ctx.operator
        self._events.record(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            operation_id=ctx.operation_id,
            user_id=operator.user_id if operator is not None else None,
            user_name=operator.user_name if operator is not None else None,
            role_code=operator.role_code if operator is not None else None,
            origin=self._origin_for(operator),
            result="success",
            action=action,
            duration_ms=duration_ms,
            reason=reason,
            error=None,
        )

    def error(
        self,
        ctx: OperationContext,
        *,
        event_type: str,
        entity_type: str,
        entity_id: int | None,
        description: str,
        action: str | None = None,
        reason: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Registra el fallo de una operación previamente iniciada."""

        if duration_ms is None:
            duration_ms = int((datetime.now(UTC) - ctx.started_at).total_seconds() * 1000)

        operator = ctx.operator
        self._events.record(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            operation_id=ctx.operation_id,
            user_id=operator.user_id if operator is not None else None,
            user_name=operator.user_name if operator is not None else None,
            role_code=operator.role_code if operator is not None else None,
            origin=self._origin_for(operator),
            result="failed",
            action=action,
            duration_ms=duration_ms,
            reason=reason,
            error=error,
        )


__all__ = ["OperationContext", "OperationLogService"]
