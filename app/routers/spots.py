# app/routers/spots.py
from typing import Optional, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_, text
from sqlalchemy.orm import Session

from app.db import get_session  # 既存のdb.pyのセッションジェネレータ
# ↓ ここは app/models.py の実クラス名に合わせて変更してください
from app.models import Spot, Content, SpotContent  # type: ignore

from app.utils.geo import haversine_km, bbox_center
import math

router = APIRouter(prefix="/api/v1/spots", tags=["spots"])

def decode_polyline(polyline: str) -> list:
    """Google Maps polylineをデコードして座標点のリストを返す"""
    try:
        print(f"DEBUG: Decoding polyline of length {len(polyline)}")
        # 簡易的なpolyline decoder
        # 実際の実装では、Google Maps APIのpolyline decoderを使用することを推奨
        points = []
        index = 0
        lat = 0
        lng = 0
        
        while index < len(polyline):
            # 緯度のデコード
            shift = 0
            result = 0
            while True:
                byte = ord(polyline[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if not byte >= 0x20:
                    break
            lat += (~(result >> 1) if (result & 1) else (result >> 1))
            
            # 経度のデコード
            shift = 0
            result = 0
            while True:
                byte = ord(polyline[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if not byte >= 0x20:
                    break
            lng += (~(result >> 1) if (result & 1) else (result >> 1))
            
            points.append((lat * 1e-5, lng * 1e-5))
        
        print(f"DEBUG: Successfully decoded {len(points)} points")
        if points:
            print(f"DEBUG: First point: {points[0]}, Last point: {points[-1]}")
        return points
    except Exception as e:
        print(f"DEBUG: Error decoding polyline: {str(e)}")
        return []

def calculate_distance_to_route(spot_lat: float, spot_lng: float, route_points: list) -> float:
    """スポットからルートまでの最短距離を計算（メートル単位）"""
    if not route_points:
        return float('inf')
    
    min_distance = float('inf')
    
    # ルートの各セグメントに対して距離を計算
    for i in range(len(route_points) - 1):
        lat1, lng1 = route_points[i]
        lat2, lng2 = route_points[i + 1]
        
        # セグメントの両端点からの距離を計算
        dist1 = haversine_km(spot_lat, spot_lng, lat1, lng1) * 1000  # km to m
        dist2 = haversine_km(spot_lat, spot_lng, lat2, lng2) * 1000  # km to m
        
        # セグメントの長さ
        segment_length = haversine_km(lat1, lng1, lat2, lng2) * 1000  # km to m
        
        if segment_length == 0:
            min_distance = min(min_distance, dist1)
            continue
        
        # スポットからセグメントへの垂線の距離を計算
        # ベクトル計算による最短距離
        dot_product = ((spot_lat - lat1) * (lat2 - lat1) + (spot_lng - lng1) * (lng2 - lng1)) / (segment_length * segment_length)
        
        if dot_product <= 0:
            # スポットはセグメントの端点1に最も近い
            min_distance = min(min_distance, dist1)
        elif dot_product >= 1:
            # スポットはセグメントの端点2に最も近い
            min_distance = min(min_distance, dist2)
        else:
            # スポットはセグメント上に垂線を下ろせる
            projection_lat = lat1 + dot_product * (lat2 - lat1)
            projection_lng = lng1 + dot_product * (lng2 - lng1)
            projection_distance = haversine_km(spot_lat, spot_lng, projection_lat, projection_lng) * 1000
            min_distance = min(min_distance, projection_distance)
    
    return min_distance

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

@router.get("/along-route")
def get_spots_along_route(
    polyline: str = Query(..., description="Google Maps encoded polyline"),
    buffer_m: int = Query(1000, description="Buffer distance in meters"),
    user_id: Optional[int] = Query(None, description="User ID for filtering"),
    followed_only: Optional[int] = Query(None, description="Show only followed spots (0 or 1)"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_session),
):
    """ルート沿いのスポットを返す"""
    try:
        print(f"DEBUG: Received polyline: {polyline[:50]}...")
        print(f"DEBUG: Buffer distance: {buffer_m}m")
        
        # polylineをデコードしてルートの座標点を取得
        route_points = decode_polyline(polyline)
        print(f"DEBUG: Decoded route points: {len(route_points)} points")
        if not route_points:
            raise HTTPException(status_code=422, detail="Invalid polyline")
        
        # 基本的なスポット取得
        stmt = select(Spot)
        
        # followed_onlyフィルタ（将来的に実装）
        if followed_only is not None:
            # TODO: ユーザーのフォローしているスポットのみをフィルタ
            pass
            
        candidates = db.execute(stmt.limit(limit * 2)).scalars().all()
        print(f"DEBUG: Found {len(candidates)} total spots in database")
        
        items = []
        for s in candidates:
            # スポットからルートまでの最短距離を計算
            min_distance = calculate_distance_to_route(float(s.lat), float(s.lng), route_points)
            
            # バッファ距離内のスポットのみを追加
            if min_distance <= buffer_m:
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
                    "distance_m": int(min_distance),
                })
        
        print(f"DEBUG: Found {len(items)} spots within {buffer_m}m buffer")
        
        # 距離順にソート
        items.sort(key=lambda x: x["distance_m"])
        return items[:limit]
        
    except Exception as e:
        print(f"DEBUG: Error in along-route: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get spots along route: {str(e)}")

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
