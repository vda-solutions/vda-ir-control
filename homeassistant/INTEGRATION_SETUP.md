# VDA IR Control Home Assistant Integration

## Overview

The `vda_ir_control` custom integration enables Home Assistant to discover, adopt, and control multiple Olamex PoE ISO ESP boards over the network. Each board manages 1-30 IR outputs for controlling cable boxes, TVs, and other IR-controllable devices.

## Features

- **Board Discovery** - Scan subnet for available IR controller boards
- **Board Adoption** - Adopt boards with custom IDs and names
- **IR Output Control** - Create switch entities for each IR output
- **Test Mode** - Send test signals to verify outputs are working
- **Service Handlers** - Integrate with Home Assistant automations and scripts
- **Real-time Status** - Poll board status via HTTP endpoints

## Installation

### As a Custom Integration

1. Clone or download the integration to your Home Assistant custom_components directory:
   ```bash
   # If you have access to your HA container/system
   cp -r homeassistant/vda_ir_control ~/.homeassistant/custom_components/
   ```

2. Restart Home Assistant

3. Go to Settings → Devices & Services → Create Integration
4. Search for "VDA IR Control"
5. Follow the setup wizard

### For Development

Add to `configuration.yaml` to load the integration in development mode:
```yaml
vda_ir_control:
```

## Configuration Flow

### Step 1: User Initiated
- User starts the integration setup
- Click "Next" to begin discovery

### Step 2: Discovery
- Scans subnet for available boards (default: 192.168.1.0/24)
- Queries `/info` endpoint on each device
- Lists discovered boards

### Step 3: Board Selection
- User selects board from discovered list
- Shows IP and MAC address of selected board

### Step 4: Adoption
- User configures:
  - **Board ID** - Unique identifier (e.g., `ir_living_room`)
  - **Board Name** - Friendly name for UI display
- Integration sends adoption request to board via HTTP
- Board stores adoption config in persistent storage

## Entities Created

For each adopted board with N IR outputs:
- Device: `vda_ir_control.{board_id}`
- Switches:
  - `switch.{board_name.lower().replace(' ', '_')}_output_1`
  - `switch.{board_name.lower().replace(' ', '_')}_output_2`
  - ... (one per output)

### Switch Behavior

**Turn On:** Sends test signal to output (100ms default)
**Turn Off:** Resets switch state (IR outputs don't have persistent state)

## Services

### `vda_ir_control.send_ir_code`
Send an IR code to a specific output.

**Parameters:**
- `board_id` (required): Board ID (string)
- `output` (required): Output number 1-30 (integer)
- `code` (required): IR code to send (string, format depends on board)

**Example:**
```yaml
service: vda_ir_control.send_ir_code
data:
  board_id: ir_living_room
  output: 1
  code: "NEC:0x12345678"
```

### `vda_ir_control.test_output`
Send a test signal to verify output connectivity.

**Parameters:**
- `board_id` (required): Board ID (string)
- `output` (required): Output number 1-30 (integer)
- `duration_ms` (optional): Duration in ms, default 500 (100-5000)

**Example:**
```yaml
service: vda_ir_control.test_output
data:
  board_id: ir_living_room
  output: 1
  duration_ms: 200
```

### `vda_ir_control.discover_boards`
Scan network for available boards.

**Parameters:**
- `subnet` (optional): Subnet to scan, default "192.168.1" (string)

**Returns:** List of discovered boards with details

**Example:**
```yaml
service: vda_ir_control.discover_boards
data:
  subnet: "192.168.1"
response_variable: discovered
```

### `vda_ir_control.get_board_status`
Get current status of a board.

**Parameters:**
- `board_id` (required): Board ID (string)

**Returns:** Board status including IP, MAC, output count, uptime, etc.

**Example:**
```yaml
service: vda_ir_control.get_board_status
data:
  board_id: ir_living_room
response_variable: status
```

## Board Requirements

Each IR controller board must implement the following HTTP API endpoints:

### `GET /info`
Returns board information.

**Response:**
```json
{
  "board_id": "ir-controller-default",
  "board_name": "Living Room IR",
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "ip_address": "192.168.1.100",
  "firmware_version": "1.0.0",
  "output_count": 10,
  "uptime_seconds": 3600
}
```

### `POST /adopt`
Adopt a board with new ID and name.

**Request:**
```json
{
  "board_id": "ir_living_room",
  "board_name": "Living Room Controller"
}
```

**Response:**
```json
{
  "success": true,
  "board_id": "ir_living_room"
}
```

### `POST /send_ir`
Send IR code to a specific output.

**Request:**
```json
{
  "output": 1,
  "code": "NEC:0x12345678"
}
```

**Response:**
```json
{
  "success": true
}
```

### `POST /test_output`
Send test signal to output.

**Request:**
```json
{
  "output": 1,
  "duration_ms": 500
}
```

**Response:**
```json
{
  "success": true
}
```

### `GET /status`
Get board status.

**Response:**
```json
{
  "board_id": "ir_living_room",
  "online": true,
  "uptime_seconds": 3600,
  "output_states": [
    {"output": 1, "status": "idle"},
    {"output": 2, "status": "idle"}
  ]
}
```

## Troubleshooting

### Board Not Found in Discovery
1. Verify board is powered on and connected via Ethernet
2. Check that board IP is in the configured subnet (default: 192.168.1.0/24)
3. Verify board has `/info` endpoint accessible via HTTP
4. Check firewall rules allow HTTP traffic

### Adoption Fails
1. Verify IP address is correct
2. Check board is reachable: `ping <board_ip>`
3. Test endpoint directly: `curl http://<board_ip>/info`
4. Check board logs for errors

### Switches Not Appearing
1. Check integration loaded successfully in HA logs
2. Verify coordinator fetched board info (check logs for output_count > 0)
3. Restart Home Assistant after adoption
4. Check entity registry for created switch entities

### Commands Not Sending
1. Verify board is online: use `get_board_status` service
2. Check output number is valid (1 to output_count)
3. Verify IR code format matches board expectations
4. Check board IR transmission circuit is functioning

## Development Notes

### File Structure
```
homeassistant/vda_ir_control/
├── __init__.py           # Integration setup and entry point
├── config_flow.py        # Config flow for discovery and adoption
├── const.py              # Constants and configuration
├── coordinator.py        # Board communication coordinator
├── services.py           # Service handler registration
├── switch.py             # Switch entity platform
├── strings.json          # UI text and service descriptions
├── manifest.json         # Integration metadata
└── py.typed              # Type hint marker
```

### Key Classes

- **VDAIRBoardCoordinator** - Manages communication with a single board
- **VDAIRDiscoveryCoordinator** - Network scanning and board discovery
- **VDAIRConfigFlow** - Config flow for setup
- **VDAIROutputSwitch** - Switch entity for each IR output

### Testing

To test the integration:

1. **Mock Board** - Create a simple HTTP server that implements the required endpoints
2. **Integration Test** - Use Home Assistant's test helpers in `tests/` directory
3. **Service Testing** - Call services via HA Developer Tools

### Future Enhancements

- MQTT-based communication instead of HTTP polling
- Button entities for individual commands
- Sensor entities for board statistics
- Diagnostics endpoint for troubleshooting
- Binary sensor for board online/offline status
- Template to support multiple board types
- IR code library management UI
