"""Config flow for Smart Wine Cellar integration.

Step 1 (user): Enter API token and sync interval.
              Validates credentials and fetches the user's SWC locations.

Step 2 (sensor_mapping): For each SWC location, select a temperature sensor
                          and optionally a humidity sensor. One sensor can be
                          mapped to multiple locations (e.g. two racks sharing
                          one thermometer).

The OptionsFlow reuses the same sensor_mapping step and lets users update
their sensor assignments and sync interval after initial setup.
"""

import hashlib
import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_BASE_URL,
    CONF_API_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_SENSOR_MAPPINGS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Shared helper — used by both ConfigFlow and OptionsFlow
# ------------------------------------------------------------------

async def _fetch_locations(hass: HomeAssistant, api_token: str):
    """Call /api/thermometer/setup and return (locations, error_key).

    Uses the shared HA aiohttp session so that custom CA bundles and
    HA-level SSL settings are respected.
    """
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{API_BASE_URL}/api/thermometer/setup",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 401:
                return [], "invalid_auth"
            if resp.status == 403:
                return [], "subscription_required"
            if resp.status != 200:
                return [], "cannot_connect"

            try:
                data = await resp.json()
            except (aiohttp.ContentTypeError, ValueError):
                _LOGGER.error("SWC API returned a non-JSON response during setup")
                return [], "cannot_connect"

            if not isinstance(data, dict):
                _LOGGER.error("SWC API setup response has unexpected shape: %r", data)
                return [], "cannot_connect"

            locations = [
                loc["location"]
                for loc in data.get("locations", [])
                if isinstance(loc, dict) and loc.get("location")
            ]
            return locations, None

    except aiohttp.ClientError:
        return [], "cannot_connect"
    except Exception:  # noqa: BLE001
        return [], "unknown"


def _sensor_mapping_schema(default_temp=None, default_hum=None) -> vol.Schema:
    """Return a sensor mapping schema with optional pre-filled defaults."""
    return vol.Schema(
        {
            vol.Optional(
                "temperature_sensor",
                description={"suggested_value": default_temp},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                )
            ),
            vol.Optional(
                "humidity_sensor",
                description={"suggested_value": default_hum},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="humidity"
                )
            ),
        }
    )


# ------------------------------------------------------------------
# Config flow (initial setup)
# ------------------------------------------------------------------

class SmartWineCellarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Smart Wine Cellar config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_token: str = ""
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._locations: list[str] = []
        self._location_index: int = 0
        self._mappings: list[dict] = []

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "SmartWineCellarOptionsFlow":
        return SmartWineCellarOptionsFlow()

    # Step 1: Credentials

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            api_token = user_input[CONF_API_TOKEN]
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            # Prevent duplicate entries for the same account
            token_hash = hashlib.sha256(api_token.encode()).hexdigest()[:16]
            await self.async_set_unique_id(token_hash)
            self._abort_if_unique_id_configured()

            locations, error = await _fetch_locations(self.hass, api_token)

            if error:
                errors["base"] = error
            else:
                self._api_token = api_token
                self._scan_interval = scan_interval
                self._locations = locations
                self._location_index = 0
                self._mappings = []

                if not locations:
                    return self._create_entry()

                return await self.async_step_sensor_mapping()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
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

    # Step 2: Sensor mapping (one location at a time)

    async def async_step_sensor_mapping(self, user_input=None):
        errors = {}

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
                return await self.async_step_sensor_mapping()

            if not self._mappings:
                self._location_index = 0
                errors["base"] = "no_mappings"
            else:
                return self._create_entry()

        current_location = self._locations[self._location_index]

        return self.async_show_form(
            step_id="sensor_mapping",
            data_schema=_sensor_mapping_schema(),
            description_placeholders={
                "location": current_location,
                "step": f"{self._location_index + 1}/{len(self._locations)}",
            },
            errors=errors,
        )

    def _create_entry(self):
        return self.async_create_entry(
            title="Smart Wine Cellar",
            data={
                CONF_API_TOKEN: self._api_token,
                CONF_SENSOR_MAPPINGS: self._mappings,
                CONF_SCAN_INTERVAL: self._scan_interval,
            },
        )


# ------------------------------------------------------------------
# Options flow (reconfiguration via the "Configure" button)
# ------------------------------------------------------------------

class SmartWineCellarOptionsFlow(config_entries.OptionsFlow):
    """Let users update sensor mappings and sync interval after initial setup."""

    def __init__(self) -> None:
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._locations: list[str] = []
        self._location_index: int = 0
        self._mappings: list[dict] = []
        self._existing_mappings: list[dict] = []

    # Step 1: Sync interval

    async def async_step_init(self, user_input=None):
        errors = {}

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        if user_input is not None:
            self._scan_interval = user_input[CONF_SCAN_INTERVAL]

            # Fetch current locations so we can re-map sensors
            api_token = self.config_entry.data[CONF_API_TOKEN]
            self._existing_mappings = self.config_entry.options.get(
                CONF_SENSOR_MAPPINGS,
                self.config_entry.data.get(CONF_SENSOR_MAPPINGS, []),
            )

            locations, error = await _fetch_locations(self.hass, api_token)
            if error:
                errors["base"] = error
            else:
                self._locations = locations
                self._location_index = 0
                self._mappings = []

                if not locations:
                    # No locations on the account — save interval and exit
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_SCAN_INTERVAL: self._scan_interval,
                            CONF_SENSOR_MAPPINGS: self._existing_mappings,
                        },
                    )

                return await self.async_step_sensor_mapping()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=5, max=60, mode="box")
                    ),
                }
            ),
            errors=errors,
        )

    # Step 2: Sensor mapping (pre-filled with current assignments)

    async def async_step_sensor_mapping(self, user_input=None):
        errors = {}

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
                return await self.async_step_sensor_mapping()

            if not self._mappings:
                self._location_index = 0
                errors["base"] = "no_mappings"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SCAN_INTERVAL: self._scan_interval,
                        CONF_SENSOR_MAPPINGS: self._mappings,
                    },
                )

        current_location = self._locations[self._location_index]

        # Pre-fill with whatever was saved for this location previously
        existing = next(
            (m for m in self._existing_mappings if m["swc_location"] == current_location),
            {},
        )

        return self.async_show_form(
            step_id="sensor_mapping",
            data_schema=_sensor_mapping_schema(
                default_temp=existing.get("temp_entity_id"),
                default_hum=existing.get("humidity_entity_id"),
            ),
            description_placeholders={
                "location": current_location,
                "step": f"{self._location_index + 1}/{len(self._locations)}",
            },
            errors=errors,
        )
