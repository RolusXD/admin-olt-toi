from datetime import UTC, datetime
import secrets

from sqlalchemy.orm import Session

from app.models.entities import OperationId


class OperationIdService:
    """Generador reutilizable de Operation IDs.

    Formato actualizado (Sprint 0.5): ``OP-YYYYMMDD-HHMMSS-XXXX`` donde:

    - ``YYYYMMDD`` es la fecha en UTC.
    - ``HHMMSS`` es la hora en UTC.
    - ``XXXX`` es un sufijo hexadecimal en mayúsculas.

    La tabla ``operation_ids`` garantiza unicidad mediante una
    restricción UNIQUE sobre ``code``.
    """

    def __init__(self, db: Session):
        self.db = db

    def generate(self) -> OperationId:
        """Genera y persiste un nuevo Operation ID.

        La función sólo hace ``flush`` sobre la sesión; el ``commit`` queda
        a cargo del llamador para poder integrarse en transacciones más
        amplias.
        """

        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        time_part = now.strftime("%H%M%S")

        # 4 caracteres hexadecimales proporcionan 65536 combinaciones por
        # segundo y son suficientes dado que la unicidad final la garantiza
        # la base de datos mediante una UNIQUE constraint.
        suffix = secrets.token_hex(2).upper()  # 4 caracteres hex
        code = f"OP-{date_part}-{time_part}-{suffix}"

        operation = OperationId(code=code)
        self.db.add(operation)
        # En caso de colisión (extremadamente improbable), la base de datos
        # lanzará una IntegrityError al hacer flush/commit y el llamador
        # será responsable de gestionar el rollback correspondiente.
        self.db.flush()
        return operation


__all__ = ["OperationIdService"]
