# VDA IR Control

[![GitHub Release](https://img.shields.io/github/v/release/vda-solutions/vda-ir-control)](https://github.com/vda-solutions/vda-ir-control/releases)
[![License](https://img.shields.io/github/license/vda-solutions/vda-ir-control)](LICENSE)

A Home Assistant integration for controlling multiple IR devices (cable boxes, TVs, etc.) using ESP32 boards. Designed for commercial venues like bars and restaurants that need to control many devices from a central location.

## Features

- **Multi-board support**: Manage multiple ESP32 boards, each with configurable IR ports
- **Dual connectivity**: Supports both Ethernet (PoE) and WiFi boards
- **IR Learning**: Learn IR codes directly from original remotes
- **Device Profiles**: Create and manage device profiles with learned IR commands
- **Custom Lovelace Card**: Beautiful UI for board management and device control
- **HACS Compatible**: Easy installation through HACS (Home Assistant Community Store)

## Supported Hardware

| Board | Connection | IR Outputs | IR Inputs | Power |
|-------|------------|------------|-----------|-------|
| [Olimex ESP32-POE-ISO](https://www.olimex.com/Products/IoT/ESP32/ESP32-POE-ISO/open-source-hardware) | Ethernet | 12 GPIOs | 4 GPIOs | PoE or USB |
| ESP32 DevKit | WiFi | 19 GPIOs | 4 GPIOs | USB |

### Additional Hardware Needed

- **IR LED(s)** - Connected to GPIO output pins for transmitting
- **IR Receiver** (e.g., TSOP38238) - Connected to GPIO input pins for learning
- **For Ethernet boards**: PoE Switch or PoE injector + Ethernet cables
- **For WiFi boards**: 2.4GHz WiFi network

## Quick Start

### 1. Download & Flash Firmware

Download the pre-built firmware for your board from [Releases](https://github.com/vda-solutions/vda-ir-control/releases):

| Board | Firmware File | Size |
|-------|---------------|------|
| Olimex ESP32-POE-ISO | [`firmware-esp32-poe-iso-v1.2.0.bin`](https://github.com/vda-solutions/vda-ir-control/releases/latest/download/firmware-esp32-poe-iso-v1.2.0.bin) | ~1020 KB |
| ESP32 DevKit (WiFi) | [`firmware-esp32-devkit-wifi-v1.2.0.bin`](https://github.com/vda-solutions/vda-ir-control/releases/latest/download/firmware-esp32-devkit-wifi-v1.2.0.bin) | ~993 KB |

Flash using [esptool](https://github.com/espressif/esptool):
```bash
pip install esptool
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 \
  write_flash -z 0x0 firmware-esp32-devkit-wifi-v1.2.0.bin
```

> **Note**: The firmware binary includes bootloader and partition table - flash to address `0x0`.

Or use the browser-based [ESP Web Tools](https://web.esphome.io/) flasher.

See [FIRMWARE_GUIDE.md](FIRMWARE_GUIDE.md) for detailed instructions.

### 2. Connect Your Board

**Ethernet (ESP32-POE-ISO):**
- Connect Ethernet cable to PoE switch
- Board gets IP via DHCP automatically
- Find IP in router or via mDNS: `vda-ir-XXXXXX.local`

**WiFi (ESP32 DevKit):**
- Board starts AP mode: `VDA-IR-XXXXXX` (password: `vda-ir-setup`)
- Built-in LED (GPIO2) blinks fast to indicate AP mode ready
- Connect to the AP and a captive portal auto-opens for WiFi setup
- Board reboots and joins your network
- LED turns solid when connected successfully

**LED Status Indicators (WiFi DevKit only):**
| LED Pattern | Meaning |
|-------------|---------|
| Slow blink (500ms) | Booting / Connecting to WiFi |
| Fast blink (150ms) | AP mode ready, waiting for configuration |
| Solid on | Connected and operational |
| Double blink | Error state |

### 3. Install Home Assistant Integration

#### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click ⋮ → **Custom repositories**
3. Add: `https://github.com/vda-solutions/vda-ir-control`
4. Category: **Integration**
5. Click "Add", then find and download "VDA IR Control"
6. Restart Home Assistant

#### Manual Installation

Copy `custom_components/vda_ir_control` to your HA `config/custom_components/` directory.

### 4. Install Lovelace Card

#### Via HACS

1. Open HACS → **Frontend**
2. Click ⋮ → **Custom repositories**
3. Add: `https://github.com/vda-solutions/vda-ir-control`
4. Category: **Lovelace**
5. Download "VDA IR Control Card"
6. Hard refresh browser (Ctrl+Shift+R)

#### Manual Installation

1. Copy `dist/vda-ir-control-card.js` to `config/www/`
2. Add resource in Lovelace:
   ```yaml
   resources:
     - url: /local/vda-ir-control-card.js
       type: module
   ```

### 5. Configure Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "VDA IR Control"
4. Follow the setup wizard

## Available GPIO Pins

### ESP32-POE-ISO (Ethernet)

| GPIO | Type | Notes |
|------|------|-------|
| 0, 1, 2, 3, 4, 5 | Output | General purpose (0,1,2,3 have boot considerations) |
| 13, 14, 15, 16 | Output | General purpose |
| 32, 33 | Output | General purpose |
| 34, 35, 36, 39 | **Input Only** | Best for IR receiver |

> **Note**: GPIO 17, 18, 19, 21, 22, 23, 25, 26, 27 are reserved for Ethernet PHY.

### ESP32 DevKit (WiFi)

| GPIO | Type | Notes |
|------|------|-------|
| 2, 4, 5, 12, 13, 14, 15 | Output | General purpose |
| 16, 17, 18, 19, 21, 22, 23 | Output | General purpose |
| 25, 26, 27, 32, 33 | Output | General purpose |
| 34, 35, 36, 39 | **Input Only** | Best for IR receiver |

## Usage

### Adding the Management Card

Add the VDA IR Control card to your dashboard:

```yaml
type: custom:vda-ir-control-card
```

### Board Discovery and Adoption

1. Open the VDA IR Control card
2. Click **Discover Boards** to find ESP32 boards on your network
3. Click **Adopt** next to each discovered board
4. Assign a friendly name (e.g., "Bar Area Controller")

### Configuring IR Ports

1. Select a board from the dropdown
2. Go to the **Ports** tab
3. For each GPIO pin:
   - Set **Mode**: `IR Output` for transmitting, `IR Input` for receiving/learning
   - Set **Name**: A descriptive name (e.g., "TV1 Output", "IR Receiver")
4. Click **Save**

### Learning IR Codes

1. Go to the **Learn Commands** tab
2. Select the board with an IR input configured
3. Select the IR input port from the dropdown
4. Click **Start Learning**
5. Point your original remote at the IR receiver and press a button
6. The learned code will appear - save it to a device profile

### Creating Device Profiles

1. Go to the **Devices** tab
2. Click **Create Device**
3. Enter device details:
   - **Name**: e.g., "Bar TV 1"
   - **Board**: Select the controlling board
   - **Output Port**: Select the IR output GPIO from dropdown
   - **Device Type**: e.g., "Samsung TV", "Comcast Box"
4. Add commands from learned codes or enter codes manually

### Built-in IR Profiles

The integration includes pre-loaded IR code profiles for popular devices, so you can get started without learning codes:

**TVs:**
| Brand | Protocol | Commands |
|-------|----------|----------|
| Samsung | SAMSUNG | Power, Volume, Channel, Navigation, Numbers, HDMI |
| LG | NEC | Power, Volume, Channel, Navigation, Numbers, HDMI 1-4 |
| Sony | SONY | Power, Volume, Channel, Navigation, Numbers |
| Vizio | NEC | Power, Volume, Channel, Navigation, Numbers, HDMI |
| TCL/Roku | NEC | Power, Volume, Navigation, Playback |
| Hisense | NEC | Power, Volume, Channel, Navigation, Numbers |

**Streaming Devices:**
| Device | Protocol | Commands |
|--------|----------|----------|
| Apple TV | NEC | Menu, Navigation, Select, Play/Pause |
| Amazon Fire TV | NEC | Power, Home, Navigation, Playback |
| Roku | NEC | Power, Home, Navigation, Playback |

**Soundbars:**
| Brand | Protocol | Commands |
|-------|----------|----------|
| Samsung | SAMSUNG | Power, Volume, Mute, Source |
| Vizio | NEC | Power, Volume, Mute, Input, Bluetooth |
| Sony | SONY | Power, Volume, Mute, Input |

**Cable/Satellite:**
| Provider | Protocol | Commands |
|----------|----------|----------|
| DirecTV | DIRECTV | Power, Guide, Menu, Navigation, Playback, Numbers |

### Controlling Devices

Once configured, devices appear as entities in Home Assistant:
- `switch.vda_ir_bar_tv_1_power`
- `button.vda_ir_bar_tv_1_volume_up`
- etc.

Use these in automations, scripts, or dashboards.

## Hardware Wiring

### IR LED Output

Basic wiring (short range):
```
GPIO Pin ──── 100Ω Resistor ──── IR LED (+) ──── GND
```

With transistor driver (longer range):
```
GPIO Pin ──── 1kΩ ──┬── NPN Base
                    │
                    └── NPN Emitter ──── GND

5V ──── 10Ω ──── IR LED (+) ──── IR LED (-) ──── NPN Collector
```

### IR Receiver

```
3.3V ──── IR Receiver VCC
GND  ──── IR Receiver GND
GPIO34 ── IR Receiver OUT (or GPIO 35, 36, 39)
```

## REST API Reference

The ESP32 firmware exposes a REST API on port 80:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/info` | GET | Board information (ID, MAC, IP, firmware version) |
| `/status` | GET | Board status and uptime |
| `/ports` | GET | List all GPIO ports and their configuration |
| `/ports/configure` | POST | Configure a port's mode and name |
| `/adopt` | POST | Adopt the board with a new ID and name |
| `/send_ir` | POST | Send an IR code |
| `/test_output` | POST | Test an IR output |
| `/learning/start` | POST | Start IR learning mode |
| `/learning/stop` | POST | Stop IR learning mode |
| `/learning/status` | GET | Get learning status and received codes |
| `/wifi/scan` | GET | Scan WiFi networks (WiFi boards only) |
| `/wifi/config` | POST | Configure WiFi credentials (WiFi boards only) |

### Example API Calls

```bash
# Get board info
curl http://192.168.1.100/info

# Configure a port as IR output
curl -X POST http://192.168.1.100/ports/configure \
  -H "Content-Type: application/json" \
  -d '{"port": 4, "mode": "ir_output", "name": "TV Output"}'

# Send IR code
curl -X POST http://192.168.1.100/send_ir \
  -H "Content-Type: application/json" \
  -d '{"output": 4, "code": "20DF10EF", "protocol": "nec"}'
```

### Home Assistant API Endpoints

The integration also exposes REST API endpoints within Home Assistant:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/vda_ir_control/boards` | GET | List all configured boards |
| `/api/vda_ir_control/profiles` | GET | List user-created profiles |
| `/api/vda_ir_control/builtin_profiles` | GET | List pre-loaded IR profiles |
| `/api/vda_ir_control/builtin_profiles/{id}` | GET | Get a specific built-in profile |
| `/api/vda_ir_control/devices` | GET | List all configured devices |

**Query parameters for `/api/vda_ir_control/builtin_profiles`:**
- `device_type`: Filter by type (tv, cable_box, soundbar, streaming)
- `manufacturer`: Filter by brand name

## Troubleshooting

### Board not discovered

1. Ensure the ESP32 has an IP address (check router DHCP or serial output)
2. Verify board is on the same network/VLAN as Home Assistant
3. Try accessing `http://<board-ip>/info` directly
4. For WiFi boards, ensure they've connected to your network (not still in AP mode)

### IR codes not working

1. Verify IR LED is connected to the correct GPIO pin
2. Check LED orientation (anode to GPIO via resistor, cathode to ground)
3. Try different IR protocols (NEC, Sony, RC5, RC6)
4. Use the test output feature to verify GPIO is working
5. For long distances, use a transistor driver circuit

### Learning not receiving codes

1. Verify IR receiver is connected to an input-only GPIO (34, 35, 36, or 39)
2. Ensure receiver is powered (3.3V) and grounded
3. Point remote directly at receiver from close range (< 1 meter)
4. Check serial output for received signals
5. Try a different remote - some use uncommon protocols

### WiFi board won't connect

1. Ensure your network is 2.4GHz (ESP32 doesn't support 5GHz)
2. Check WiFi credentials are correct
3. Move board closer to router during initial setup
4. Factory reset: erase flash and re-flash firmware

## Building from Source

```bash
# Clone repository
git clone https://github.com/vda-solutions/vda-ir-control.git
cd vda-ir-control/firmware

# Build for ESP32-POE-ISO (Ethernet)
pio run -e esp32-poe-iso

# Build for ESP32 DevKit (WiFi)
pio run -e esp32-devkit

# Upload to connected board
pio run -e esp32-poe-iso -t upload
```

## Development Setup

For testing the integration locally with Home Assistant in Docker:

```bash
# Start Home Assistant and Mosquitto
docker-compose up -d

# Access Home Assistant at http://localhost:8123

# View logs
docker logs -f homeassistant
```

> **Important**: The docker-compose.yml uses `network_mode: host` so Home Assistant can discover ESP32 boards on your local network.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/vda-solutions/vda-ir-control/issues)
- **Firmware Guide**: [FIRMWARE_GUIDE.md](FIRMWARE_GUIDE.md)
