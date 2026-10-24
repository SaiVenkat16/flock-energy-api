from fastapi import APIRouter, HTTPException, Path
from app.client import UrjaPortalClient
from app.cache import store
from app.analytics import (
    analyze_meter_health, analyze_transformer_load,
    MeterHealthReport, TransformerLoadSummary
)

router = APIRouter(prefix="/api/v1", tags=["Analytics"])

def get_portal_client() -> UrjaPortalClient:
    from app.main import portal_client
    return portal_client

@router.get("/meters/{meter_id}/health", response_model=MeterHealthReport)
async def get_meter_health(meter_id: str = Path(..., description="Unique meter identifier")):
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)

    meter = store.index.get_meter(meter_id)
    if not meter:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")

    try:
        cons = await client.fetch_meter_energy(meter_id)
        readings = cons.readings
    except Exception:
        readings = []

    return analyze_meter_health(meter, readings)

@router.get("/transformers/{dt_code}/summary", response_model=TransformerLoadSummary)
async def get_transformer_summary(dt_code: str = Path(..., description="DT code (e.g. DT-001)")):
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)

    dt_obj = store.index._transformers.get(dt_code)
    connected = [m for m in store.index._meters.values() if m.dt_code == dt_code]
    if not dt_obj and not connected:
        raise HTTPException(status_code=404, detail=f"Transformer '{dt_code}' not found.")

    return analyze_transformer_load(dt_obj, dt_code, connected)

@router.get("/analytics/grid-overview")
async def get_grid_overview():
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)

    all_meters = list(store.index._meters.values())
    total = len(all_meters)

    by_status = {}
    by_make = {}
    by_phase = {}
    by_dt = {}

    for m in all_meters:
        by_status[m.install_status] = by_status.get(m.install_status, 0) + 1
        by_make[m.make] = by_make.get(m.make, 0) + 1
        by_phase[m.phase_type] = by_phase.get(m.phase_type, 0) + 1
        if m.dt_code:
            by_dt[m.dt_code] = by_dt.get(m.dt_code, 0) + 1

    return {
        "total_meters": total,
        "total_distribution_transformers": len(store.index._transformers),
        "status_breakdown": by_status,
        "manufacturer_breakdown": by_make,
        "phase_breakdown": by_phase,
        "meters_per_dt": by_dt
    }
