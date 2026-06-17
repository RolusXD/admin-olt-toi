from sqlalchemy.orm import Session

from app.models.entities import EventLog


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def record(self, event_type: str, entity_type: str, entity_id: int | None, description: str) -> EventLog:
        event = EventLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
