from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Адрес/район/место для геокодинга")
    category: str = Field(..., min_length=1, description="Код категории (например: cafe, hospital, shop)")


class Place(BaseModel):
    name: str
    lat: float
    lon: float
    distance_m: float
    address: str = ""
    osm_id: int
    osm_type: str
    category: str
