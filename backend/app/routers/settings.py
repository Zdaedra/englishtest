from fastapi import APIRouter, Depends
from sqlmodel import Session

from .. import models
from ..db import get_session

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_row(session: Session = Depends(get_session)):
    row = session.get(models.Setting, 1)
    if not row:
        row = models.Setting(id=1)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row.model_dump()


@router.put("")
def update_settings(patch: dict, session: Session = Depends(get_session)):
    row = session.get(models.Setting, 1) or models.Setting(id=1)
    allowed = set(models.Setting.model_fields.keys()) - {"id"}
    for k, v in patch.items():
        if k in allowed:
            setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.model_dump()
