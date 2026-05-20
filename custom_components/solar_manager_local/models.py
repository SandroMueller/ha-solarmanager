"""Data models for the Solar Manager local API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeviceData:
    """Parsed device entry from the devices array in /v2/point."""

    device_id: str
    power: float
    soc: float | None
    signal: str
    temperature: float | None
    active_device: int | None
    import_energy_wh: float
    export_energy_wh: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceData:
        soc = data.get("soc")
        temp = data.get("temperature")
        active = data.get("activeDevice")
        return cls(
            device_id=str(data.get("_id", "")),
            power=float(data.get("power", 0)),
            soc=float(soc) if soc is not None else None,
            signal=str(data.get("signal", "unknown")),
            temperature=float(temp) if temp is not None else None,
            active_device=int(active) if active is not None else None,
            import_energy_wh=float(data.get("iWh", 0)),
            export_energy_wh=float(data.get("eWh", 0)),
        )


@dataclass(frozen=True)
class PointData:
    """Parsed response from GET /v2/point."""

    production_power_w: float
    consumption_power_w: float
    interval_production_wh: float
    timestamp: str
    devices: list[DeviceData] = field(default_factory=lambda: [])
    raw: dict[str, Any] = field(default_factory=lambda: {})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PointData:
        devices_raw: list[Any] = data.get("devices", [])
        devices = [
            DeviceData.from_dict(d)  # pyright: ignore[reportUnknownArgumentType]
            for d in devices_raw
            if isinstance(d, dict)
        ]
        return cls(
            production_power_w=float(data.get("pW", 0)),
            consumption_power_w=float(data.get("cW", 0)),
            interval_production_wh=float(data.get("pWh", 0)),
            timestamp=str(data.get("t", "")),
            devices=devices,
            raw=data,
        )
