"""
Geo utilities — extracted from data_collection.py.
Web Mercator projection + Haversine distance.
"""

from __future__ import annotations
import math
import threading
import time
from typing import Tuple

import requests


def lonlat_to_tile_xy(lon: float, lat: float, zoom: float) -> Tuple[float, float]:
    """Convert lon/lat to tile x/y at given zoom level."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def tile_xy_to_lonlat(x: float, y: float, zoom: float) -> Tuple[float, float]:
    """Convert tile x/y to lon/lat at given zoom level."""
    n = 2.0 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lon, lat


def snapshot_pixel_to_lonlat(
    px: float, py: float,
    center_ll: Tuple[float, float],
    z_level: float,
    img_w: int, img_h: int,
) -> Tuple[float, float]:
    """Convert pixel coordinates (relative to image top-left) to lon/lat."""
    lon0, lat0 = center_ll
    xtile0, ytile0 = lonlat_to_tile_xy(lon0, lat0, z_level)
    px_per_tile = 256
    dx = px - img_w / 2
    dy = py - img_h / 2
    xtile = xtile0 + dx / px_per_tile
    ytile = ytile0 + dy / px_per_tile
    return tile_xy_to_lonlat(xtile, ytile, z_level)


def snapshot_lonlat_to_pixel(
    lon: float, lat: float,
    center_ll: Tuple[float, float],
    z_level: float,
    img_w: int, img_h: int,
) -> Tuple[float, float]:
    """Convert lon/lat to pixel coordinates on a snapshot image."""
    lon0, lat0 = center_ll
    cx, cy = lonlat_to_tile_xy(lon0, lat0, z_level)
    px, py = lonlat_to_tile_xy(lon, lat, z_level)
    tile_size = 256
    screen_x = img_w / 2 + (px - cx) * tile_size
    screen_y = img_h / 2 + (py - cy) * tile_size
    return screen_x, screen_y


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great circle distance in meters between two points. Written in the
    order the page measured it before (frontend/src/utils/geoUtils.ts), so the
    distances come out the same to the last digit."""
    R = 6371e3  # Earth radius in meters
    d_lat = ((lat2 - lat1) * math.pi) / 180
    d_lon = ((lon2 - lon1) * math.pi) / 180
    a = (math.sin(d_lat / 2) * math.sin(d_lat / 2)
         + math.cos((lat1 * math.pi) / 180) * math.cos((lat2 * math.pi) / 180)
         * math.sin(d_lon / 2) * math.sin(d_lon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def manhattan_spherical_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """North-south plus east-west distance, meters: along the streets rather
    than across the site."""
    return haversine_distance(lat1, lon1, lat2, lon1) + haversine_distance(lat2, lon1, lat2, lon2)


# Nominatim's usage policy: at most one request per second from the whole
# server, or it blocks the server's address. Requests wait for their turn, but
# not long: a queue of waiting lookups would hold the threads every other
# endpoint runs on.
NOMINATIM_INTERVAL = 1.0
NOMINATIM_MAX_WAIT = 3.0
_nominatim_lock = threading.Lock()
_nominatim_next = 0.0


class GeocodeBusy(RuntimeError):
    pass


def _nominatim_turn() -> None:
    """Wait for this request's one-second slot (process-wide)."""
    global _nominatim_next
    with _nominatim_lock:
        now = time.monotonic()
        slot = max(now, _nominatim_next)
        if slot - now > NOMINATIM_MAX_WAIT:
            raise GeocodeBusy("The address search is busy; try again in a few seconds.")
        _nominatim_next = slot + NOMINATIM_INTERVAL
    if slot > now:
        time.sleep(slot - now)


def geocode_address(query: str) -> list[dict]:
    """
    Geocode an address using Nominatim.
    Returns list of {display_name, lat, lon} results.
    """
    _nominatim_turn()
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 5}
    headers = {"User-Agent": "HeatTransPlan/1.0"}
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    return [
        {
            "display_name": r.get("display_name", ""),
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
        }
        for r in results
    ]
