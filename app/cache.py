import asyncio
import time
from datetime import datetime, timezone
from typing import Optional
from app.config import settings
from app.client import UrjaPortalClient
from app.indexer import MeterIndex

class DataStore:
    def __init__(self):
        self.index = MeterIndex()
        self.last_synced_at: Optional[datetime] = None
        self._sync_lock = asyncio.Lock()
        self._last_sync_timestamp: float = 0.0

    @property
    def is_stale(self) -> bool:
        if not self.last_synced_at:
            return True
        return (time.time() - self._last_sync_timestamp) > settings.CACHE_TTL_SECONDS

    async def sync(self, client: UrjaPortalClient, force: bool = False) -> bool:
        if not force and not self.is_stale and self.index.total_count() > 0:
            return False

        async with self._sync_lock:
            # Recheck inside lock
            if not force and not self.is_stale and self.index.total_count() > 0:
                return False

            meters = await client.fetch_bulk_export()
            transformers = await client.fetch_all_transformers()
            self.index.set_meters(meters)
            self.index.set_transformers(transformers)
            self.last_synced_at = datetime.now(timezone.utc)
            self._last_sync_timestamp = time.time()
            return True

store = DataStore()
