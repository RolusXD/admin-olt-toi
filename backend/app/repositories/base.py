from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[ModelT]:
        return list(self.db.scalars(select(self.model)))

    def get(self, entity_id: int) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def create(self, data: dict) -> ModelT:
        entity = self.model(**data)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: ModelT, data: dict) -> ModelT:
        for key, value in data.items():
            setattr(entity, key, value)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)
        self.db.commit()
