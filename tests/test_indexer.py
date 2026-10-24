import pytest
from app.indexer import MeterIndex, haversine_km
from app.models import MeterDetail, MeterGeo, MeterHierarchy, HierarchyNode, TransformerSummary

@pytest.fixture
def sample_meters():
    return [
        MeterDetail(
            meter_id="M1",
            serial_no="SN001",
            make="HPL",
            phase_type="single",
            install_status="Installed",
            build="legacy",
            dt_code="DT-01",
            geo=MeterGeo(latitude=26.90, longitude=75.80),
            hierarchy=MeterHierarchy(
                zone=HierarchyNode(name="Zone 1", code="Z1"),
                circle=HierarchyNode(name="Circle 1", code="C1"),
                division=HierarchyNode(name="Div 1", code="D1"),
                subdivision=HierarchyNode(name="SubDiv 1", code="SD1"),
                substation=HierarchyNode(name="SS 1", code="SS1"),
                feeder=HierarchyNode(name="F 1", code="F1"),
                dt=HierarchyNode(name="DT 1", code="DT-01")
            )
        ),
        MeterDetail(
            meter_id="M2",
            serial_no="SN002",
            make="Genus",
            phase_type="three",
            install_status="Faulty",
            build="v2",
            dt_code="DT-02",
            geo=MeterGeo(latitude=26.92, longitude=75.82)
        ),
        MeterDetail(
            meter_id="M3",
            serial_no="SN003",
            make="HPL",
            phase_type="three",
            install_status="Decommissioned",
            build="v2",
            dt_code="DT-01",
            geo=MeterGeo(latitude=28.50, longitude=77.20)
        ),
    ]

def test_haversine_calculation():
    # Jaipur ~ 26.91, 75.81 to Jaipur airport ~ 26.82, 75.80 is approx 10 km
    dist = haversine_km(26.91, 75.81, 26.82, 75.80)
    assert 9.0 <= dist <= 11.0

def test_indexer_filtering(sample_meters):
    index = MeterIndex()
    index.set_meters(sample_meters)

    # Filter by make
    hpl = index.search_and_filter(make="HPL")
    assert len(hpl) == 2

    # Filter by phase
    three_phase = index.search_and_filter(phase_type="three")
    assert len(three_phase) == 2

    # Search by serial substring
    sn2 = index.search_and_filter(q="002")
    assert len(sn2) == 1
    assert sn2[0].meter_id == "M2"

    # Multi-attribute filter
    hpl_faulty = index.search_and_filter(make="HPL", install_status="Faulty")
    assert len(hpl_faulty) == 0

def test_spatial_proximity(sample_meters):
    index = MeterIndex()
    index.set_meters(sample_meters)

    # Search near Jaipur coords (26.91, 75.81) with 10 km radius
    nearby = index.find_nearby(26.91, 75.81, radius_km=10.0)
    assert len(nearby) == 2
    # M3 is in Delhi, should not be included
    assert "M3" not in [m.meter_id for m in nearby]

def test_hierarchy_tree(sample_meters):
    index = MeterIndex()
    index.set_meters(sample_meters)
    tree = index.build_hierarchy_tree()

    assert "Zone 1" in tree
    assert "Circle 1" in tree["Zone 1"]
