# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VDA IR Control is a Home Assistant integration for controlling multiple cable boxes, TVs, and other IR-controllable devices using Olamex PoE ISO ESP boards. The system manages 20-30 individually controlled IR outputs, maintains a database of IR codes for various device models, and operates over Ethernet with PoE power delivery.

## Architecture

### Core Components

1. **ESP Firmware** - Microcontroller code running on Olamex PoE ISO boards that handles:
   - Ethernet connectivity with PoE power management
   - IR signal transmission through multiple output pins (GPIO)
   - Receiving commands from Home Assistant via MQTT or HTTP over Ethernet
   - Managing device state and execution logic
   - Storing/loading IR code database
   - Handling isolation features (optical isolation provided by board hardware)

2. **Home Assistant Integration** - YAML/Python configuration for:
   - Defining IR output entities (switches/buttons for each IR port)
   - Device discovery and entity registration
   - Service definitions for sending custom IR codes
   - Device templates for common cable boxes/TVs

3. **IR Code Database** - Structured storage (JSON/YAML) containing:
   - Device model mappings
   - IR code definitions for commands (power, volume, channel, etc.)
   - Transmission timing and protocol information (NEC, RC5, etc.)

### Data Flow

1. Home Assistant sends command → MQTT/HTTP to ESP
2. ESP firmware receives command, looks up IR code in database
3. ESP transmits IR signal via designated output pin
4. Device receives IR signal and executes command

## Development Commands

Using PlatformIO:

```bash
# Build firmware (adjust environment as needed: esp32, esp8266, etc.)
pio run -e esp32

# Upload firmware to device
pio run -e esp32 -t upload

# Monitor serial output
pio run -e esp32 -t monitor

# Build and upload in one command
pio run -e esp32 -t upload --verbose

# Clean build files
pio run -e esp32 -t clean
```

### PlatformIO Setup
- Install PlatformIO Core or use PlatformIO IDE (VS Code extension)
- Project configuration in `platformio.ini` defines board type (Olamex PoE ISO ESP variant), libraries, build settings, and upload parameters
- Libraries managed automatically via `platformio.ini` dependency declarations
- Required libraries: Ethernet (for PoE ISO boards), IRremoteESP8266 (or equivalent), PubSubClient (MQTT), and any Olamex-specific libraries for board features


## Key Files/Directories (to be created)

- `firmware/` - ESP microcontroller code
  - `src/` - Main firmware source
  - `lib/` - Custom libraries (IR transmitter, MQTT client, etc.)
  - `include/` - Header files
- `homeassistant/` - Home Assistant integration (custom integration for GitHub)
  - `vda_ir_control/` - Main integration package
    - `__init__.py` - Integration entry point and setup
    - `manifest.json` - Integration metadata
    - `const.py` - Constants and configuration
    - `coordinator.py` - Data coordination/discovery of boards
    - `services.py` - Service handlers for board management
    - `api.py` - Direct HTTP/MQTT communication with boards
    - `frontend/` - UI Lovelace cards and dashboard
      - `admin-dashboard.js` - Advanced admin interface
      - `board-management-card.js` - Board discovery/adoption UI
      - `ir-tester-card.js` - IR output testing interface
      - `config-manager-card.js` - Board configuration UI
    - `scripts/` - Automation scripts
      - `discover_boards.yaml` - Discovery script
      - `adopt_board.yaml` - Adoption/provisioning script
      - `remove_board.yaml` - Board removal script
- `database/` - IR code database
  - `devices.json` - Device model definitions
  - `codes/` - IR codes by device type
- `docs/` - Documentation
  - `setup.md` - Initial setup/flashing guide
  - `integration-setup.md` - HA integration installation guide
  - `admin-dashboard.md` - Dashboard usage guide
  - `adding-devices.md` - How to add new IR device codes

## Important Implementation Patterns

### Ethernet & PoE Integration
- Initialize Ethernet connection early in firmware startup (before MQTT/HTTP connections)
- Use Olamex board's Ethernet peripheral configuration for PoE ISO boards
- Implement automatic reconnection with exponential backoff for lost Ethernet connections
- Monitor PoE power status and log any power management events
- Ensure all network communication (MQTT, HTTP) operates over Ethernet, not WiFi

### IR Output Management
- Use a pin configuration mapping to track which GPIO pin corresponds to each output number (1-30)
- Account for Olamex board's GPIO layout and any reserved pins for Ethernet/PoE functions
- Implement debouncing/timing between IR transmissions to avoid conflicts
- Consider using PWM or a dedicated IR library for protocol-accurate signal generation

### IR Code Database
- Structure devices by model/brand (e.g., "Comcast XR15", "Samsung TV Model XYZ")
- Store commands as named actions (power, volume_up, channel_123) rather than raw codes
- Support multiple IR protocols (NEC, RC5, etc.) and encoding formats

### Home Assistant Integration
- Each IR output should be a separate entity (e.g., `switch.ir_output_1`, `button.ir_output_2_power`)
- Use device registry to group outputs logically (e.g., all outputs for "Living Room Cable Box")
- Implement discovery to make device registration automatic when possible

### Board Discovery & Adoption
- Each board broadcasts its presence via mDNS with a default hostname (e.g., `ir-controller-XXXXXX` using MAC address last 6 digits)
- Implement a discovery API endpoint (`/discover` or `/info`) that returns board metadata: MAC address, hostname, firmware version, number of IR outputs available
- Support a provisioning/adoption flow where Home Assistant can:
  - Discover available boards on the network
  - Send adoption request with a unique board ID and friendly name
  - Board stores adoption config (board_id, name) in persistent storage (SPIFFS/NVS)
- Board ID should be stable and human-readable (e.g., `ir_living_room`, `ir_bedroom`)
- MQTT topics should include board ID for routing (e.g., `home/ir/ir_living_room/output_1/set`, `home/ir/ir_bedroom/output_5/set`)

### Configuration
- Config files for MQTT broker, Home Assistant URL, network settings
- Ethernet configuration (IP address, gateway, DNS) via config file or DHCP
- Store adopted board ID and friendly name in persistent storage (SPIFFS/NVS)
- Allow hot-reloading of IR code database without firmware reflash
- Support management endpoints for viewing/updating board configuration

## Home Assistant Integration Architecture

### Integration Structure
The custom HA integration handles:
1. **Board Discovery** - Scans network via mDNS or manual IP ranges, queries `/info` endpoint on each board
2. **Board Adoption** - Sends adoption request (board_id, friendly_name) to board, stores mapping in HA
3. **Entity Management** - Creates switch/button entities for each IR output on adopted boards
4. **Service Handlers** - Provides services for:
   - `vda_ir_control.send_code` - Send raw IR code to specific board/output
   - `vda_ir_control.test_output` - Cycle IR output for testing
   - `vda_ir_control.discover_boards` - Trigger network discovery
   - `vda_ir_control.adopt_board` - Adopt a new board
   - `vda_ir_control.remove_board` - Remove adopted board

### Admin Dashboard UI
Frontend Lovelace cards provide:
- **Board Management Card** - Discover available boards, adopt new ones, view board status (IP, MAC, firmware version)
- **Board Configuration Card** - Edit board_id, friendly name, IR output count
- **IR Output Tester** - Test individual IR outputs to verify connectivity and transmission
- **Diagnostics Panel** - View board logs, network status, error history

### Communication Flows
1. **Discover Boards** - HA integration queries boards via mDNS hostname or scans subnet → calls `/info` on each
2. **Adopt Board** - HA sends POST to board `/{board_id}/adopt` with `board_id` and `friendly_name` → board stores and responds
3. **Send IR Code** - HA publishes to MQTT `home/ir/{board_id}/output_{n}/set` with code payload → board transmits
4. **Board Status** - Board publishes status to `home/ir/{board_id}/status` periodically → HA coordinator updates

### Data Storage
- HA stores board mappings in `vda_ir_control` config entry (board_id, friendly_name, IP, MAC)
- Boards store board_id and friendly_name in persistent storage (SPIFFS/NVS)
- IR code database can be bundled with integration or stored centrally and synced to boards

## User-Facing Dashboard & Kiosk Mode

### Dashboard Types
1. **Admin Dashboard** - For managing boards, adoption, diagnostics (protected via Home Assistant user roles)
2. **Control Dashboard** - User-facing interface for controlling cable boxes, TVs, other devices (kiosk-safe)

### Kiosk Implementation
Two approaches to consider:

**Approach 1: Fully Kiosk Browser (Recommended for Wall-Mounted Displays)**
- Use Fully Kiosk Browser app on Android tablets/displays for full-screen kiosk mode
- Configure HA to load specific dashboard URL automatically
- Fully Kiosk handles hiding status bar, lockdown, auto-refresh
- Integration can pass device info to dashboard via URL parameters

**Approach 2: Home Assistant Native Kiosk Mode**
- Use HA's native `?kiosk` URL parameter (hides sidebar, header, etc.)
- Restrict user access to control dashboard only via Home Assistant user roles
- Use HA's template conditions to hide admin controls on user accounts
- Create view-only user accounts for public/kiosk access

### Control Dashboard Features
- **Device Room Grouping** - Organize controls by location (Living Room, Bedroom, etc.)
- **Device Control Cards** - One card per controlled device showing:
  - Power button
  - Volume/Channel up/down
  - Number pad for direct channel entry
  - Common commands (mute, guide, menu)
- **Hidden Elements** - No sidebar, no header, no notifications, no HA menu
- **Responsive Design** - Works on tablets, wall-mounted displays, phones
- **Session Protection** - Auto-logout after inactivity period

### Configuration
- Control dashboard URL stored in config (e.g., `/lovelace-control` or specific dashboard ID)
- Kiosk mode URL pattern: `http://ha-url/lovelace-control?kiosk` or Fully Kiosk pointing to specific view
- Admin dashboard protected by Home Assistant user role/permissions
- Inactivity timeout configured in dashboard or app level
- Optional PIN/password lock for admin access (Fully Kiosk feature)

## Testing Strategy

- Unit tests for IR code lookup and transmission logic
- Integration tests with Home Assistant (mock MQTT)
- Hardware testing: verify IR signals reach devices correctly
- Test edge cases: rapid command sequences, invalid codes, network loss
- Dashboard testing: board discovery, adoption/removal, IR output testing

## Next Steps

### Phase 1: Firmware Foundation
1. Set up PlatformIO project for Olamex PoE ISO board
2. Implement Ethernet initialization with PoE power handling
3. Implement mDNS broadcasting with board discovery info
4. Create REST API endpoints (`/info`, `/{board_id}/adopt`)
5. Implement MQTT client connection and topic subscriptions
6. Add IR transmission library integration for single output

### Phase 2: Board Management
1. Implement board adoption flow (persistent storage of board_id)
2. Extend firmware to handle 20-30 IR outputs with pin mapping
3. Add IR code database loading from JSON
4. Implement IR code lookup and transmission logic

### Phase 3: Home Assistant Integration
1. Create custom integration boilerplate (`__init__.py`, `manifest.json`)
2. Implement board discovery coordinator (mDNS scanning)
3. Create entity discovery (switch/button for each IR output)
4. Implement service handlers for adoption, removal, IR testing
5. Create MQTT communication layer

### Phase 4: Admin Dashboard
1. Build Lovelace cards for board management UI
2. Implement board discovery and adoption UI
3. Create IR output tester interface
4. Add board configuration editor
5. Implement diagnostics/status panel

### Phase 5: IR Code Database
1. Design database schema (devices, commands, codes)
2. Build IR code database for target devices (cable boxes, TVs)
3. Implement database sync to boards
4. Create admin tools for adding/updating codes
