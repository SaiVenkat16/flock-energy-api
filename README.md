# Flock Energy — Urja Meter Ops REST API Wrapper

A high-performance, strongly-typed, and modern REST API proxy layer built on top of the legacy **Urja Meter Ops** portal (`https://urja-ops.flockenergy.tech`).

---

## Quick Links
* **Protocol & Reverse-Engineering Findings:** [PROTOCOL.md](file:///c:/Users/SaiVe/Desktop/flock-energy-api/PROTOCOL.md)
* **OpenAPI 3.0 Specification:** [openapi.json](file:///c:/Users/SaiVe/Desktop/flock-energy-api/openapi.json)
* **Engineering Reflections & Self-Critique:** [REFLECTION.md](file:///c:/Users/SaiVe/Desktop/flock-energy-api/REFLECTION.md)
* **Interactive Documentation (when running):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 1. What Was Built & Architecture

The legacy **Urja Meter Ops** platform requires manual operator browsing and presents heterogeneous data structures across different meter revisions (`legacy` vs `v2`). This service acts as an intelligent **Adapter & Caching Proxy**:

```mermaid
flowchart LR
    DownstreamClient[Downstream Client / Mobile / Frontend] -->|REST / JSON| FastAPI[FastAPI Adapter Service]
    FastAPI --> InMem[In-Memory Index & Geo Engine]
    FastAPI --> Adapter[UrjaPortalClient]
    Adapter -->|Session / HMAC Signed Export| UrjaPortal[(Urja Meter Ops Portal)]
```

### Key Capabilities
1. **Automated Authentication & Session Resilience:**
   - Emulates operator login with browser-grade headers (`Origin`, `Referer`) bypassing SvelteKit CSRF checks.
   - Transparently handles session token lifecycle (`__Secure-better-auth.session_token`).
   - Automatically detects HTTP 401, re-authenticates in the background, and retries the request without failing the downstream client.
2. **Normalized Data Schemas:**
   - Reconciles the schema split between 238 `legacy` meters (flat parameter arrays) and 165 `v2` meters (`classData` JSON strings) into a unified, strongly-typed Pydantic model.
   - Cleanses whitespace, normalizes Indian datetime strings (`DD/MM/YYYY HH:MM`) to ISO-8601 UTC timestamps, and casts numeric string fields (`kwh`, `kvah`, `voltR`) into floats while handling dropouts (`—`, empty strings).
3. **Advanced Local Query & Indexing Layer:**
   - Overcomes the legacy portal's search limitations (which only matches meter ID or serial with a fixed 20-item page size).
   - Enables multi-attribute filtering across `make`, `phase_type`, `install_status`, `dt_code`, `build`, and `install_type` with custom sorting and configurable pagination.
4. **Spatial Proximity Query (`/api/v1/meters/nearby`):**
   - Geodesic distance calculation via the Haversine formula to query smart meters within a specified radius (`radius_km`) of any GPS coordinate.
5. **Network Hierarchy Reconstruction (`/api/v1/hierarchy`):**
   - Rebuilds the 7-level distribution grid hierarchy tree:
     `Zone` → `Circle` → `Division` → `Subdivision` → `Substation` → `Feeder` → `Distribution Transformer (DT)` → `Meters`.
6. **High-Speed Cryptographic Bulk Extraction:**
   - Discovered and implemented the HMAC-SHA256 signature algorithm against `/portal/keys` and `/portal/export?page=1` to hydrate all 403 meters in a single HTTP transaction.

---

## 2. Directory Structure

```text
flock-energy-api/
├── app/
│   ├── __init__.py
│   ├── config.py         # Environment variables & runtime settings
│   ├── models.py         # Strongly-typed Pydantic schemas & response models
│   ├── client.py         # Upstream Urja portal HTTP client, auth, & HMAC signer
│   ├── indexer.py        # In-memory query engine, Haversine geo search, & hierarchy
│   ├── cache.py          # DataStore & stale-while-revalidate synchronization
│   └── main.py           # FastAPI routes, middleware, lifespan, & Swagger UI
├── tests/
│   ├── __init__.py
│   ├── test_indexer.py   # Unit tests for filtering, proximity, & hierarchy
│   └── test_api.py       # Integration tests for REST API endpoints
├── .env.example          # Sample environment configuration
├── .gitignore            # Git exclusion rules
├── openapi.json          # Exported OpenAPI 3.0 specification
├── PROTOCOL.md           # Detailed reverse-engineering protocol write-up
├── README.md             # Project documentation & operational guide
├── REFLECTION.md         # Answers to mandatory reflection questions
└── requirements.txt      # Python dependencies
```

---

## 3. Installation & Getting Started

### Prerequisites
* **Python 3.10+** (Tested on Python 3.13)
* Internet access to reach `https://urja-ops.flockenergy.tech`

### Setup Instructions

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd flock-energy-api

# 2. Create and activate a virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
# source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (optional, defaults are pre-configured)
cp .env.example .env

# 5. Start the REST API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will automatically perform an initial sync on startup. Visit:
* **Interactive Swagger Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Alternative Redoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Raw OpenAPI Specification:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 4. Running Automated Tests

Run the full automated test suite with `pytest`:

```bash
pytest tests/ -v
```

All 11 unit and integration tests will execute:
* Spatial distance accuracy (Haversine formula verification)
* Multi-attribute filtering (make, phase, status, search query)
* Network hierarchy tree generation
* REST endpoint validation (health, meters, detail, geo, nearby, transformers)

---

## 5. Sample API Requests & Responses

### 1. Health & Sync Status
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```
**Response:**
```json
{
  "status": "healthy",
  "portal_status": "connected",
  "cached_meters_count": 403,
  "last_synced_at": "2026-10-24T11:30:00.000000+00:00",
  "cache_ttl_seconds": 300
}
```

### 2. Search & Filter Meters
```bash
# Filter single-phase meters manufactured by HPL with status 'Installed'
curl -X GET "http://localhost:8000/api/v1/meters?make=HPL&phase_type=single&install_status=Installed&page=1&page_size=2"
```
**Response:**
```json
{
  "total": 52,
  "page": 1,
  "page_size": 2,
  "total_pages": 26,
  "data": [
    {
      "meter_id": "J100010",
      "serial_no": "SE12894",
      "make": "HPL",
      "phase_type": "single",
      "install_status": "Installed",
      "install_type": "Whole Current",
      "build": "legacy",
      "dt_code": "DT-002",
      "hierarchy": { ... },
      "geo": { "latitude": 26.941, "longitude": 75.832 }
    }
  ]
}
```

### 3. Spatial Proximity Query (What's near this location?)
```bash
# Find meters within 3.0 km of Jaipur coordinates (26.938, 75.830)
curl -X GET "http://localhost:8000/api/v1/meters/nearby?lat=26.938&lng=75.830&radius_km=3.0&limit=3"
```
**Response:**
```json
[
  {
    "meter_id": "J100000",
    "serial_no": "SE33962",
    "make": "HPL",
    "phase_type": "single",
    "install_status": "Decommissioned",
    "dt_code": "DT-001",
    "latitude": 26.938961,
    "longitude": 75.830956,
    "distance_km": 0.143
  }
]
```

### 4. Normalized Energy Consumption History
```bash
curl -X GET "http://localhost:8000/api/v1/meters/J100000/consumption"
```
**Response:**
```json
{
  "meter_id": "J100000",
  "total_readings": 48,
  "min_voltage_v": 218.0,
  "max_voltage_v": 242.0,
  "latest_kwh": 48458.50,
  "readings": [
    {
      "timestamp": "2026-06-23T23:30:00",
      "raw_timestamp": "23/06/2026 23:30",
      "kwh": 48438.74,
      "kvah": 52313.84,
      "volt_r": 226.0
    }
  ]
}
```

---

## 6. Design Decisions & Trade-Offs

| Decision | Chosen Approach | Alternative Considered | Rationale / Trade-Off |
| :--- | :--- | :--- | :--- |
| **Framework** | **FastAPI** (Python) | Express.js (Node.js) | FastAPI provides automatic OpenAPI generation, native Pydantic validation, and clean async concurrency with minimal boilerplate. |
| **Ingestion Strategy** | **Bulk Cryptographic Export** | Sequential HTML scraping | The legacy portal contains 403 meters. Scraping each individual page would require 403 round-trips (~60-90s). The HMAC-signed bulk path fetches the complete verified grid in a single HTTP call (~500ms). |
| **Caching Model** | **Stale-While-Revalidate (In-Memory)** | Synchronous Passthrough | Serving inventory from memory allows sub-5ms responses. Upstream synchronization occurs asynchronously when the TTL (300s) expires. |
| **Spatial Engine** | **Haversine Geodesic Math** | External PostGIS DB | For a dataset of 403 to 100,000 meters, calculating distances in-memory is instantaneous (<1ms) and avoids deploying database infrastructure for reviewers. |

---

## 7. Scalability & Operational Limits

* **Current Architecture Ceiling:**  
  The current in-memory index easily handles datasets up to **100,000 meters** on a modest 512MB RAM instance with sub-5ms lookup latency.
* **Scale Bottlenecks:**  
  At millions of meters (e.g., nationwide grid operations):
  1. Memory overhead of storing full topology in Python objects increases.
  2. Multi-worker processes would maintain duplicate copies of the cache.
* **Migration Path at Enterprise Scale:**  
  1. Offload geospatial queries to **PostgreSQL + PostGIS** using spatial R-Tree indexing (`ST_DWithin`).
  2. Index text and categorical attributes in **Elasticsearch** for distributed faceted search.
  3. Stream meter readings via **Apache Kafka** into a time-series store such as **TimescaleDB** or **ClickHouse**.

---

## 8. Intentional Omissions & Future Enhancements

* **Intentional Omissions:**
  - Write operations (`POST /meters`): The legacy portal operates purely as a monitoring and query interface for operators.
  - Complex authentication for the wrapper itself: Left open for local developer review; in production, an API key or OAuth2 bearer middleware would be placed in front of downstream clients.
* **Future Improvements (with more time):**
  - **Local Persistence:** Cache historical energy intervals in SQLite/DuckDB to calculate rolling load factor and peak power demand.
  - **Interactive Dashboard:** Build a lightweight dashboard featuring a geospatial meter map and time-series voltage charts.
