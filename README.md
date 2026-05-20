# Solar Manager Local (Home Assistant)

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Open your Home Assistant instance and show the add repository dialog in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bastbu&repository=ha-solarmanager&category=integration)
[![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=solar_manager_local)

Custom integration that reads data from a Solar Manager device via the local `/v2/point` endpoint.

### Gateway sensors

| Sensor | API field | Unit |
|---|---|---|
| PV production power | `pW` | W |
| Home consumption power | `cW` | W |
| PV energy produced total | `pWh` (accumulated) | kWh |

### Per-device sensors

Each device in the `devices` array is exposed as a separate Home Assistant device with:

| Sensor | API field | Unit |
|---|---|---|
| Power | `power` | W |
| Battery charge | `soc` | % |
| Temperature | `temperature` | °C |
| Signal | `signal` | — |

Battery charge and temperature are only created for devices that report them.

## Installation

1. Open HACS in Home Assistant.
2. Add this repository as a **Custom repository** (category: **Integration**).
3. Install **Solar Manager Local** and restart Home Assistant.

## Configuration

Add your API key to `secrets.yaml`:

```yaml
solar_manager_api_key: "YOUR_API_KEY"
```

Then add the integration and provide:

- **Base URL** — e.g. `http://192.168.1.20`
- **Secret name for API key** — default: `solar_manager_api_key`
