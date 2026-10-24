import math
from typing import List, Optional, Dict, Any
from app.models import MeterDetail, NearbyMeter, TransformerSummary

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c

class MeterIndex:
    def __init__(self):
        self._meters: Dict[str, MeterDetail] = {}
        self._transformers: Dict[str, TransformerSummary] = {}

    def set_meters(self, meters: List[MeterDetail]):
        self._meters = {m.meter_id: m for m in meters}

    def set_transformers(self, transformers: List[TransformerSummary]):
        self._transformers = {t.code: t for t in transformers}

    def get_meter(self, meter_id: str) -> Optional[MeterDetail]:
        return self._meters.get(meter_id)

    def total_count(self) -> int:
        return len(self._meters)

    def search_and_filter(
        self,
        q: Optional[str] = None,
        make: Optional[str] = None,
        phase_type: Optional[str] = None,
        install_status: Optional[str] = None,
        dt_code: Optional[str] = None,
        build: Optional[str] = None,
        install_type: Optional[str] = None,
        sort_by: str = "meter_id",
        sort_order: str = "asc"
    ) -> List[MeterDetail]:
        results = list(self._meters.values())

        if q:
            query = q.strip().lower()
            results = [
                m for m in results
                if query in m.meter_id.lower() or query in m.serial_no.lower()
            ]

        if make:
            m_target = make.strip().lower()
            results = [m for m in results if m.make.lower() == m_target]

        if phase_type:
            p_target = phase_type.strip().lower()
            results = [m for m in results if m.phase_type.lower() == p_target]

        if install_status:
            s_target = install_status.strip().lower()
            results = [m for m in results if m.install_status.lower() == s_target]

        if dt_code:
            d_target = dt_code.strip().lower()
            results = [m for m in results if m.dt_code and m.dt_code.lower() == d_target]

        if build:
            b_target = build.strip().lower()
            results = [m for m in results if m.build and m.build.lower() == b_target]

        if install_type:
            i_target = install_type.strip().lower()
            results = [m for m in results if m.install_type and m.install_type.lower() == i_target]

        reverse = (sort_order.lower() == "desc")
        if hasattr(MeterDetail, sort_by):
            results.sort(key=lambda x: getattr(x, sort_by) or "", reverse=reverse)
        else:
            results.sort(key=lambda x: x.meter_id, reverse=reverse)

        return results

    def find_nearby(
        self,
        target_lat: float,
        target_lng: float,
        radius_km: float = 5.0,
        limit: int = 50
    ) -> List[NearbyMeter]:
        nearby: List[NearbyMeter] = []
        for m in self._meters.values():
            if not m.geo:
                continue
            dist = haversine_km(target_lat, target_lng, m.geo.latitude, m.geo.longitude)
            if dist <= radius_km:
                nearby.append(NearbyMeter(
                    meter_id=m.meter_id,
                    serial_no=m.serial_no,
                    make=m.make,
                    phase_type=m.phase_type,
                    install_status=m.install_status,
                    dt_code=m.dt_code,
                    latitude=m.geo.latitude,
                    longitude=m.geo.longitude,
                    distance_km=round(dist, 3)
                ))
        nearby.sort(key=lambda x: x.distance_km)
        return nearby[:limit]

    def build_hierarchy_tree(self) -> Dict[str, Any]:
        tree: Dict[str, Any] = {}
        for m in self._meters.values():
            if not m.hierarchy:
                continue
            h = m.hierarchy
            z_key = h.zone.name if h.zone else "Unassigned Zone"
            c_key = h.circle.name if h.circle else "Unassigned Circle"
            d_key = h.division.name if h.division else "Unassigned Division"
            sd_key = h.subdivision.name if h.subdivision else "Unassigned Subdivision"
            ss_key = h.substation.name if h.substation else "Unassigned Substation"
            f_key = h.feeder.name if h.feeder else "Unassigned Feeder"
            dt_key = h.dt.name if h.dt else "Unassigned DT"

            curr = tree.setdefault(z_key, {})
            curr = curr.setdefault(c_key, {})
            curr = curr.setdefault(d_key, {})
            curr = curr.setdefault(sd_key, {})
            curr = curr.setdefault(ss_key, {})
            curr = curr.setdefault(f_key, {})
            dt_list = curr.setdefault(dt_key, [])
            dt_list.append({
                "meter_id": m.meter_id,
                "serial_no": m.serial_no,
                "make": m.make,
                "status": m.install_status
            })
        return tree
