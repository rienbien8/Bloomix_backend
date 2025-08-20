# app/routers/bff_maps.py
from fastapi import APIRouter, HTTPException, Query
import os, requests

router = APIRouter(prefix="/bff/maps", tags=["bff-maps"])

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_MAPS_API_KEY is not set")

PLACES_BASE = "https://places.googleapis.com/v1"

@router.get("/autocomplete")
def autocomplete(
    q: str = Query(..., description="検索キーワード"),
    language: str = Query("ja", description="言語（languageCode）"),
    origin: str | None = Query(None, description="lat,lng（任意）"),
    radius_m: int | None = Query(None, description="場所バイアス半径[m] 任意"),
):
    """
    Places API（New）の Autocomplete を呼ぶ。
    POST https://places.googleapis.com/v1/places:autocomplete
    """
    body = {"input": q, "languageCode": language}

    # 任意: 原点バイアス・距離
    if origin:
        try:
            lat, lng = [float(x) for x in origin.split(",")]
            body["origin"] = {"latitude": lat, "longitude": lng}
            if radius_m:
                body["locationBias"] = {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius_m),
                    }
                }
        except Exception:
            pass  # 無効なoriginは無視

    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": API_KEY}
    r = requests.post(f"{PLACES_BASE}/places:autocomplete", headers=headers, json=body, timeout=6)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    data = r.json()

    # 旧版に似せた出力へ整形（frontendを触らずに移行するため）
    preds = []
    for s in data.get("suggestions", []):
        p = s.get("placePrediction", {}) or {}
        text = (p.get("text") or {}).get("text")
        fmt = p.get("structuredFormat") or {}
        main = (fmt.get("mainText") or {}).get("text")
        sec = (fmt.get("secondaryText") or {}).get("text")
        preds.append({
            "place_id": p.get("placeId") or (p.get("place") or "").replace("places/",""),
            "description": text or main or "",
            "structured_formatting": {"main_text": main, "secondary_text": sec},
        })
    return {"predictions": preds}

@router.get("/place-details")
def place_details(
    place_id: str = Query(..., description="Googleのplace_id（ChIJ...）"),
    language: str = Query("ja", description="言語（languageCode）"),
):
    """
    Places API（New）の Place Details を呼ぶ。
    GET https://places.googleapis.com/v1/places/{placeId}
    ※ FieldMask 必須
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,location",
    }
    params = {"languageCode": language}
    r = requests.get(f"{PLACES_BASE}/places/{place_id}", headers=headers, params=params, timeout=6)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    res = r.json()
    return {
        "place_id": res.get("id") or place_id,
        "name": (res.get("displayName") or {}).get("text"),
        "address": res.get("formattedAddress"),
        "location": res.get("location"),  # {"latitude": .., "longitude": ..}
    }


@router.get("/search-text")
def search_text(
    q: str = Query(..., description="自由文の検索語（例: 渋谷 Snow Man ライブ会場）"),
    language: str = Query("ja", description="言語コード（languageCode）"),
    region: str = Query("JP", description="地域（regionCode）"),
    origin: str | None = Query(None, description="バイアス中心 lat,lng（任意）"),
    radius_m: int | None = Query(3000, description="バイアス半径[m]（任意）"),
    limit: int = Query(10, ge=1, le=20),
):
    """
    テキスト部分の検索
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        # 返すフィールドを絞る（FieldMask）
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.types",
    }
    body: dict = {
        "textQuery": q,
        "languageCode": language,
        "regionCode": region,
        "maxResultCount": limit,
    }
    # 位置バイアス（任意）
    if origin:
        try:
            lat, lng = [float(x) for x in origin.split(",")]
            if radius_m:
                body["locationBias"] = {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius_m),
                    }
                }
        except Exception:
            pass

    r = requests.post(f"{PLACES_BASE}/places:searchText", headers=headers, json=body, timeout=8)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    data = r.json()
    items = []
    for p in data.get("places", []):
        items.append({
            "place_id": p.get("id"),
            "name": (p.get("displayName") or {}).get("text"),
            "address": p.get("formattedAddress"),
            "location": p.get("location"),  # {"latitude":..,"longitude":..}
            "types": p.get("types", []),
        })
    return {"count": len(items), "items": items}

# /bff/maps/route追記
@router.get("/route")
def compute_route(
    origin: str = Query(..., description="lat,lng 出発地"),
    destination: str = Query(..., description="lat,lng 目的地"),
    language: str = Query("ja", description="言語コード"),
    waypoints: str | None = Query(None, description="経由地 lat,lng|lat,lng..."),
    alternatives: int = Query(1, description="代替ルートを返すか"),
):
    """
    Google Routes API v2: computeRoutes
    - 最短ルートとエコルートを返す
    """
    if not API_KEY:
        raise HTTPException(500, "GOOGLE_MAPS_API_KEY not configured")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": (
            "routes.duration,"
            "routes.distanceMeters,"
            "routes.polyline.encodedPolyline,"
            "routes.travelAdvisory.fuelConsumptionMicroliters,"
            "routes.routeLabels"  # ← 追加
        ),
    }

    def parse_latlng(s: str):
        lat, lng = [float(x) for x in s.split(",")]
        return {"location": {"latLng": {"latitude": lat, "longitude": lng}}}

    body = {
        "origin": parse_latlng(origin),
        "destination": parse_latlng(destination),
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "polylineQuality": "OVERVIEW",
        "computeAlternativeRoutes": True,  # ←代替ルートを必ず返す
        "languageCode": language,
        "extraComputations": ["FUEL_CONSUMPTION"],
    }
    if waypoints:
        body["intermediates"] = [
            parse_latlng(w) for w in waypoints.split("|") if w
        ]

    r = requests.post(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        headers=headers,
        json=body,
        timeout=10,
    )
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    data = r.json()

    # 整形
    
    
    routes = []
    for idx, rt in enumerate(data.get("routes", [])):
        dur_sec = float(str(rt.get("duration", "0s")).replace("s", "")) if rt.get("duration") else 0
        dist_m = rt.get("distanceMeters", 0)
        poly = (rt.get("polyline") or {}).get("encodedPolyline")
        fuel = (rt.get("travelAdvisory") or {}).get("fuelConsumptionMicroliters")
        labels = rt.get("routeLabels", []) or []

        # 一応ラベルでエコ判定できる時は拾う
        rtype = "eco" if "FUEL_EFFICIENT" in labels else ("fastest" if idx == 0 else "eco")
        
        routes.append({
            "type": rtype,
            "duration_min": round(dur_sec / 60, 1),
            "distance_km": round(dist_m / 1000, 1),
            "polyline": poly,
            "advisory": {
                "fuel_consumption_ml": int(fuel/1000) if fuel else None
            },
            "labels": labels
        })
        
    

    # --- 3) フォールバック（二択を保証）---
    if len(routes) == 1:
        # 同じものを eco として複製（メモを残す）
        clone = {**routes[0], "type": "eco"}
        if "labels" in clone:
            clone["labels"] = list(set([*clone.get("labels", []), "FALLBACK_DUP"]))
        routes.append(clone)

    # "fastest" を先、"eco" を後に並べ替え（念のため）
    routes = sorted(routes, key=lambda r: 0 if r["type"] == "fastest" else 1)

    return {"routes": routes}