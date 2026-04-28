from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class VehiclePayload(BaseModel):
    """Validates incoming MQTT telemetry payload from ESP32."""
    rpm: float
    throttle: float
    speed: float
    gear: float
    brake: float
    engineCoolantTemp: float
    airIntakeTemp: float
    odoMeter: float
    vehicleId: Optional[str] = "ESP32"


class VehicleDocument(VehiclePayload):
    """Document shape written to MongoDB (adds server-side timestamp)."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))