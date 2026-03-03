"""Config flow for Smart Wine Cellar integration.

Step 1 (user / init): Credentials + sync interval. Validates the token and
                       fetches the SWC locations for the account.

Step 2 (sensor_mapping): All locations shown on a single page. Each location
                          gets a temperature selector and an optional humidity
                          selector, pre-filled with existing assignments when
                          reconfiguring via the "Configure" button.
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

# Maximum number of locations supported in the single-page mapping form.
# The translation file has entries for indices 0–(MAX_LOCATIONS-1).
MAX_LOCATIONS = 8


# ------------------------------------------------------------------
# Shared helpers
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


def _mapping_schema(
    locations: list[str],
    existing: list[dict],
) -> vol.Schema:
    """Build a single-page schema with one temp+hum pair per location.

    Field names are temp_0/hum_0, temp_1/hum_1 … so the translation file
    can label and describe each pair independently. Existing sensor
    assignments are pre-filled via suggested_value.
    """
    fields: dict = {}
    for i, location in enumerate(locations):
        current = next(
            (m for m in existing if m["swc_location"] == location), {}
        )
        fields[vol.Optional(
            f"temp_{i}",
            description={"suggested_value": current.get("temp_entity_id")},
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
        )
        fields[vol.Optional(
            f"hum_{i}",
            description={"suggested_value": current.get("humidity_entity_id")},
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
        )
    return vol.Schema(fields)


def _parse_mappings(user_input: dict, locations: list[str]) -> list[dict]:
    """Reconstruct the sensor mapping list from the flat indexed form fields."""
    mappings = []
    for i, location in enumerate(locations):
        temp = user_input.get(f"temp_{i}")
        hum = user_input.get(f"hum_{i}") or None
        if temp:
            mappings.append(
                {
                    "swc_location": location,
                    "temp_entity_id": temp,
                    "humidity_entity_id": hum,
                }
            )
    return mappings


def _location_placeholders(locations: list[str]) -> dict:
    """Return {loc_0: 'Cellar', loc_1: 'Cellar - Right', …} for form labels."""
    return {f"loc_{i}": loc for i, loc in enumerate(locations)}


# ------------------------------------------------------------------
# Config flow (initial setup — 2 steps)
# ------------------------------------------------------------------

class SmartWineCellarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Smart Wine Cellar config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_token: str = ""
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._locations: list[str] = []

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "SmartWineCellarOptionsFlow":
        return SmartWineCellarOptionsFlow()

    # Step 1: token + interval

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            api_token = user_input[CONF_API_TOKEN]
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

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

                if not locations:
                    return self._create_entry([])

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

    # Step 2: all sensor mappings on one page

    async def async_step_sensor_mapping(self, user_input=None):
        errors = {}

        if user_input is not None:
            mappings = _parse_mappings(user_input, self._locations)
            if not mappings:
                errors["base"] = "no_mappings"
            else:
                return self._create_entry(mappings)

        return self.async_show_form(
            step_id="sensor_mapping",
            data_schema=_mapping_schema(self._locations, []),
            description_placeholders=_location_placeholders(self._locations),
            errors=errors,
        )

    def _create_entry(self, mappings: list[dict]):
        return self.async_create_entry(
            title="Smart Wine Cellar",
            data={
                CONF_API_TOKEN: self._api_token,
                CONF_SENSOR_MAPPINGS: mappings,
                CONF_SCAN_INTERVAL: self._scan_interval,
            },
        )


# ------------------------------------------------------------------
# Options flow (reconfiguration via the "Configure" button — 2 steps)
# ------------------------------------------------------------------

class SmartWineCellarOptionsFlow(config_entries.OptionsFlow):
    """Let users update sensor mappings and sync interval after initial setup."""

    def __init__(self) -> None:
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._locations: list[str] = []
        self._existing_mappings: list[dict] = []

    # Step 1: sync interval

    async def async_step_init(self, user_input=None):
        errors = {}

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        if user_input is not None:
            self._scan_interval = user_input[CONF_SCAN_INTERVAL]

            self._existing_mappings = self.config_entry.options.get(
                CONF_SENSOR_MAPPINGS,
                self.config_entry.data.get(CONF_SENSOR_MAPPINGS, []),
            )

            api_token = self.config_entry.data[CONF_API_TOKEN]
            locations, error = await _fetch_locations(self.hass, api_token)
            if error:
                errors["base"] = error
            else:
                self._locations = locations
                if not locations:
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

    # Step 2: all sensor mappings on one page (pre-filled)

    async def async_step_sensor_mapping(self, user_input=None):
        errors = {}

        if user_input is not None:
            mappings = _parse_mappings(user_input, self._locations)
            if not mappings:
                errors["base"] = "no_mappings"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SCAN_INTERVAL: self._scan_interval,
                        CONF_SENSOR_MAPPINGS: mappings,
                    },
                )

        return self.async_show_form(
            step_id="sensor_mapping",
            data_schema=_mapping_schema(self._locations, self._existing_mappings),
            description_placeholders=_location_placeholders(self._locations),
            errors=errors,
        )
