from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.models import EnergyReading, MeterDetail, TransformerSummary

class MeterHealthReport(BaseModel):
    meter_id: str
    health_score: int = Field(..., ge=0, le=100, description="Overall health score 0-100")
    status_level: str = Field(..., description="OPTIMAL, WARNING, or CRITICAL")
    nominal_voltage_v: float = 230.0
    voltage_anomalies_count: int
    min_voltage_v: Optional[float] = None
    max_voltage_v: Optional[float] = None
    avg_voltage_v: Optional[float] = None
    recommendations: List[str]

class TransformerLoadSummary(BaseModel):
    dt_code: str
    dt_name: Optional[str] = None
    capacity_kva: Optional[int] = None
    feeder_code: Optional[str] = None
    connected_meters_count: int
    installed_meters_count: int
    faulty_meters_count: int
    decommissioned_meters_count: int
    fault_ratio_percent: float
    grid_risk_level: str = Field(..., description="LOW, MODERATE, or HIGH")
    recommended_action: str

def analyze_meter_health(meter: MeterDetail, readings: List[EnergyReading]) -> MeterHealthReport:
    recommendations = []
    
    if meter.install_status.lower() == "decommissioned":
        return MeterHealthReport(
            meter_id=meter.meter_id,
            health_score=0,
            status_level="CRITICAL",
            voltage_anomalies_count=0,
            recommendations=["Meter decommissioned. Physical removal or asset retirement required."]
        )

    valid_volts = [r.volt_r for r in readings if r.volt_r is not None]
    anomalies = 0
    score = 100

    if meter.install_status.lower() == "faulty":
        score -= 40
        recommendations.append("Flagged as Faulty in utility registry: field crew dispatch required.")

    if valid_volts:
        min_v = min(valid_volts)
        max_v = max(valid_volts)
        avg_v = round(sum(valid_volts) / len(valid_volts), 1)

        # Standard Indian Grid Code allowable limits: 230V +/- 6% (216V - 244V)
        for v in valid_volts:
            if v < 216.0 or v > 244.0:
                anomalies += 1

        if anomalies > 0:
            deduction = min(35, anomalies * 5)
            score -= deduction
            if min_v < 210.0:
                recommendations.append(f"Severe under-voltage detected (min {min_v}V). Risk of consumer appliance stalling.")
            if max_v > 248.0:
                recommendations.append(f"Severe over-voltage surge detected (max {max_v}V). Risk of insulation breakdown.")
    else:
        min_v, max_v, avg_v = None, None, None
        score -= 10
        recommendations.append("No recent voltage telemetry captured in current window.")

    final_score = max(0, min(100, score))
    if final_score >= 80:
        level = "OPTIMAL"
    elif final_score >= 50:
        level = "WARNING"
    else:
        level = "CRITICAL"

    if not recommendations:
        recommendations.append("All voltage parameters within statutory limits.")

    return MeterHealthReport(
        meter_id=meter.meter_id,
        health_score=final_score,
        status_level=level,
        voltage_anomalies_count=anomalies,
        min_voltage_v=min_v,
        max_voltage_v=max_v,
        avg_voltage_v=avg_v,
        recommendations=recommendations
    )

def analyze_transformer_load(
    dt: Optional[TransformerSummary],
    dt_code: str,
    connected_meters: List[MeterDetail]
) -> TransformerLoadSummary:
    total = len(connected_meters)
    installed = sum(1 for m in connected_meters if m.install_status.lower() == "installed")
    faulty = sum(1 for m in connected_meters if m.install_status.lower() == "faulty")
    decom = sum(1 for m in connected_meters if m.install_status.lower() == "decommissioned")

    fault_ratio = round((faulty / total * 100), 1) if total > 0 else 0.0

    if fault_ratio >= 30.0 or faulty >= 5:
        risk = "HIGH"
        action = "High cluster of faulty meters detected on this DT. Schedule immediate transformer feeder patrol."
    elif fault_ratio >= 15.0 or total > 25:
        risk = "MODERATE"
        action = "Moderate failure rate or high meter concentration. Monitor load balance."
    else:
        risk = "LOW"
        action = "Transformer operating within normal operational and meter health bounds."

    return TransformerLoadSummary(
        dt_code=dt_code,
        dt_name=dt.name if dt else None,
        capacity_kva=dt.capacity_kva if dt else None,
        feeder_code=dt.feeder_code if dt else None,
        connected_meters_count=total,
        installed_meters_count=installed,
        faulty_meters_count=faulty,
        decommissioned_meters_count=decom,
        fault_ratio_percent=fault_ratio,
        grid_risk_level=risk,
        recommended_action=action
    )
