from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Olt

DbSession = Annotated[Session, Depends(get_db)]


def get_olt_or_404(db: DbSession, olt_id: int) -> Olt:
    olt = db.get(Olt, olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OLT not found")
    return olt
