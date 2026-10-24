import math
from fastapi import APIRouter, Query
from app.client import UrjaPortalClient
from app.cache import store
from app.models import TransformerSummary, PaginatedResponse

router = APIRouter(prefix="/api/v1", tags=["Transformers & Hierarchy"])

def get_portal_client() -> UrjaPortalClient:
    from app.main import portal_client
    return portal_client

@router.get("/transformers", response_model=PaginatedResponse[TransformerSummary], tags=["Transformers"])
async def list_transformers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)

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

@router.get("/hierarchy", tags=["Hierarchy"])
async def get_network_hierarchy():
    client = get_portal_client()
    if store.is_stale:
        await store.sync(client)
    return store.index.build_hierarchy_tree()
