import hmac
import hashlib
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.models import (
    MeterDetail, MeterSummary, MeterGeo, MeterHierarchy, HierarchyNode,
    EnergyReading, EnergyConsumptionResponse, TransformerSummary
)

class UrjaPortalClient:
    def __init__(self, base_url: str = settings.PORTAL_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            follow_redirects=False
        )
        self.session_token: Optional[str] = None
        self.last_login_time: float = 0.0

    async def close(self):
        await self.client.aclose()

    async def login(self) -> bool:
        login_url = f"{self.base_url}/login"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": login_url,
            "User-Agent": "Urja-REST-Adapter/1.0"
        }
        data = {
            "email": settings.PORTAL_USERNAME,
            "password": settings.PORTAL_PASSWORD
        }
        
        response = await self.client.post("/login", data=data, headers=headers)
        if response.status_code in (200, 303):
            cookie_val = response.cookies.get("__Secure-better-auth.session_token")
            if cookie_val:
                self.session_token = cookie_val
                self.last_login_time = time.time()
                return True
        return False

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if not self.session_token:
            await self.login()
            
        resp = await self.client.request(method, path, **kwargs)
        if resp.status_code == 401:
            await self.login()
            resp = await self.client.request(method, path, **kwargs)
        return resp

    async def fetch_portal_keys(self) -> str:
        resp = await self._request("GET", "/portal/keys")
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["signingSecret"]

    async def fetch_bulk_export(self) -> List[MeterDetail]:
        secret = await self.fetch_portal_keys()
        timestamp = str(int(time.time()))
        query = "page=1"
        canonical = f"GET\n/portal/export\n{query}\n{timestamp}"
        signature = hmac.new(
            secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "x-timestamp": timestamp,
            "x-signature": signature
        }
        resp = await self._request("GET", f"/portal/export?{query}", headers=headers)
        resp.raise_for_status()
        payload = resp.json()
        raw_items = payload.get("data", [])
        
        normalized: List[MeterDetail] = []
        for item in raw_items:
            geo_data = item.get("geo")
            geo_obj = None
            if geo_data and geo_data.get("lat") is not None and geo_data.get("lng") is not None:
                geo_obj = MeterGeo(latitude=float(geo_data["lat"]), longitude=float(geo_data["lng"]))
                
            hier_data = item.get("hierarchy", {})
            hier_obj = MeterHierarchy(
                zone=HierarchyNode(**hier_data["zone"]) if hier_data.get("zone") else None,
                circle=HierarchyNode(**hier_data["circle"]) if hier_data.get("circle") else None,
                division=HierarchyNode(**hier_data["division"]) if hier_data.get("division") else None,
                subdivision=HierarchyNode(**hier_data["subdivision"]) if hier_data.get("subdivision") else None,
                substation=HierarchyNode(**hier_data["substation"]) if hier_data.get("substation") else None,
                feeder=HierarchyNode(**hier_data["feeder"]) if hier_data.get("feeder") else None,
                dt=HierarchyNode(**hier_data["dt"]) if hier_data.get("dt") else None,
            ) if hier_data else None

            normalized.append(MeterDetail(
                meter_id=item["meterId"],
                serial_no=item["serialNo"],
                make=item["make"],
                phase_type=item["phaseType"],
                install_status=item["installStatus"],
                install_type=item.get("installType"),
                build=item.get("build"),
                dt_code=item.get("dtCode"),
                geo=geo_obj,
                hierarchy=hier_obj
            ))
        return normalized

    async def fetch_transformers(self, page: int = 1) -> Dict[str, Any]:
        resp = await self._request("GET", f"/portal/dts?page={page}")
        resp.raise_for_status()
        data = resp.json()
        transformers = [
            TransformerSummary(
                code=d["code"],
                name=d["name"],
                feeder_code=d["feederCode"],
                capacity_kva=d["capacityKva"]
            )
            for d in data.get("data", [])
        ]
        return {"total": data.get("total", len(transformers)), "data": transformers}

    async def fetch_all_transformers(self) -> List[TransformerSummary]:
        page1 = await self.fetch_transformers(page=1)
        total = page1["total"]
        items = page1["data"]
        current = len(items)
        page = 2
        while current < total:
            next_page = await self.fetch_transformers(page=page)
            if not next_page["data"]:
                break
            items.extend(next_page["data"])
            current += len(next_page["data"])
            page += 1
        return items

    async def fetch_meter_energy(self, meter_id: str) -> EnergyConsumptionResponse:
        resp = await self._request("GET", f"/portal/meters/{meter_id}/energy")
        if resp.status_code == 404:
            raise KeyError(f"Meter {meter_id} not found")
        resp.raise_for_status()
        
        raw_readings = resp.json().get("data", [])
        normalized_readings: List[EnergyReading] = []
        voltages: List[float] = []
        kwh_values: List[float] = []

        for r in raw_readings:
            raw_ts = r.get("timestamp", "")
            iso_ts = raw_ts
            try:
                dt = datetime.strptime(raw_ts, "%d/%m/%Y %H:%M")
                iso_ts = dt.isoformat()
            except Exception:
                pass

            def parse_float(val: Any) -> Optional[float]:
                if val is None:
                    return None
                val_str = str(val).strip().replace("—", "").replace("-", "")
                if not val_str:
                    return None
                try:
                    return float(val_str)
                except ValueError:
                    return None

            kwh_val = parse_float(r.get("kwh"))
            kvah_val = parse_float(r.get("kvah"))
            volt_val = parse_float(r.get("voltR"))

            if volt_val is not None:
                voltages.append(volt_val)
            if kwh_val is not None:
                kwh_values.append(kwh_val)

            normalized_readings.append(EnergyReading(
                timestamp=iso_ts,
                raw_timestamp=raw_ts,
                kwh=kwh_val,
                kvah=kvah_val,
                volt_r=volt_val
            ))

        return EnergyConsumptionResponse(
            meter_id=meter_id,
            total_readings=len(normalized_readings),
            readings=normalized_readings,
            min_voltage_v=min(voltages) if voltages else None,
            max_voltage_v=max(voltages) if voltages else None,
            latest_kwh=kwh_values[-1] if kwh_values else None
        )

    async def fetch_meter_geo(self, meter_id: str) -> MeterGeo:
        resp = await self._request("GET", f"/portal/meters/{meter_id}/geo")
        if resp.status_code == 404:
            raise KeyError(f"Meter {meter_id} not found")
        resp.raise_for_status()
        geo_dict = resp.json().get("data", {})
        return MeterGeo(
            latitude=float(geo_dict.get("latitude", 0.0)),
            longitude=float(geo_dict.get("longitude", 0.0))
        )
