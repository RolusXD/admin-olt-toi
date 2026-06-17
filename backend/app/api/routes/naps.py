from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.models.entities import Nap
from app.repositories.entities import NapRepository
from app.schemas.entities import NapRead, NapSchema

router = APIRouter(prefix="/naps", tags=["naps"])


@router.get("", response_model=list[NapRead])
def list_naps(db: DbSession) -> list[Nap]:
    return NapRepository(db).list()


@router.post("", response_model=NapRead, status_code=status.HTTP_201_CREATED)
def create_nap(payload: NapSchema, db: DbSession) -> Nap:
    return NapRepository(db).create(payload.model_dump())


@router.patch("/{nap_id}", response_model=NapRead)
def update_nap(nap_id: int, payload: NapSchema, db: DbSession) -> Nap:
    nap = db.get(Nap, nap_id)
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
    return NapRepository(db).update(nap, payload.model_dump())


@router.delete("/{nap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_nap(nap_id: int, db: DbSession) -> None:
    nap = db.get(Nap, nap_id)
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
    NapRepository(db).delete(nap)
