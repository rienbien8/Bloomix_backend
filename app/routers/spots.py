# app/routers/spots.py
from typing import Optional, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_, text
from sqlalchemy.orm import Session

from app.db import get_session  # 既存のdb.pyのセッションジェネレータ
# ↓ ここは app/models.py の実クラス名に合わせて変更してください
from app.models import Spot, Content, SpotContent  # type: ignore

from app.utils.geo import haversine_km, bbox_center

router = APIRouter(prefix="/api/v1/spots", tags=["spots"])

def _parse_bbox(bbox: str) -> Tuple[float, float, float, float]:
    try:
        parts = [float(p.strip()) for p in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError
        min_lat, min_lng, max_lat, max_lng = parts
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90 and -180 <= min_lng <= 180 and -180 <= max_lng <= 180):
            raise ValueError
        if min_lat > max_lat or min_lng > max_lng:
            raise ValueError
        return min_lat, min_lng, max_lat, max_lng
    except Exception:
        raise HTTPException(status_code=422, detail="bbox must be 'minLat,minLng,maxLat,maxLng' (float)")

def _parse_origin(origin: Optional[str], bbox_tuple: Tuple[float, float, float, float]) -> Tuple[float, float]:
    if origin:
        try:
            lat, lng = [float(p.strip()) for p in origin.split(",")]
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError
            return lat, lng
        except Exception:
            raise HTTPException(status_code=422, detail="origin must be 'lat,lng' (float)")
    return bbox_center(*bbox_tuple)

@router.get("")
def list_spots(
    bbox: str = Query(..., description="minLat,minLng,maxLat,maxLng"),
    is_special: Optional[int] = Query(None, description="0 or 1"),
    q: Optional[str] = Query(None, description="partial match on name/description"),
    origin: Optional[str] = Query(None, description="lat,lng (distance sort origin)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """BBox内のスポットを距離昇順で返す（origin未指定はBBox中心）。"""
    min_lat, min_lng, max_lat, max_lng = _parse_bbox(bbox)
    org_lat, org_lng = _parse_origin(origin, (min_lat, min_lng, max_lat, max_lng))

    # 絞り込み（まずはBBox）
    stmt = select(Spot).where(
        and_(Spot.lat >= min_lat, Spot.lat <= max_lat, Spot.lng >= min_lng, Spot.lng <= max_lng)
    )
    if is_special is not None:
        stmt = stmt.where(Spot.is_special == bool(is_special))
    if q:
        like = f"%{q}%"
        # name/description の部分一致（SQLModel/SAどちらでもOKな書き方）
        stmt = stmt.where(or_(Spot.name.like(like), Spot.description.like(like)))

    # 取り過ぎ→距離計算→昇順→limit
    candidates = db.execute(stmt).scalars().all()
    items = []
    for s in candidates:
        # Decimal列でもfloat()でOK
        d = haversine_km(float(s.lat), float(s.lng), org_lat, org_lng)
        items.append({
            "id": s.id,
            "name": s.name,
            "lat": float(s.lat),
            "lng": float(s.lng),
            "type": getattr(s, "type", None),
            "is_special": bool(s.is_special),
            "dwell_min": getattr(s, "dwell_min", None),
            "address": getattr(s, "address", None),
            "place_id": getattr(s, "place_id", None),
            "distance_km": round(d, 3),
        })
    items.sort(key=lambda x: x["distance_km"])
    return {"count": min(len(items), limit), "items": items[:limit]}

@router.get("/{spot_id}")
def get_spot(spot_id: int, db: Session = Depends(get_session)):
    s = db.execute(select(Spot).where(Spot.id == spot_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="spot not found")
    return {
        "id": s.id,
        "name": s.name,
        "lat": float(s.lat),
        "lng": float(s.lng),
        "type": getattr(s, "type", None),
        "is_special": bool(s.is_special),
        "dwell_min": getattr(s, "dwell_min", None),
        "address": getattr(s, "address", None),
        "place_id": getattr(s, "place_id", None),
        "description": getattr(s, "description", None),
        "created_at": getattr(s, "created_at", None),
        "updated_at": getattr(s, "updated_at", None),
    }

@router.get("/{spot_id}/contents")
def get_spot_contents(
    spot_id: int,
    langs: Optional[str] = Query(None, description="comma separated, e.g. 'ja,en'"),
    min_duration: Optional[int] = Query(None, ge=0),
    max_duration: Optional[int] = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    lang_list: Optional[List[str]] = None
    if langs:
        lang_list = [x.strip() for x in langs.split(",") if x.strip()]

    # Spot に紐づく Content を取得
    j = select(Content).join(SpotContent, SpotContent.content_id == Content.id).where(SpotContent.spot_id == spot_id)
    if lang_list:
        j = j.where(Content.lang.in_(lang_list))
    if min_duration is not None:
        j = j.where(Content.duration_min >= min_duration)
    if max_duration is not None:
        j = j.where(Content.duration_min <= max_duration)

    rows = db.execute(j.limit(limit)).scalars().all()
    return {
        "count": len(rows),
        "items": [{
            "id": c.id,
            "title": c.title,
            "media_type": c.media_type,
            "media_url": getattr(c, "media_url", None),
            "youtube_id": getattr(c, "youtube_id", None),
            "lang": getattr(c, "lang", None),
            "thumbnail_url": getattr(c, "thumbnail_url", None),
            "duration_min": getattr(c, "duration_min", None),
        } for c in rows]
    }
