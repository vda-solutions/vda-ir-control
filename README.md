# VDA IR Control

A Home Assistant integration for controlling multiple IR devices (cable boxes, TVs, etc.) using Olimex ESP32-POE-ISO boards. Designed for commercial venues like bars and restaurants that need to control many devices from a central location.

## Features

- **Multi-board support**: Manage multiple ESP32-POE-ISO boards, each with up to 16 configurable IR ports
- **PoE powered**: Power over Ethernet eliminates the need for separate power supplies
- **IR Learning**: Learn IR codes directly from original remotes
- **Device Profiles**: Create and manage device profiles with learned IR commands
- **Custom Lovelace Card**: Beautiful UI for board management and device control
- **HACS Compatible**: Easy installation through HACS (Home Assistant Community Store)

## Hardware Requirements

- **[Olimex ESP32-POE-ISO](https://www.olimex.com/Products/IoT/ESP32/ESP32-POE-ISO/open-source-hardware)** board(s)
- **IR LED(s)** connected to GPIO output pins
- **IR Receiver** (e.g., TSOP38238) connected to GPIO input pins for learning
- **PoE Switch** or PoE injector
- **Ethernet cables**

### Available GPIO Pins

| GPIO | Type | Notes |
|------|------|-------|
| 0 | Output | Boot mode (use with caution) |
| 1 | Output | TX0 - Serial output |
| 2 | Output | On-board LED |
| 3 | Output | RX0 - Serial input |
| 4 | Output | General purpose |
| 5 | Output | General purpose |
| 13 | Output | General purpose |
| 14 | Output | General purpose |
| 15 | Output | General purpose |
| 16 | Output | General purpose |
| 32 | Output | General purpose |
| 33 | Output | General purpose |
| 34 | Input Only | ADC1_CH6 - Best for IR receiver |
| 35 | Input Only | ADC1_CH7 |
| 36 | Input Only | SENSOR_VP |
| 39 | Input Only | SENSOR_VN |

**Note**: GPIO 17, 18, 19, 21, 22, 23, 25, 26, 27 are reserved for Ethernet PHY.

## Installation

### 1. Flash the Firmware

See [FIRMWARE_GUIDE.md](FIRMWARE_GUIDE.md) for detailed flashing instructions.

**Quick start with PlatformIO:**
```bash
cd firmware
pio run -t upload
```

Or download the pre-built firmware from [Releases](https://github.com/vda-solutions/vda-ir-control/releases).

### 2. Install the Home Assistant Integration

#### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu (⋮) in the top right
3. Select "Custom repositories"
4. Add repository URL: `https://github.com/vda-solutions/vda-ir-control`
5. Select category: **Integration**
6. Click "Add"
7. Find "VDA IR Control" in the integrations list and click "Download"
8. Restart Home Assistant

#### Manual Installation

1. Copy the `custom_components/vda_ir_control` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

### 3. Install the Lovelace Card

#### Via HACS

1. Open HACS in Home Assistant
2. Go to "Frontend" section
3. Click the three dots menu (⋮) in the top right
4. Select "Custom repositories"
5. Add repository URL: `https://github.com/vda-solutions/vda-ir-control`
6. Select category: **Lovelace**
7. Click "Add"
8. Find "VDA IR Control Card" and click "Download"
9. Refresh your browser (Ctrl+Shift+R / Cmd+Shift+R)

#### Manual Installation

1. Copy `dist/vda-ir-control-card.js` to your `config/www/` directory
2. Add to your Lovelace resources:
   ```yaml
   resources:
     - url: /local/vda-ir-control-card.js
       type: module
   ```

### 4. Configure the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "VDA IR Control"
4. Follow the setup wizard

## Usage

### Adding the Management Card

Add the VDA IR Control card to your dashboard:

```yaml
type: custom:vda-ir-control-card
```

### Board Discovery and Adoption

1. Open the VDA IR Control card
2. Click "Discover Boards" to find ESP32 boards on your network
3. Click "Adopt" next to each discovered board
4. Assign a friendly name (e.g., "Living Room IR Controller")

### Configuring IR Ports

1. Select a board from the dropdown
2. Go to the "Ports" tab
3. For each GPIO pin you want to use:
   - Set **Mode**: `IR Output` for transmitting, `IR Input` for receiving/learning
   - Set **Name**: A descriptive name (e.g., "TV Output", "IR Receiver")
4. Click Save

### Learning IR Codes

1. Go to the "Learn Commands" tab
2. Select the board with an IR input configured
3. Select the IR input port
4. Click "Start Learning"
5. Point your original remote at the IR receiver and press a button
6. The learned code will appear - save it to a device profile

### Creating Device Profiles

1. Go to the "Devices" tab
2. Click "Create Device"
3. Enter device details:
   - **Name**: e.g., "Living Room TV"
   - **Board**: Select the controlling board
   - **Output Port**: Select the IR output GPIO
   - **Device Type**: e.g., "Samsung TV", "Comcast Box"
4. Add commands from learned codes or enter codes manually

### Controlling Devices

Once configured, devices appear as entities in Home Assistant:
- `switch.vda_ir_living_room_tv_power`
- `button.vda_ir_living_room_tv_volume_up`
- etc.

Use these in automations, scripts, or dashboards.

## API Reference

The ESP32 firmware exposes a REST API on port 8080:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/info` | GET | Board information |
| `/status` | GET | Board status and uptime |
| `/ports` | GET | List all GPIO ports and their configuration |
| `/ports/configure` | POST | Configure a port's mode and name |
| `/adopt` | POST | Adopt the board with a new ID and name |
| `/send_ir` | POST | Send an IR code |
| `/test_output` | POST | Test an IR output |
| `/learning/start` | POST | Start IR learning mode |
| `/learning/stop` | POST | Stop IR learning mode |
| `/learning/status` | GET | Get learning status and received codes |

## Troubleshooting

### Board not discovered

1. Ensure the ESP32 is connected via Ethernet and has an IP address
2. Check that the board is on the same network/VLAN as Home Assistant
3. Verify the firmware is running (check serial output or try accessing `http://<board-ip>:8080/info`)

### IR codes not working

1. Verify the IR LED is connected to the correct GPIO pin
2. Check the LED is oriented correctly (anode to GPIO, cathode to ground through resistor)
3. Try different IR protocols (NEC, Sony, RC5, RC6)
4. Use the test output feature to verify the GPIO is working

### Learning not receiving codes

1. Verify the IR receiver is connected to an input-only GPIO (34, 35, 36, or 39)
2. Ensure the receiver is powered (3.3V) and grounded
3. Point the remote directly at the receiver from close range
4. Check serial output for received signals

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
- **Documentation**: [Wiki](https://github.com/vda-solutions/vda-ir-control/wiki)
