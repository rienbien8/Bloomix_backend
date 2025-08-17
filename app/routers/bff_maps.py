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