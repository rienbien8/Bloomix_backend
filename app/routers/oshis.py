# app/routers/oshis.py
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Oshi, SpotsOshi  # type: ignore

router = APIRouter(prefix="/api/v1/oshis", tags=["oshis"])

@router.get("")
def list_oshis(
    q: Optional[str] = Query(None, description="部分一致（name/description）"),
    category: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),  # デフォルト200件、最大1000件まで
    db: Session = Depends(get_session),
):
    # スポット数を集計するサブクエリ
    spots_count_subquery = (
        select(
            SpotsOshi.oshi_id,
            func.count(SpotsOshi.spot_id).label("spots_count")
        )
        .group_by(SpotsOshi.oshi_id)
        .subquery()
    )
    
    # メインクエリ：Oshiテーブルとスポット数をJOIN
    stmt = (
        select(
            Oshi.id,
            Oshi.name,
            Oshi.category,
            Oshi.image_url,
            Oshi.description,
            Oshi.created_at,
            Oshi.updated_at,
            func.coalesce(spots_count_subquery.c.spots_count, 0).label("spots_count")
        )
        .outerjoin(spots_count_subquery, Oshi.id == spots_count_subquery.c.oshi_id)
    )
    
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

    rows = db.execute(stmt.limit(limit)).all()
    items = [{
        "id": str(o.id),
        "name": o.name,
        "spotsCount": o.spots_count,
        "iconUrl": o.image_url,
        "category": o.category,
        "description": o.description,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    } for o in rows]
    return {"count": len(items), "items": items}
