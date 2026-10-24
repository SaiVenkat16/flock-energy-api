import math
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Path, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.client import UrjaPortalClient
from app.cache import store
from app.models import (
    MeterDetail, MeterGeo, EnergyConsumptionResponse,
    TransformerSummary, NearbyMeter, PaginatedResponse, HealthResponse
)

portal_client = UrjaPortalClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Hydrate cache from legacy portal
    try:
        await store.sync(portal_client, force=True)
    except Exception as e:
        print(f"Warning: Initial sync failed ({e}). Retrying on first request.")
    yield
    # Shutdown: Clean up client connections
    await portal_client.close()

app = FastAPI(
    title="Flock Energy — Urja Meter Ops API",
    version="1.0.0",
    description="High-performance, modern REST API proxy layer over legacy Urja Meter Ops portal.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return HealthResponse(
        status="healthy",
        portal_status="connected" if portal_client.session_token else "standby",
        cached_meters_count=store.index.total_count(),
        last_synced_at=store.last_synced_at.isoformat() if store.last_synced_at else None,
        cache_ttl_seconds=settings.CACHE_TTL_SECONDS
    )

@app.post("/api/v1/sync", tags=["System"])
async def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(store.sync, portal_client, force=True)
    return {"message": "Cache synchronization initiated in background."}

@app.get("/api/v1/meters/nearby", response_model=List[NearbyMeter], tags=["Spatial Query"])
async def get_nearby_meters(
    lat: float = Query(..., description="Target latitude in decimal degrees"),
    lng: float = Query(..., description="Target longitude in decimal degrees"),
    radius_km: float = Query(5.0, ge=0.1, le=50.0, description="Search radius in kilometers"),
    limit: int = Query(50, ge=1, le=200, description="Max meters to return")
):
    if store.is_stale:
        await store.sync(portal_client)
    return store.index.find_nearby(target_lat=lat, target_lng=lng, radius_km=radius_km, limit=limit)

@app.get("/api/v1/meters", response_model=PaginatedResponse[MeterDetail], tags=["Meters"])
async def list_meters(
    q: Optional[str] = Query(None, description="Search meter ID or serial number"),
    make: Optional[str] = Query(None, description="Filter by manufacturer (HPL, Genus, etc.)"),
    phase_type: Optional[str] = Query(None, description="Filter by phase (single, three)"),
    install_status: Optional[str] = Query(None, description="Filter status (Installed, Faulty, Decommissioned)"),
    dt_code: Optional[str] = Query(None, description="Filter by Distribution Transformer code"),
    build: Optional[str] = Query(None, description="Filter by build variant (legacy, v2)"),
    install_type: Optional[str] = Query(None, description="Filter by install type (Whole Current, CT Operated)"),
    sort_by: str = Query("meter_id", description="Field to sort by"),
    sort_order: str = Query("asc", description="Sort direction (asc, desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    if store.is_stale:
        await store.sync(portal_client)

    filtered = store.index.search_and_filter(
        q=q, make=make, phase_type=phase_type, install_status=install_status,
        dt_code=dt_code, build=build, install_type=install_type,
        sort_by=sort_by, sort_order=sort_order
    )
    total = len(filtered)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    page_data = filtered[start : start + page_size]

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        data=page_data
    )

@app.get("/api/v1/meters/{meter_id}", response_model=MeterDetail, tags=["Meters"])
async def get_meter_detail(
    meter_id: str = Path(..., description="Unique meter identifier (e.g. J100000)")
):
    if store.is_stale:
        await store.sync(portal_client)

    meter = store.index.get_meter(meter_id)
    if not meter:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")
    return meter

@app.get("/api/v1/meters/{meter_id}/geo", response_model=MeterGeo, tags=["Meters"])
async def get_meter_geo(
    meter_id: str = Path(..., description="Unique meter identifier")
):
    meter = store.index.get_meter(meter_id)
    if meter and meter.geo:
        return meter.geo
    try:
        return await portal_client.fetch_meter_geo(meter_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream portal error: {str(e)}")

@app.get("/api/v1/meters/{meter_id}/consumption", response_model=EnergyConsumptionResponse, tags=["Meters"])
async def get_meter_consumption(
    meter_id: str = Path(..., description="Unique meter identifier")
):
    try:
        return await portal_client.fetch_meter_energy(meter_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream portal error: {str(e)}")

@app.get("/api/v1/transformers", response_model=PaginatedResponse[TransformerSummary], tags=["Transformers"])
async def list_transformers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    if store.is_stale:
        await store.sync(portal_client)

    all_t = list(store.index._transformers.values())
    total = len(all_t)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    page_data = all_t[start : start + page_size]

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        data=page_data
    )

@app.get("/api/v1/hierarchy", tags=["Hierarchy"])
async def get_network_hierarchy():
    if store.is_stale:
        await store.sync(portal_client)
    return store.index.build_hierarchy_tree()
