<p align="center">
  <a href="https://smartwinecellar.xyz" target="_blank">
    <img src="https://smartwinecellar.xyz/assets/img/smartwinecellar.svg" height="150" alt="Smart Wine Cellar">
  </a>
</p>

# Smart Wine Cellar — Home Assistant Integration

A [HACS](https://hacs.xyz/) custom integration that connects Home Assistant to the [Smart Wine Cellar](https://smartwinecellar.xyz) cloud service. It reads temperature and humidity sensors from your Home Assistant instance and periodically pushes readings to the Smart Wine Cellar API, keeping your cellar conditions in sync.

---

## Features

- Push temperature and humidity readings from any Home Assistant sensor to Smart Wine Cellar
- Support for multiple wine cellar locations with individual sensor mappings
- Configurable sync interval (5–60 minutes, default 15)
- Automatic temperature scale detection (°C / °F)
- UI-based setup via the Home Assistant Integrations page (no YAML required)
- Gracefully handles unavailable or unknown sensors — skips and logs, never crashes

---

## Requirements

- Home Assistant **2023.1.0** or later
- An active [Smart Wine Cellar](https://smartwinecellar.xyz) PRO account with at least one configured location
- At least one temperature sensor in Home Assistant (humidity is optional)
- A Smart Wine Cellar API token (generated in the app under **Settings → API Tokens**)

---

## Installation

### Via HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** and click the **+** button.
3. Search for **Smart Wine Cellar** and install it.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/smart_wine_cellar/` directory into your Home Assistant `config/custom_components/` folder.
2. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Integrations**.
2. Click **Add Integration** and search for **Smart Wine Cellar**.
3. Enter your **API URL** and **API Token** (found in the Smart Wine Cellar app under **Settings → API Tokens**).
4. Set the **sync interval** in minutes (5–60, default 15).
5. For each configured location in your Smart Wine Cellar account, map it to a Home Assistant **temperature sensor** (and optionally a **humidity sensor**). Locations can be skipped if you don't want to track them.
6. Click **Finish** — the integration is now active.

---

## How It Works

At every sync interval the integration:

1. Reads the current state of each mapped temperature and humidity sensor.
2. Detects the temperature scale (°C or °F) from the sensor's unit attribute.
3. Posts the readings to the Smart Wine Cellar API (`POST /api/thermometer/save`) with a bearer token.
4. Skips sensors that are `unavailable` or `unknown` and logs a warning.

The integration uses Home Assistant's `DataUpdateCoordinator` pattern — it does **not** create any new entities or devices in Home Assistant; it only reads existing ones.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `invalid_auth` | API token is wrong or expired | Generate a new token in the Smart Wine Cellar app |
| `subscription_required` | Account lacks an active subscription | Check your subscription status at smartwinecellar.xyz |
| `cannot_connect` | Network or server unreachable | Verify your API URL and internet connectivity |
| Sensor skipped (warning in logs) | Sensor state is `unavailable` / `unknown` | Check that the sensor is working in Home Assistant |

Enable **debug logging** for detailed output:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.smart_wine_cellar: debug
```

---

## Links

- Website: [smartwinecellar.xyz](https://smartwinecellar.xyz)
- Issues & feature requests: [GitHub Issues](https://github.com/smartwinecellar/smartwinecellar-hacs/issues)
