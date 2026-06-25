from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Role, User, UserRole


@dataclass(slots=True)
class OperatorContext:
    """Identidad operativa mínima del usuario autenticado.

    Esta capa no implementa autorización por permisos; sólo resuelve
    información de identidad para enriquecer logs y operaciones.
    """

    user_id: int | None
    user_name: str
    role_code: str
    origin: str


class OperatorContextService:
    """Resuelve la identidad operativa a partir del subject del token.

    En el Sprint 0.5 el login HTTP sigue siendo un único administrador
    respaldado por variables de entorno (`ADMIN_USERNAME`/`ADMIN_PASSWORD_HASH`).
    Para ese caso se aplica la siguiente estrategia conservadora:

    - Si existe un User con `username == subject`, se reutiliza.
    - Si no existe, se crea un User activo con ese username y un rol
      `ADMIN` asociado cuando exista en catálogo de roles.

    No se realiza aún autorización por permisos; el rol `ADMIN` se usa
    únicamente como metadato en los eventos operativos.
    """

    def __init__(self, db: Session, origin: str = "api") -> None:
        self.db = db
        self.origin = origin

    def resolve(self, subject: str) -> OperatorContext:
        normalized = (subject or "").strip()
        if not normalized:
            # Fallback defensivo: identidad anónima lógica
            return OperatorContext(user_id=None, user_name="anonymous", role_code="SYSTEM", origin=self.origin)

        user = self.db.execute(select(User).where(User.username == normalized)).scalar_one_or_none()
        if user is None:
            user = User(username=normalized, full_name=normalized, is_active=True, status="active")
            self.db.add(user)
            self.db.flush()

        role_code = "ADMIN"
        # Asignar rol ADMIN conservadoramente si existe en catálogo y aún no está ligado al usuario.
        role = self.db.execute(select(Role).where(Role.code == role_code)).scalar_one_or_none()
        if role is not None:
            link = self.db.execute(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
            ).scalar_one_or_none()
            if link is None:
                self.db.add(UserRole(user_id=user.id, role_id=role.id))
                self.db.flush()

        return OperatorContext(user_id=user.id, user_name=user.username, role_code=role_code, origin=self.origin)


__all__ = ["OperatorContext", "OperatorContextService"]
