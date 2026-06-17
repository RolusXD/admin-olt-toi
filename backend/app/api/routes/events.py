from fastapi import APIRouter

from app.api.deps import DbSession
from app.repositories.entities import EventRepository
from app.schemas.entities import EventRead

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventRead])
def list_events(db: DbSession):
    return EventRepository(db).list()
