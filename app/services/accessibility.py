from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

import aiohttp

from app.config import get_settings
from app.models import Place

# Very small starter mapping (easy to extend)
# If you want a new category: add more tag tuples for it (key, value).
CATEGORY_TAGS: dict[str, list[tuple[str, str]]] = {
    "cafe": [("amenity", "cafe")],
    "restaurant": [("amenity", "restaurant")],
    "bar": [("amenity", "bar")],
    "hospital": [("amenity", "hospital"), ("amenity", "clinic")],
    "pharmacy": [("amenity", "pharmacy")],
    "toilets": [("amenity", "toilets")],
    "parking": [("amenity", "parking")],
    "atm": [("amenity", "atm")],
    "bank": [("amenity", "bank")],
    "museum": [("tourism", "museum")],
    "hotel": [("tourism", "hotel")],
    "supermarket": [("shop", "supermarket")],
    "shop": [("shop", "yes")],  # fallback: many shops use specific values, so this may be imperfect
    "bus_stop": [("highway", "bus_stop")],
}

_STEP_FREE_KEYS = (
    "step_free_access",
    "step_free",
    "entrance:step_free",
    "wheelchair",  # sometimes used as a proxy, but we keep separate filters too
    "entrance:step_count",
    "step_count",
)

YES_VALUES = {"yes", "true", "1"}
NO_VALUES = {"no", "false", "0"}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two WGS84 coords."""
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _addr_from_tags(tags: Dict[str, Any]) -> str:
    parts = []
    street = tags.get("addr:street")
    house = tags.get("addr:housenumber")
    city = tags.get("addr:city")
    if street:
        parts.append(str(street))
    if house:
        parts.append(str(house))
    if city:
        parts.append(str(city))
    return ", ".join(parts)


def _tag_match(value: Optional[str], desired: Optional[str]) -> bool:
    if desired is None:
        return True
    if desired == "unknown":
        return value is None or value == "unknown"
    return value == desired


def _step_free_value(tags: Dict[str, Any]) -> Optional[bool]:
    # best-effort: infer step-free from known tags
    for k in ("step_free_access", "step_free", "entrance:step_free"):
        v = tags.get(k)
        if isinstance(v, str):
            vv = v.strip().lower()
            if vv in YES_VALUES:
                return True
            if vv in NO_VALUES:
                return False

    # step_count=0 => step-free; any positive => not step-free
    for k in ("entrance:step_count", "step_count"):
        v = tags.get(k)
        if v is None:
            continue
        try:
            n = int(str(v).strip())
            return n == 0
        except ValueError:
            continue

    return None


async def geocode_query(session: aiohttp.ClientSession, q: str) -> Tuple[float, float, str]:
    """Geocode a free-text location query (Nominatim). Returns (lat, lon, display_name)."""
    settings = get_settings()
    params = {
        "q": q,
        "format": "jsonv2",
        "limit": 1,
        "addressdetails": 1,
    }
    if settings.nominatim_email:
        params["email"] = settings.nominatim_email

    headers = {"User-Agent": settings.user_agent}
    timeout = aiohttp.ClientTimeout(total=settings.http_timeout_s)

    async with session.get(str(settings.nominatim_base_url), params=params, headers=headers, timeout=timeout) as resp:
        resp.raise_for_status()
        data = await resp.json()

    if not data:
        raise ValueError("Location not found")

    item = data[0]
    return float(item["lat"]), float(item["lon"]), str(item.get("display_name", ""))


def _category_filters(category: str) -> List[Tuple[str, str]]:
    # Allow power-user form: "key=value"
    if "=" in category and len(category.split("=", 1)[0]) > 0:
        k, v = category.split("=", 1)
        return [(k.strip(), v.strip())]

    if category not in CATEGORY_TAGS:
        raise ValueError(
            f"Unknown category '{category}'. Supported: {', '.join(sorted(CATEGORY_TAGS.keys()))} "
            "or pass raw tag like 'amenity=cafe'."
        )
    return CATEGORY_TAGS[category]


def _overpass_query(lat: float, lon: float, radius_m: int, tag_key: str, tag_value: str,
                    wheelchair: Optional[str], toilets_wheelchair: Optional[str]) -> str:
    extra = ""
    # If we can push filters to Overpass - do it (unknown can't be expressed reliably)
    if wheelchair and wheelchair != "unknown":
        extra += f'[wheelchair={wheelchair}]'
    if toilets_wheelchair and toilets_wheelchair != "unknown":
        extra += f'["toilets:wheelchair"={toilets_wheelchair}]'

    # Note: for ways/relations we request center.
    return f"""[out:json][timeout:25];
(
  node(around:{radius_m},{lat},{lon})[{tag_key}={tag_value}]{extra};
  way(around:{radius_m},{lat},{lon})[{tag_key}={tag_value}]{extra};
  relation(around:{radius_m},{lat},{lon})[{tag_key}={tag_value}]{extra};
);
out center tags;
"""


async def fetch_accessible_places(
    session: aiohttp.ClientSession,
    *,
    lat: float,
    lon: float,
    category: str,
    radius_m: Optional[int] = None,
    limit: int = 20,
    wheelchair: Optional[str] = None,
    toilets_wheelchair: Optional[str] = None,
    step_free: Optional[bool] = None,
) -> List[Place]:
    """Search places by category near (lat, lon) using Overpass."""
    settings = get_settings()

    if radius_m is None:
        radius_m = 1500

    cat_filters = _category_filters(category)

    timeout = aiohttp.ClientTimeout(total=settings.http_timeout_s)

    elements: list[dict[str, Any]] = []
    for (k, v) in cat_filters:
        query = _overpass_query(lat, lon, radius_m, k, v, wheelchair, toilets_wheelchair)
        async with session.post(str(settings.overpass_base_url), data={"data": query}, timeout=timeout) as resp:
            resp.raise_for_status()
            data = await resp.json()
        elements.extend(data.get("elements", []))

    # Deduplicate by (type, id)
    seen: set[tuple[str, int]] = set()
    places: list[Place] = []

    for el in elements:
        osm_type = str(el.get("type", ""))
        osm_id = int(el.get("id", 0))
        key = (osm_type, osm_id)
        if key in seen:
            continue
        seen.add(key)

        # Coordinates: node => lat/lon, others => center
        if osm_type == "node":
            plat = el.get("lat")
            plon = el.get("lon")
        else:
            center = el.get("center") or {}
            plat = center.get("lat")
            plon = center.get("lon")

        if plat is None or plon is None:
            continue

        tags = el.get("tags") or {}

        # Filters
        if not _tag_match(tags.get("wheelchair"), wheelchair):
            continue
        if not _tag_match(tags.get("toilets:wheelchair"), toilets_wheelchair):
            continue

        step_val = _step_free_value(tags)
        if step_free is True and step_val is not True:
            continue
        if step_free is False and step_val is True:
            continue

        name = tags.get("name") or tags.get("brand") or f"{category} ({osm_type}:{osm_id})"
        address = _addr_from_tags(tags)
        dist = _haversine_m(lat, lon, float(plat), float(plon))

        places.append(
            Place(
                name=str(name),
                lat=float(plat),
                lon=float(plon),
                distance_m=float(dist),
                address=address,
                osm_id=osm_id,
                osm_type=osm_type,
                category=category,
            )
        )

    places.sort(key=lambda p: p.distance_m)
    return places[: max(1, min(limit, 100))]
