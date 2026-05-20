from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import SolarManagerDataCoordinator
from .models import DeviceData, PointData


@dataclass(frozen=True, kw_only=True)
class SolarManagerSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[PointData, SolarManagerDataCoordinator], float | None]


SENSOR_DESCRIPTIONS: tuple[SolarManagerSensorEntityDescription, ...] = (
    SolarManagerSensorEntityDescription(
        key="pv_production_power",
        name="PV production power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda pt, _coord: pt.production_power_w,
    ),
    SolarManagerSensorEntityDescription(
        key="home_consumption_power",
        name="Home consumption power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda pt, _coord: pt.consumption_power_w,
    ),
    SolarManagerSensorEntityDescription(
        key="pv_energy_produced_total",
        name="PV energy produced total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda _pt, coord: coord.produced_energy_kwh,
    ),
)


# ── Per-device sensor descriptions ──────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class SolarManagerDeviceSensorDescription(SensorEntityDescription):
    """Description for a sensor derived from a single Solar Manager device."""

    value_fn: Callable[[DeviceData], float | str | None]


DEVICE_SENSOR_DESCRIPTIONS: tuple[SolarManagerDeviceSensorDescription, ...] = (
    SolarManagerDeviceSensorDescription(
        key="power",
        translation_key="device_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.power,
    ),
    SolarManagerDeviceSensorDescription(
        key="soc",
        translation_key="device_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.soc,
    ),
    SolarManagerDeviceSensorDescription(
        key="temperature",
        translation_key="device_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: d.temperature,
    ),
    SolarManagerDeviceSensorDescription(
        key="signal",
        translation_key="device_signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.signal,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SolarManagerDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    # ── Gateway-level sensors ───────────────────────────────────────
    for description in SENSOR_DESCRIPTIONS:
        if description.key == "pv_energy_produced_total":
            entities.append(
                SolarManagerAccumulatedEnergySensor(coordinator, entry, description)
            )
        else:
            entities.append(SolarManagerSensor(coordinator, entry, description))

    # ── Per-device sensors ──────────────────────────────────────────
    for device in coordinator.data.devices:
        for desc in DEVICE_SENSOR_DESCRIPTIONS:
            # Skip state-of-charge sensor for devices that don't report it.
            if desc.key == "soc" and device.soc is None:
                continue
            # Skip temperature sensor for devices that don't report it.
            if desc.key == "temperature" and device.temperature is None:
                continue
            entities.append(
                SolarManagerDeviceSensor(coordinator, entry, desc, device.device_id)
            )

    async_add_entities(entities)


class SolarManagerSensor(CoordinatorEntity[SolarManagerDataCoordinator], SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    def __init__(
        self,
        coordinator: SolarManagerDataCoordinator,
        entry: ConfigEntry,
        description: SolarManagerSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": "Solar Manager",
        }
        self._attr_has_entity_name = True
        self._value_fn = description.value_fn

    def _handle_coordinator_update(self) -> None:
        value = self._value_fn(self.coordinator.data, self.coordinator)
        if value is not None:
            self._attr_native_value = float(value)
        else:
            self._attr_native_value = None
        super()._handle_coordinator_update()


class SolarManagerAccumulatedEnergySensor(SolarManagerSensor, RestoreSensor):  # pyright: ignore[reportIncompatibleVariableOverride]
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        try:
            restored_value = float(last_state.state)
        except (TypeError, ValueError):
            return

        self.coordinator.set_initial_produced_energy_kwh(restored_value)


class SolarManagerDeviceSensor(CoordinatorEntity[SolarManagerDataCoordinator], SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Sensor entity for a single device reported by the Solar Manager."""

    def __init__(
        self,
        coordinator: SolarManagerDataCoordinator,
        entry: ConfigEntry,
        description: SolarManagerDeviceSensorDescription,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        short_id = device_id[-6:]
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Solar Manager Device {short_id}",
            "manufacturer": "Solar Manager",
            "via_device": (DOMAIN, entry.entry_id),
        }
        self._attr_has_entity_name = True
        self._value_fn = description.value_fn

    def _find_device(self) -> DeviceData | None:
        for d in self.coordinator.data.devices:
            if d.device_id == self._device_id:
                return d
        return None

    def _handle_coordinator_update(self) -> None:
        device = self._find_device()
        if device is not None:
            value = self._value_fn(device)
            if isinstance(value, (int, float)):
                self._attr_native_value = float(value)
            else:
                self._attr_native_value = value
        else:
            self._attr_native_value = None
        super()._handle_coordinator_update()
