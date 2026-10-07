from datetime import date
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.dependencies import get_fault_store
from backend.app.domain.agent import FaultRecord
from backend.app.infrastructure.fault_store import SQLiteFaultStore

router = APIRouter(tags=["fault history"])


class FaultCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    equipment_id: str = Field(min_length=1, max_length=100)
    occurred_at: date
    symptom: str = Field(min_length=1, max_length=2000)
    cause: str = Field(min_length=1, max_length=2000)
    corrective_action: str = Field(min_length=1, max_length=2000)
    resolved: bool


@router.post("/faults", response_model=FaultRecord, status_code=201)
def create_fault(
    payload: FaultCreate,
    store: Annotated[SQLiteFaultStore, Depends(get_fault_store)],
) -> FaultRecord:
    record = FaultRecord(fault_id=uuid4().hex, **payload.model_dump())
    store.add(record)
    return record


@router.get("/faults", response_model=list[FaultRecord])
def list_faults(
    equipment_id: Annotated[str, Query(min_length=1, max_length=100, pattern=r".*\S.*")],
    store: Annotated[SQLiteFaultStore, Depends(get_fault_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[FaultRecord]:
    return store.lookup(equipment_id, limit=limit)
