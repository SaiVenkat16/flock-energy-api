import io
import csv
import math
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Path, Response
from app.client import UrjaPortalClient
from app.cache import store
from app.models import (
    MeterDetail, MeterGeo, EnergyConsumptionResponse,
    NearbyMeter, PaginatedResponse
)

router = APIRouter(prefix="/api/v1/meters", tags=["Meters"])

def get_portal_client() -> UrjaPortalClient:
    from app.main import portal_client
    return portal_client

@router.get("", response_model=PaginatedResponse[MeterDetail])
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
    page_size: int = Query(20, ge=1, le=500, description="Items per page")
):
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)

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

@router.get("/nearby", response_model=List[NearbyMeter], tags=["Spatial Query"])
async def get_nearby_meters(
    lat: float = Query(..., description="Target latitude in decimal degrees"),
    lng: float = Query(..., description="Target longitude in decimal degrees"),
    radius_km: float = Query(5.0, ge=0.1, le=50.0, description="Search radius in kilometers"),
    limit: int = Query(50, ge=1, le=200, description="Max meters to return")
):
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)
    return store.index.find_nearby(target_lat=lat, target_lng=lng, radius_km=radius_km, limit=limit)

@router.get("/map-pins")
async def get_meter_map_pins():
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)
    return [
        {
            "meter_id": m.meter_id,
            "serial_no": m.serial_no,
            "make": m.make,
            "phase_type": m.phase_type,
            "status": m.install_status,
            "dt_code": m.dt_code,
            "lat": m.geo.latitude,
            "lng": m.geo.longitude
        }
        for m in store.index._meters.values()
        if m.geo and m.geo.latitude and m.geo.longitude
    ]

@router.get("/export/csv")
async def export_meters_csv(
    q: Optional[str] = Query(None),
    make: Optional[str] = Query(None),
    phase_type: Optional[str] = Query(None),
    install_status: Optional[str] = Query(None),
    dt_code: Optional[str] = Query(None)
):
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)

    meters = store.index.search_and_filter(
        q=q, make=make, phase_type=phase_type,
        install_status=install_status, dt_code=dt_code
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Meter ID", "Serial Number", "Make", "Phase", "Status",
        "DT Code", "Build", "Latitude", "Longitude", "Zone", "Circle", "Feeder"
    ])

    for m in meters:
        lat = m.geo.latitude if m.geo else ""
        lng = m.geo.longitude if m.geo else ""
        z = m.hierarchy.zone.name if m.hierarchy and m.hierarchy.zone else ""
        c = m.hierarchy.circle.name if m.hierarchy and m.hierarchy.circle else ""
        f = m.hierarchy.feeder.name if m.hierarchy and m.hierarchy.feeder else ""
        writer.writerow([
            m.meter_id, m.serial_no, m.make, m.phase_type, m.install_status,
            m.dt_code or "", m.build or "", lat, lng, z, c, f
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=urja-meters-export.csv"}
    )

@router.get("/{meter_id}", response_model=MeterDetail)
async def get_meter_detail(
    meter_id: str = Path(..., description="Unique meter identifier (e.g. J100000)")
):
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)

    meter = store.index.get_meter(meter_id)
    if not meter:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")
    return meter

@router.get("/{meter_id}/geo", response_model=MeterGeo)
async def get_meter_geo(
    meter_id: str = Path(..., description="Unique meter identifier")
):
    meter = store.index.get_meter(meter_id)
    if meter and meter.geo:
        return meter.geo
    client = get_portal_client()
    try:
        return await client.fetch_meter_geo(meter_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream portal error: {str(e)}")

@router.get("/{meter_id}/consumption", response_model=EnergyConsumptionResponse)
async def get_meter_consumption(
    meter_id: str = Path(..., description="Unique meter identifier")
):
    client = get_portal_client()
    try:
        return await client.fetch_meter_energy(meter_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream portal error: {str(e)}")
