# app/utils/geo.py
import math
from typing import Tuple

EARTH_RADIUS_KM = 6371.0088

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometers."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c

def bbox_center(min_lat: float, min_lng: float, max_lat: float, max_lng: float) -> Tuple[float, float]:
    return ( (min_lat + max_lat) / 2.0, (min_lng + max_lng) / 2.0 )
