"""Smart Wine Cellar integration for Home Assistant.

Reads temperature and humidity sensors from HA and periodically pushes
the readings to the Smart Wine Cellar API, one POST per configured
wine cellar location.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SmartWineCellarCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Wine Cellar from a config entry."""
    coordinator = SmartWineCellarCoordinator(hass, entry.data)

    # Run the first sync immediately so errors surface right away
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _LOGGER.info(
        "Smart Wine Cellar integration loaded — %d location(s) configured",
        len(coordinator.sensor_mappings),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
