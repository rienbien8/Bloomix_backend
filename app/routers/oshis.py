# app/routers/oshis.py
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Oshi  # type: ignore

router = APIRouter(prefix="/api/v1/oshis", tags=["oshis"])

@router.get("")
def list_oshis(
    q: Optional[str] = Query(None, description="部分一致（name/description）"),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    stmt = select(Oshi)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                getattr(Oshi, "name").like(like),
                getattr(Oshi, "description").like(like),
            )
        )
    if category:
        stmt = stmt.where(getattr(Oshi, "category") == category)

    rows = db.execute(stmt.limit(limit)).scalars().all()
    items = [{
        "id": o.id,
        "name": o.name,
        "category": o.category,
        "image_url": getattr(o, "image_url", None),
        "description": getattr(o, "description", None),
        "created_at": getattr(o, "created_at", None),
        "updated_at": getattr(o, "updated_at", None),
    } for o in rows]
    return {"count": len(items), "items": items}
