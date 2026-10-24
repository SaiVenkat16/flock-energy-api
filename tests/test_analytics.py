import pytest
from app.models import MeterDetail, MeterGeo, EnergyReading, TransformerSummary
from app.analytics import analyze_meter_health, analyze_transformer_load
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_analyze_meter_health_optimal():
    m = MeterDetail(
        meter_id="J100000",
        serial_no="SN001",
        make="HPL",
        phase_type="single",
        install_status="Installed"
    )
    readings = [
        EnergyReading(timestamp="2026-06-24T00:00:00", kwh=10.5, volt_r=228.0),
        EnergyReading(timestamp="2026-06-24T00:30:00", kwh=11.0, volt_r=230.0)
    ]
    report = analyze_meter_health(m, readings)
    assert report.health_score >= 90
    assert report.status_level == "OPTIMAL"
    assert report.voltage_anomalies_count == 0

def test_analyze_meter_health_faulty_undervoltage():
    m = MeterDetail(
        meter_id="J100001",
        serial_no="SN002",
        make="Genus",
        phase_type="single",
        install_status="Faulty"
    )
    readings = [
        EnergyReading(timestamp="2026-06-24T00:00:00", kwh=10.5, volt_r=198.0),  # Under-voltage
        EnergyReading(timestamp="2026-06-24T00:30:00", kwh=11.0, volt_r=202.0)
    ]
    report = analyze_meter_health(m, readings)
    assert report.health_score < 60
    assert report.status_level in ("WARNING", "CRITICAL")
    assert report.voltage_anomalies_count == 2

def test_analyze_transformer_load_risk():
    dt = TransformerSummary(code="DT-001", name="Test DT", feeder_code="F-1", capacity_kva=100)
    meters = [
        MeterDetail(meter_id=f"M{i}", serial_no=f"S{i}", make="HPL", phase_type="single", install_status="Faulty", dt_code="DT-001")
        for i in range(10)
    ]
    summary = analyze_transformer_load(dt, "DT-001", meters)
    assert summary.grid_risk_level == "HIGH"
    assert summary.fault_ratio_percent == 100.0

def test_export_csv_endpoint():
    resp = client.get("/api/v1/meters/export/csv?make=HPL")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Meter ID,Serial Number,Make" in resp.text
    assert "HPL" in resp.text

def test_grid_overview_endpoint():
    resp = client.get("/api/v1/analytics/grid-overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_meters" in data
    assert "status_breakdown" in data
