from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.client import UrjaPortalClient
from app.cache import store
from app.dashboard import DASHBOARD_HTML
from app.models import HealthResponse
from app.routers.meters import router as meters_router
from app.routers.transformers import router as transformers_router
from app.routers.analytics import router as analytics_router

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

# Mount Modular Domain Routers
app.include_router(meters_router)
app.include_router(transformers_router)
app.include_router(analytics_router)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def serve_dashboard():
    return DASHBOARD_HTML

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
