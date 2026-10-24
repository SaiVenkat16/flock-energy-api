from typing import List, Optional, Generic, TypeVar, Dict, Any
from pydantic import BaseModel, Field

T = TypeVar("T")

class HierarchyNode(BaseModel):
    name: str = Field(..., description="Name of the grid level entity")
    code: str = Field(..., description="Unique alphanumeric identifier")

class MeterHierarchy(BaseModel):
    zone: Optional[HierarchyNode] = None
    circle: Optional[HierarchyNode] = None
    division: Optional[HierarchyNode] = None
    subdivision: Optional[HierarchyNode] = None
    substation: Optional[HierarchyNode] = None
    feeder: Optional[HierarchyNode] = None
    dt: Optional[HierarchyNode] = None

class MeterGeo(BaseModel):
    latitude: float = Field(..., description="Geographic latitude in decimal degrees")
    longitude: float = Field(..., description="Geographic longitude in decimal degrees")

class MeterSummary(BaseModel):
    meter_id: str = Field(..., description="Unique meter identifier")
    serial_no: str = Field(..., description="Manufacturer serial number")
    make: str = Field(..., description="Meter manufacturer (e.g. HPL, Genus, Secure, L&T, Allied)")
    phase_type: str = Field(..., description="single or three phase")
    install_status: str = Field(..., description="Installed, Faulty, or Decommissioned")
    install_type: Optional[str] = Field(None, description="Whole Current or CT Operated")
    build: Optional[str] = Field(None, description="legacy or v2 build type")
    dt_code: Optional[str] = Field(None, description="Associated Distribution Transformer code")

class MeterDetail(MeterSummary):
    hierarchy: Optional[MeterHierarchy] = None
    geo: Optional[MeterGeo] = None

class EnergyReading(BaseModel):
    timestamp: str = Field(..., description="Normalized ISO-8601 reading timestamp")
    raw_timestamp: Optional[str] = Field(None, description="Original portal timestamp format")
    kwh: Optional[float] = Field(None, description="Active energy consumed in kWh")
    kvah: Optional[float] = Field(None, description="Apparent energy in kVAh")
    volt_r: Optional[float] = Field(None, description="R-Phase voltage in Volts")

class EnergyConsumptionResponse(BaseModel):
    meter_id: str
    total_readings: int
    readings: List[EnergyReading]
    min_voltage_v: Optional[float] = None
    max_voltage_v: Optional[float] = None
    latest_kwh: Optional[float] = None

class TransformerSummary(BaseModel):
    code: str
    name: str
    feeder_code: str
    capacity_kva: int

class NearbyMeter(BaseModel):
    meter_id: str
    serial_no: str
    make: str
    phase_type: str
    install_status: str
    dt_code: Optional[str] = None
    latitude: float
    longitude: float
    distance_km: float

class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[T]

class HealthResponse(BaseModel):
    status: str
    portal_status: str
    cached_meters_count: int
    last_synced_at: Optional[str] = None
    cache_ttl_seconds: int
