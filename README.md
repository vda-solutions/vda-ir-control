# VDA IR Control

[![GitHub Release](https://img.shields.io/github/v/release/vda-solutions/vda-ir-control)](https://github.com/vda-solutions/vda-ir-control/releases)
[![License](https://img.shields.io/github/license/vda-solutions/vda-ir-control)](LICENSE)

A Home Assistant integration for controlling multiple IR devices (TVs, AV receivers, cable boxes, etc.) using ESP32 boards. Designed for commercial venues like bars and restaurants that need to control many devices from a central location.

## What This Does

The VDA IR Control integration provides:

- **Multi-board Management** - Connect multiple ESP32 IR controllers
- **Device Profiles** - Manage IR code profiles for your devices
- **IR Learning** - Learn codes from original remotes
- **Network Devices** - Control HDMI matrices and network-controllable devices
- **REST API** - Full API for automation and custom integrations
- **Community Profiles** - Sync IR codes from the community repository

## Part of the VDA IR Control Ecosystem

This integration works with several companion repositories:

| Repository | Purpose | Required |
|------------|---------|----------|
| **vda-ir-control** | Home Assistant Integration (this repo) | Yes |
| [vda-ir-control-admin-card](https://github.com/vda-solutions/vda-ir-control-admin-card) | Admin/Management Lovelace Card | Yes |
| [vda-ir-remote-card](https://github.com/vda-solutions/vda-ir-remote-card) | Remote Control Lovelace Card | Optional |
| [vda-ir-firmware](https://github.com/vda-solutions/vda-ir-firmware) | ESP32 Firmware | Yes |
| [vda-ir-profiles](https://github.com/vda-solutions/vda-ir-profiles) | Community IR Profiles | Optional |

## Installation

### Step 1: Flash Firmware to ESP32

Download firmware from [vda-ir-firmware releases](https://github.com/vda-solutions/vda-ir-firmware/releases):

| Board | Firmware |
|-------|----------|
| Olimex ESP32-POE-ISO | `firmware-esp32-poe-iso-vX.X.X.bin` |
| ESP32 DevKit (WiFi) | `firmware-esp32-devkit-wifi-vX.X.X.bin` |

Flash using [esptool](https://github.com/espressif/esptool):
```bash
esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash 0x0 firmware-esp32-devkit-wifi-v1.2.1.bin
```

### Step 2: Install Integration (HACS)

1. Open HACS
2. Click ⋮ → **Custom repositories**
3. Add: `https://github.com/vda-solutions/vda-ir-control`
4. Type: **Integration**
5. Download "VDA IR Control"
6. Restart Home Assistant

### Step 3: Install Admin Card (HACS)

1. Open HACS
2. Click ⋮ → **Custom repositories**
3. Add: `https://github.com/vda-solutions/vda-ir-control-admin-card`
4. Type: **Dashboard**
5. Download "VDA IR Control Admin Card"
6. Hard refresh browser (Ctrl+Shift+R)

### Step 4: Install Remote Card (Optional)

1. Open HACS
2. Click ⋮ → **Custom repositories**
3. Add: `https://github.com/vda-solutions/vda-ir-remote-card`
4. Type: **Dashboard**
5. Download "VDA IR Remote Card"

### Step 5: Add Cards to Dashboard

```yaml
# Admin card for configuration
type: custom:vda-ir-control-card

# Remote card for device control
type: custom:vda-ir-remote-card
```

## Supported Hardware

| Board | Connection | Features |
|-------|------------|----------|
| [Olimex ESP32-POE-ISO](https://www.olimex.com/Products/IoT/ESP32/ESP32-POE-ISO/) | Ethernet + PoE | Stable, isolated power |
| ESP32 DevKit | WiFi | Easy setup, captive portal |

See [vda-ir-firmware](https://github.com/vda-solutions/vda-ir-firmware) for hardware setup and wiring guides.

## Built-in IR Profiles

The integration includes pre-loaded profiles for popular devices:

**TVs:** Samsung, LG, Sony, Vizio, TCL/Roku, Hisense
**AV Receivers:** Pioneer, Pioneer Elite
**Soundbars:** Samsung, Sony, Vizio
**Streaming:** Apple TV, Amazon Fire TV, Roku
**Cable/Satellite:** DirecTV

Additional profiles available via [vda-ir-profiles](https://github.com/vda-solutions/vda-ir-profiles) community repository.

## Home Assistant API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/vda_ir_control/boards` | List configured boards |
| `/api/vda_ir_control/devices` | List controlled devices |
| `/api/vda_ir_control/profiles` | List user profiles |
| `/api/vda_ir_control/builtin_profiles` | List built-in profiles |
| `/api/vda_ir_control/community_profiles` | List synced community profiles |
| `/api/vda_ir_control/sync_profiles` | Sync from community repo |

## Troubleshooting

### Board not discovered
- Verify board has IP (check router DHCP)
- Ensure same network/VLAN as Home Assistant
- Try accessing `http://<board-ip>/info` directly

### IR codes not working
- Check IR LED connection and polarity
- Try different protocols (NEC, SAMSUNG, SONY)
- Use transistor driver for longer range

### Cards not loading
- Hard refresh browser (Ctrl+Shift+R)
- Check browser console for errors
- Verify resources are added to Lovelace

## Contributing

Contributions welcome! See individual repositories for contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/vda-solutions/vda-ir-control/issues)
- **Firmware**: [vda-ir-firmware](https://github.com/vda-solutions/vda-ir-firmware)
- **Community Profiles**: [vda-ir-profiles](https://github.com/vda-solutions/vda-ir-profiles)
