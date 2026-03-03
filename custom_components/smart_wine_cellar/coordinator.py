from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_TOKEN,
    CONF_API_URL,
    CONF_SCAN_INTERVAL,
    CONF_SENSOR_MAPPINGS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Accepted unit strings that indicate Fahrenheit scale
_FAHRENHEIT_UNITS: frozenset[str] = frozenset({"°F", "F"})


class SmartWineCellarCoordinator(DataUpdateCoordinator):
    """Periodically reads HA sensors and pushes readings to Smart Wine Cellar."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        config = entry.data
        self.entry_id = entry.entry_id
        self.api_url = config[CONF_API_URL].rstrip("/")
        self.api_token = config[CONF_API_TOKEN]
        self.sensor_mappings = config[CONF_SENSOR_MAPPINGS]
        # Guard against a corrupted/zero interval reaching timedelta
        scan_interval = max(5, config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    @property
    def locations(self) -> list[str]:
        """Return all configured SWC location names."""
        return [m["swc_location"] for m in self.sensor_mappings]

    async def _async_update_data(self) -> dict:
        """Read sensors and push each mapped location to the SWC API."""
        session = async_get_clientsession(self.hass)
        results = {}

        # Read all unique sensor State objects up front — one lookup per entity,
        # avoiding a second hass.states.get() call later for attributes.
        entity_states: dict[str, object] = {}
        for mapping in self.sensor_mappings:
            for key in ("temp_entity_id", "humidity_entity_id"):
                entity_id = mapping.get(key)
                if entity_id and entity_id not in entity_states:
                    state = self.hass.states.get(entity_id)
                    entity_states[entity_id] = (
                        state
                        if state and state.state not in ("unavailable", "unknown", "none")
                        else None
                    )

        for mapping in self.sensor_mappings:
            swc_location = mapping["swc_location"]
            temp_entity = mapping.get("temp_entity_id")
            hum_entity = mapping.get("humidity_entity_id")

            if not temp_entity:
                continue

            temp_state = entity_states.get(temp_entity)
            if temp_state is None:
                _LOGGER.warning(
                    "Temperature sensor %s is unavailable, skipping location '%s'",
                    temp_entity,
                    swc_location,
                )
                continue

            try:
                temp_float = float(temp_state.state)
            except (ValueError, TypeError):
                _LOGGER.error(
                    "Invalid temperature value '%s' from %s",
                    temp_state.state,
                    temp_entity,
                )
                continue

            hum_state = entity_states.get(hum_entity) if hum_entity else None
            try:
                hum_float = float(hum_state.state) if hum_state is not None else 0.0
            except (ValueError, TypeError):
                hum_float = 0.0

            # Unit is read from the already-fetched State object — no second lookup
            unit = temp_state.attributes.get("unit_of_measurement", "°C")
            scale = "F" if unit.strip() in _FAHRENHEIT_UNITS else "C"

            payload = {
                "temperature": temp_float,
                "humidity": hum_float,
                "location": swc_location,
                "scale": scale,
            }

            try:
                async with session.post(
                    f"{self.api_url}/api/thermometer/save",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 403:
                        raise ConfigEntryAuthFailed(
                            "Subscription required or token invalid"
                        )
                    if resp.status == 200:
                        results[swc_location] = {
                            "temp": temp_float,
                            "humidity": hum_float,
                            "scale": scale,
                        }
                        _LOGGER.debug(
                            "Pushed %.1f°%s / %.1f%% to SWC location '%s'",
                            temp_float,
                            scale,
                            hum_float,
                            swc_location,
                        )
                    else:
                        _LOGGER.error(
                            "SWC API returned HTTP %s for location '%s'",
                            resp.status,
                            swc_location,
                        )
            except ConfigEntryAuthFailed:
                raise
            except aiohttp.ClientError as err:
                raise UpdateFailed(
                    f"Network error communicating with Smart Wine Cellar API: {err}"
                ) from err
            except Exception as err:
                raise UpdateFailed(
                    f"Unexpected error communicating with Smart Wine Cellar API: {err}"
                ) from err

        return results
