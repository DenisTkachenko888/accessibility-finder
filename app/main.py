from __future__ import annotations

from typing import List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, Query

from app.config import get_settings
from app.models import Place, SearchRequest
from app.services.accessibility import fetch_accessible_places, geocode_query, list_categories

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Service to find accessible places using OpenStreetMap data.",
)


@app.get("/", tags=["Root"])
async def root():
    return {"ok": True, "service": settings.app_name, "version": settings.version}


@app.get("/health", tags=["Healthcheck"])
async def health():
    return {"ok": True}


@app.get("/api/categories", tags=["Api Categories"])
async def api_categories():
    return {"categories": list_categories()}


@app.get("/api/geocode", tags=["Api Geocode"])
async def api_geocode(q: str = Query(..., min_length=2, description="Free-text location query")):
    async with aiohttp.ClientSession() as session:
        try:
            lat, lon, display_name = await geocode_query(session, q)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except aiohttp.ClientResponseError as e:
            raise HTTPException(status_code=502, detail=f"Nominatim error: {e.status}")

    return {"query": q, "lat": lat, "lon": lon, "display_name": display_name}


@app.get("/api/search", response_model=List[Place], tags=["Api Search"])
async def api_search(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    category: str = Query(..., min_length=1),
    radius_m: Optional[int] = Query(None, ge=50, le=50_000),
    limit: int = Query(20, ge=1, le=100),
    wheelchair: Optional[str] = Query(None, pattern="^(yes|no|limited|unknown)$"),
    toilets_wheelchair: Optional[str] = Query(None, pattern="^(yes|no|unknown)$"),
    step_free: Optional[bool] = Query(None),
):
    async with aiohttp.ClientSession() as session:
        try:
            places = await fetch_accessible_places(
                session,
                lat=lat,
                lon=lon,
                category=category,
                radius_m=radius_m,
                limit=limit,
                wheelchair=wheelchair,
                toilets_wheelchair=toilets_wheelchair,
                step_free=step_free,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except aiohttp.ClientResponseError as e:
            raise HTTPException(status_code=502, detail=f"Overpass error: {e.status}")

    return places


@app.post("/search", response_model=List[Place], tags=["Search Places"])
async def legacy_search(req: SearchRequest):
    """Legacy endpoint (kept for compatibility). Prefer GET /api/geocode + GET /api/search."""
    async with aiohttp.ClientSession() as session:
        try:
            lat, lon, _ = await geocode_query(session, req.query)
            places = await fetch_accessible_places(session, lat=lat, lon=lon, category=req.category)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except aiohttp.ClientResponseError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e.status}")

    return places
