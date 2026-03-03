"""Diagnostic sensors for Smart Wine Cellar.

For each configured SWC location this module creates:
  - A temperature sensor showing the last value pushed to the API.
  - A humidity sensor (only when a humidity entity was mapped for that location).

Both are grouped under a single "Smart Wine Cellar" device so users can
confirm readings are being pushed without digging through logs.
"""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import API_BASE_URL, DOMAIN
from .coordinator import SmartWineCellarCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one temperature + one optional humidity sensor per SWC location."""
    coordinator: SmartWineCellarCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for mapping in coordinator.sensor_mappings:
        location = mapping["swc_location"]
        entities.append(SmartWineCellarTemperatureSensor(coordinator, location))
        if mapping.get("humidity_entity_id"):
            entities.append(SmartWineCellarHumiditySensor(coordinator, location))

    async_add_entities(entities)


def _device_info(coordinator: SmartWineCellarCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry_id)},
        name="Smart Wine Cellar",
        manufacturer="Smart Wine Cellar",
        configuration_url=API_BASE_URL,
    )


class SmartWineCellarTemperatureSensor(
    CoordinatorEntity[SmartWineCellarCoordinator], SensorEntity
):
    """Last temperature value pushed to a SWC location."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: SmartWineCellarCoordinator, location: str
    ) -> None:
        super().__init__(coordinator)
        self._location = location
        self._attr_unique_id = f"{coordinator.entry_id}_{location}_temperature"
        self._attr_name = location

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self.coordinator)

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        loc_data = self.coordinator.data.get(self._location)
        return loc_data["temp"] if loc_data else None

    @property
    def native_unit_of_measurement(self) -> str:
        if self.coordinator.data:
            loc_data = self.coordinator.data.get(self._location)
            if loc_data:
                return (
                    UnitOfTemperature.FAHRENHEIT
                    if loc_data["scale"] == "F"
                    else UnitOfTemperature.CELSIUS
                )
        return UnitOfTemperature.CELSIUS


class SmartWineCellarHumiditySensor(
    CoordinatorEntity[SmartWineCellarCoordinator], SensorEntity
):
    """Last humidity value pushed to a SWC location."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: SmartWineCellarCoordinator, location: str
    ) -> None:
        super().__init__(coordinator)
        self._location = location
        self._attr_unique_id = f"{coordinator.entry_id}_{location}_humidity"
        self._attr_name = f"{location} Humidity"

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self.coordinator)

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        loc_data = self.coordinator.data.get(self._location)
        return loc_data["humidity"] if loc_data else None
