"""Config flow for Smart Wine Cellar integration.

Step 1 (user): Enter API URL, API token, and sync interval.
              Validates credentials and fetches the user's SWC locations.

Step 2 (sensor_mapping): For each SWC location, select a temperature sensor
                          and optionally a humidity sensor. One sensor can be
                          mapped to multiple locations (e.g. two racks sharing
                          one thermometer).
"""

import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_API_TOKEN,
    CONF_API_URL,
    CONF_SCAN_INTERVAL,
    CONF_SENSOR_MAPPINGS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SmartWineCellarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Smart Wine Cellar config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_url: str = ""
        self._api_token: str = ""
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._locations: list[str] = []
        self._location_index: int = 0
        self._mappings: list[dict] = []

    # ------------------------------------------------------------------
    # Step 1: Credentials
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            api_url = user_input[CONF_API_URL].rstrip("/")
            api_token = user_input[CONF_API_TOKEN]
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            locations, error = await self._fetch_locations(api_url, api_token)

            if error:
                errors["base"] = error
            else:
                self._api_url = api_url
                self._api_token = api_token
                self._scan_interval = scan_interval
                self._locations = locations
                self._location_index = 0
                self._mappings = []

                if not locations:
                    # No wine locations configured in SWC yet — still allow setup
                    return self._create_entry()

                return await self.async_step_sensor_mapping()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_URL): selector.TextSelector(
                        selector.TextSelectorConfig(type="url")
                    ),
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(type="password")
                    ),
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=5, max=60, mode="box")
                    ),
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2: Sensor mapping (one location at a time)
    # ------------------------------------------------------------------

    async def async_step_sensor_mapping(self, user_input=None):
        if user_input is not None:
            temp_entity = user_input.get("temperature_sensor")
            hum_entity = user_input.get("humidity_sensor") or None

            if temp_entity:
                self._mappings.append(
                    {
                        "swc_location": self._locations[self._location_index],
                        "temp_entity_id": temp_entity,
                        "humidity_entity_id": hum_entity,
                    }
                )

            self._location_index += 1

            if self._location_index < len(self._locations):
                # More locations to configure
                return await self.async_step_sensor_mapping()

            return self._create_entry()

        current_location = self._locations[self._location_index]
        total = len(self._locations)
        step_label = f"{self._location_index + 1}/{total}"

        return self.async_show_form(
            step_id="sensor_mapping",
            data_schema=vol.Schema(
                {
                    vol.Optional("temperature_sensor"): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="temperature"
                        )
                    ),
                    vol.Optional("humidity_sensor"): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="humidity"
                        )
                    ),
                }
            ),
            description_placeholders={
                "location": current_location,
                "step": step_label,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_entry(self):
        return self.async_create_entry(
            title="Smart Wine Cellar",
            data={
                CONF_API_URL: self._api_url,
                CONF_API_TOKEN: self._api_token,
                CONF_SENSOR_MAPPINGS: self._mappings,
                CONF_SCAN_INTERVAL: self._scan_interval,
            },
        )

    @staticmethod
    async def _fetch_locations(api_url: str, api_token: str):
        """Call /api/thermometer/setup and return (locations, error_key)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{api_url}/api/thermometer/setup",
                    headers={"Authorization": f"Bearer {api_token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 401:
                        return [], "invalid_auth"
                    if resp.status == 403:
                        return [], "subscription_required"
                    if resp.status != 200:
                        return [], "cannot_connect"

                    data = await resp.json()
                    locations = [
                        loc["location"]
                        for loc in data.get("locations", [])
                        if loc.get("location")
                    ]
                    return locations, None

        except aiohttp.ClientError:
            return [], "cannot_connect"
        except Exception:  # noqa: BLE001
            return [], "unknown"
