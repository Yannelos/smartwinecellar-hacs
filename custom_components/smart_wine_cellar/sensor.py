"""Diagnostic sensors for Smart Wine Cellar.

One temperature sensor entity is created per configured SWC location.
Its state reflects the last value successfully pushed to the API, making
it easy to confirm the integration is working without reading logs.
"""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up one sensor per configured SWC location."""
    coordinator: SmartWineCellarCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SmartWineCellarSensor(coordinator, location)
        for location in coordinator.locations
    )


class SmartWineCellarSensor(CoordinatorEntity[SmartWineCellarCoordinator], SensorEntity):
    """Shows the last temperature value pushed to a SWC location."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: SmartWineCellarCoordinator, location: str
    ) -> None:
        super().__init__(coordinator)
        self._location = location
        self._attr_unique_id = f"{coordinator.entry_id}_{location}"
        self._attr_name = location

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry_id)},
            name="Smart Wine Cellar",
            manufacturer="Smart Wine Cellar",
            configuration_url=API_BASE_URL,
        )

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
                return "°F" if loc_data["scale"] == "F" else "°C"
        return "°C"

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        loc_data = self.coordinator.data.get(self._location)
        if loc_data:
            return {
                "humidity": loc_data["humidity"],
                "location": self._location,
            }
        return {}
