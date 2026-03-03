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

- Home Assistant **2023.6.0** or later
- An active [Smart Wine Cellar](https://smartwinecellar.xyz) PRO account with at least one configured location
- At least one temperature sensor in Home Assistant (humidity is optional)
- A Smart Wine Cellar API token (generated in the app under **[Your settings → API Tokens](https://smartwinecellar.xyz/settings#/api)**)

---

## Installation

### Via HACS (recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Go to **Integrations** → **Explore & download repositories**.
3. Search for **Smart Wine Cellar**, select it, and click **Download**.
4. Restart Home Assistant.
5. After the restart, continue with the **Configuration** steps below to finish setting it up.

> **Note:** HACS only installs the integration files. You still need to add and configure it in Home Assistant Settings — see the Configuration section below.

### Manual

1. Copy the `custom_components/smart_wine_cellar/` directory into your Home Assistant `config/custom_components/` folder.
2. Restart Home Assistant.
3. Continue with the **Configuration** steps below.

---

## Configuration

After installation (HACS or manual), configure the integration in Home Assistant:

1. Go to **Settings** (bottom-left cog icon) → **Devices & Services**.
2. Click **+ Add Integration** (bottom-right corner).
3. Search for **Smart Wine Cellar** and select it.
4. Enter your **API Token** — get it from [smartwinecellar.xyz/settings#/api](https://smartwinecellar.xyz/settings#/api).
5. Set the **sync interval** in minutes (5–60, default 15).
6. For each configured location in your Smart Wine Cellar account, map it to a Home Assistant **temperature sensor** (and optionally a **humidity sensor**).
7. Click **Finish** — the integration is now active.

---

## Changing sensors or sync interval

To update your sensor assignments or sync interval after initial setup:

1. Go to **Settings → Devices & Services**.
2. Find the **Smart Wine Cellar** card and click **Configure**.
3. Adjust the **sync interval**, then step through each location and pick new sensors. Your current sensors are pre-filled so you only need to change what you want.
4. Click **Submit** — the integration reloads automatically with the new settings.

---

## How It Works

At every sync interval the integration:

1. Reads the current state of each mapped temperature and humidity sensor.
2. Detects the temperature scale (°C or °F) from the sensor's unit attribute.
3. Posts the readings to the Smart Wine Cellar API (`POST /api/thermometer/save`) with a bearer token.
4. Skips sensors that are `unavailable` or `unknown` and logs a warning.

The integration uses Home Assistant's `DataUpdateCoordinator` pattern. For each configured location it creates a **diagnostic temperature sensor** in Home Assistant so you can confirm readings are being pushed without digging through logs. These sensors are grouped under a single **Smart Wine Cellar** device in **Settings → Devices & Services**.

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
- Issues & feature requests: [GitHub Issues](https://github.com/Yannelos/smartwinecellar-hacs/issues)
