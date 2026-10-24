import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.cache import store
from app.models import MeterDetail, MeterGeo, MeterHierarchy, HierarchyNode, TransformerSummary

@pytest.fixture(autouse=True)
def seed_store():
    store.index.set_meters([
        MeterDetail(
            meter_id="J100000",
            serial_no="SE33962",
            make="HPL",
            phase_type="single",
            install_status="Decommissioned",
            build="legacy",
            dt_code="DT-001",
            geo=MeterGeo(latitude=26.9389, longitude=75.8309),
            hierarchy=MeterHierarchy(
                zone=HierarchyNode(name="Jaipur Zone 1", code="Z-01"),
                circle=HierarchyNode(name="Circle 1", code="C-01"),
                division=HierarchyNode(name="Division 1", code="D-01"),
                subdivision=HierarchyNode(name="Subdivision 1", code="SD-01"),
                substation=HierarchyNode(name="Substation 1", code="SS-01"),
                feeder=HierarchyNode(name="Feeder 1", code="F-001"),
                dt=HierarchyNode(name="Malviya Nagar DT 1", code="DT-001")
            )
        ),
        MeterDetail(
            meter_id="J100004",
            serial_no="SE65293",
            make="Genus",
            phase_type="single",
            install_status="Faulty",
            build="v2",
            dt_code="DT-005",
            geo=MeterGeo(latitude=26.9124, longitude=75.7873)
        )
    ])
    store.index.set_transformers([
        TransformerSummary(
            code="DT-001",
            name="Malviya Nagar DT 1",
            feeder_code="F-001",
            capacity_kva=100
        )
    ])

client = TestClient(app)

def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["cached_meters_count"] >= 2

def test_list_meters_pagination_and_filter():
    resp = client.get("/api/v1/meters?make=HPL")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["data"][0]["make"] == "HPL"

def test_get_meter_by_id():
    resp = client.get("/api/v1/meters/J100000")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meter_id"] == "J100000"
    assert data["serial_no"] == "SE33962"
    assert data["hierarchy"]["zone"]["name"] == "Jaipur Zone 1"

def test_get_meter_not_found():
    resp = client.get("/api/v1/meters/NON_EXISTENT")
    assert resp.status_code == 404

def test_spatial_nearby_query():
    # Coords close to J100000 (26.9389, 75.8309)
    resp = client.get("/api/v1/meters/nearby?lat=26.938&lng=75.830&radius_km=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["meter_id"] == "J100000"
    assert data[0]["distance_km"] < 2.0

def test_transformers_endpoint():
    resp = client.get("/api/v1/transformers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["data"][0]["code"] == "DT-001"

def test_hierarchy_tree_endpoint():
    resp = client.get("/api/v1/hierarchy")
    assert resp.status_code == 200
    data = resp.json()
    assert "Jaipur Zone 1" in data

def test_dashboard_endpoint():
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Urja Smart Meter Ops Dashboard" in resp.text
