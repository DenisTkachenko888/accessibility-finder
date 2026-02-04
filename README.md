# Accessibility Finder API

Service to find accessible places using **OpenStreetMap** data via **Nominatim** (geocoding) and **Overpass API** (POI search).

> This repository currently contains the **backend (FastAPI)** only.

---

## Features

- **Geocoding**: free-text location → coordinates (lat/lon)
- **Search**: find nearby places by category within a radius
- Optional accessibility filters (when available in OSM tags):
  - `wheelchair`: `yes | no | limited | unknown`
  - `toilets_wheelchair`: `yes | no | unknown`
  - `step_free`: `true | false`

---

## Tech stack

- Python 3.10+ (tested on 3.12)
- FastAPI
- Uvicorn
- aiohttp
- Pydantic / pydantic-settings

---

## Installation (local)

Create and activate virtual environment:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run dev server:

```bash
uvicorn app.main:app --reload
```

Open API docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## Configuration

By default the service uses public endpoints. If you want to point to your own instances (recommended for production), use environment variables (see `app/config.py`):

- `NOMINATIM_BASE_URL` (default: public Nominatim)
- `OVERPASS_API_URL` (default: public Overpass)
- `CACHE_TTL_S` (default: 120 seconds)
- `CACHE_MAX_SIZE` (default: 512 entries)

Example (PowerShell):

```powershell
$env:NOMINATIM_BASE_URL="https://nominatim.openstreetmap.org"
$env:OVERPASS_API_URL="https://overpass-api.de/api/interpreter"
```

---

## API

### Healthcheck

- `GET /health` → `{ "status": "ok" }` (or similar)

### Geocode

- `GET /api/geocode?q=...`  
  Free-text location query (min length: 2).

Example:

```bash
curl "http://127.0.0.1:8000/api/geocode?q=Times%20Square"
```

### Search

- `GET /api/search`

Query parameters:

- `lat` *(required)*: number `[-90..90]`
- `lon` *(required)*: number `[-180..180]`
- `category` *(required)*: non-empty string (e.g. `cafe`, `shop`, `transport`, etc.)
- `radius_m` *(optional)*: integer (search radius in meters)
- `limit` *(optional)*: integer `[1..100]`, default `20`
- `wheelchair` *(optional)*: `yes|no|limited|unknown`
- `toilets_wheelchair` *(optional)*: `yes|no|unknown`
- `step_free` *(optional)*: `true|false`

Example:

```bash
curl "http://127.0.0.1:8000/api/search?lat=40.7580&lon=-73.9855&category=cafe&radius_m=800&limit=10&wheelchair=yes"
```

Response sample:

```json
[
  {
    "name": "Cafe Example",
    "lat": 40.0,
    "lon": -73.0,
    "distance_m": 120,
    "address": "Some address",
    "osm_id": 123,
    "osm_type": "node",
    "category": "cafe"
  }
]
```

### Categories

- `GET /api/categories`  
  Returns supported categories and their OSM tag filters.

### Legacy endpoint

- `POST /search`  
  **Legacy endpoint (kept for compatibility).** Prefer: `GET /api/geocode` + `GET /api/search`.

Request:

```json
{
  "query": "Тверской район",
  "category": "cafe"
}
```

Example:

```bash
curl -X POST "http://127.0.0.1:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"Тверской район","category":"cafe"}'
```

> On Windows `cmd` you may need to escape quotes differently.

---

## Docker (compose)

A minimal `docker-compose.yml` is included.

```bash
docker compose up --build
```

Then open docs:

- `http://127.0.0.1:8000/docs`

> If you add env vars to compose, make sure to pass `NOMINATIM_BASE_URL` and `OVERPASS_API_URL` as needed.

---

## Testing

Run unit tests:

```bash
pytest
```

Manual API smoke checks (after `uvicorn app.main:app --reload`):

```bash
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/api/categories"
curl "http://127.0.0.1:8000/api/geocode?q=Times%20Square"
curl "http://127.0.0.1:8000/api/search?lat=40.7580&lon=-73.9855&category=cafe&radius_m=800&limit=5"
```

---

## Project structure

```
app/
  main.py              # FastAPI app + routes
  config.py            # settings (env)
  models.py            # pydantic models
  services/
    accessibility.py   # OSM queries (Nominatim / Overpass)
```

---

## Roadmap

- Reverse-geocoding for nicer addresses
- More categories and better category config
- Caching & rate limiting
- Tests + CI (lint, type-check, unit tests)
- Frontend (optional): map view, filters, saved places

---

## License

MIT — see [LICENSE](LICENSE).
