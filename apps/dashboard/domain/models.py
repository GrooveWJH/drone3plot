"""Domain models shared across services, API, and sockets."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Position(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    relative_altitude: Optional[float] = None


class Speed(BaseModel):
    horizontal: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


class BatteryStatus(BaseModel):
    percent: Optional[int] = None


class GimbalState(BaseModel):
    pitch: Optional[float] = None
    roll: Optional[float] = None
    yaw: Optional[float] = None


class CameraState(BaseModel):
    payload_index: Optional[str] = None
    lens_type: str = "zoom"
    zoom_factor: Optional[float] = None
    gimbal: GimbalState = Field(default_factory=GimbalState)


class FlightState(BaseModel):
    mode_code: Optional[int] = None
    mode_label: str = "未知"


class ConnectionState(BaseModel):
    osd_frequency: Optional[float] = None
    is_online: bool = True


class TelemetrySnapshot(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    position: Position = Field(default_factory=Position)
    speed: Speed = Field(default_factory=Speed)
    battery: BatteryStatus = Field(default_factory=BatteryStatus)
    camera: CameraState = Field(default_factory=CameraState)
    flight: FlightState = Field(default_factory=FlightState)
    connection: ConnectionState = Field(default_factory=ConnectionState)


class StickCommand(BaseModel):
    roll: float = Field(0.0, ge=-1.0, le=1.0)
    pitch: float = Field(0.0, ge=-1.0, le=1.0)
    yaw: float = Field(0.0, ge=-1.0, le=1.0)
    throttle: float = Field(0.0, ge=-1.0, le=1.0)

    @field_validator("roll", "pitch", "yaw", "throttle", mode="before")
    @classmethod
    def _coerce(cls, value: float) -> float:
        if isinstance(value, str):
            return float(value)
        return value


class ZoomCommand(BaseModel):
    zoom_factor: float = Field(..., gt=0)
    camera_type: str = Field("zoom")

    @field_validator("camera_type")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return value.lower()
