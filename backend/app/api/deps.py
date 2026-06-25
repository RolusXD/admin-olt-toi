from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.entities import Olt
from app.services.operator_context_service import OperatorContext, OperatorContextService


DbSession = Annotated[Session, Depends(get_db)]


def get_olt_or_404(db: DbSession, olt_id: int) -> Olt:
    olt = db.get(Olt, olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OLT not found")
    return olt


def get_current_operator(
    db: DbSession,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> OperatorContext:
    """Resolver identidad operativa a partir de un JWT opcional.

    Reglas (Sprint 0.75):

    - Si no se envía cabecera ``Authorization`` → operador lógico
      ``anonymous`` con rol ``SYSTEM`` y origen ``api``.
    - Si se envía ``Authorization: Bearer <token>`` → se decodifica el
      token con :func:`decode_access_token` y se resuelve un
      :class:`OperatorContext` real mediante
      :class:`OperatorContextService`.
    - Si el formato de la cabecera es inválido o el token no es válido
      → HTTP 401.

    Esta función **no cambia** el flujo de login existente; sólo
    proporciona un helper reutilizable para que los endpoints puedan
    obtener un operador sin duplicar código de parsing de JWT.
    """

    # Sin cabecera → operador anónimo lógico, útil para entornos de test
    # o herramientas internas que aún no envían JWT.
    if not authorization:
        return OperatorContext(
            user_id=None,
            user_name="anonymous",
            role_code="SYSTEM",
            origin="api",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")

    try:
        subject = decode_access_token(token.strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    service = OperatorContextService(db, origin="api")
    return service.resolve(subject)


__all__ = ["DbSession", "get_olt_or_404", "get_current_operator"]
