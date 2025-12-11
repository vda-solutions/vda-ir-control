# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VDA IR Control is a Home Assistant integration for controlling multiple IR devices (TVs, cable boxes, etc.) using ESP32 boards. It consists of two main components:

1. **ESP32 Firmware** (`firmware/`) - C++ firmware for IR transmission/reception
2. **Home Assistant Integration** (`custom_components/vda_ir_control/`) - Python integration for HA

## Build Commands

### Firmware (PlatformIO)

```bash
# Build for Olimex ESP32-POE-ISO (Ethernet)
cd firmware && pio run -e esp32-poe-iso

# Build for ESP32 DevKit (WiFi)
cd firmware && pio run -e esp32-devkit

# Build both environments
cd firmware && pio run

# Upload to connected board
cd firmware && pio run -e esp32-poe-iso -t upload

# Monitor serial output
cd firmware && pio run -t monitor
```

Built binaries are output to:
- `.pio/build/esp32-poe-iso/firmware.bin`
- `.pio/build/esp32-devkit/firmware.bin`

Release binaries should be copied to `releases/` folder.

### Home Assistant Integration

No build step required. The integration is installed by copying `custom_components/vda_ir_control/` to HA's `config/custom_components/` directory.

## Architecture

### Firmware Architecture

The firmware (`firmware/src/main.cpp`) uses conditional compilation for dual board support:

- `USE_ETHERNET` - Olimex ESP32-POE-ISO with Ethernet PHY
- `USE_WIFI` - ESP32 DevKit with WiFi (includes AP mode for setup)

Key components:
- **WebServer** on port 80 - REST API for all operations
- **IRsend/IRrecv** - IR transmission and learning via IRremoteESP8266 library
- **Preferences** - NVS flash storage for persistent configuration
- **mDNS** - Device discovery as `vda-ir-XXXXXX.local`
- **DNSServer** (WiFi only) - Captive portal for easy WiFi setup
- **LED Status** (WiFi only) - GPIO2 LED indicates connection state

REST API endpoints: `/info`, `/status`, `/ports`, `/ports/configure`, `/adopt`, `/send_ir`, `/test_output`, `/learning/start`, `/learning/stop`, `/learning/status`, `/wifi/scan`, `/wifi/config`

### Home Assistant Integration Architecture

```
custom_components/vda_ir_control/
├── __init__.py      # Entry point, registers frontend and platforms
├── api.py           # REST API endpoints (HomeAssistantView subclasses)
├── coordinator.py   # VDAIRBoardCoordinator - manages board communication
├── services.py      # HA service handlers (send_ir_code, learn, etc.)
├── storage.py       # Persistent storage for boards/profiles/devices
├── models.py        # Data models (BoardConfig, DeviceProfile, IRCode, etc.)
├── device_types.py  # Device type definitions and GPIO pin mappings
├── config_flow.py   # Config entry setup flow
├── switch.py        # Switch platform entities
└── const.py         # Constants and domain definition
```

Data flow:
1. **Coordinator** polls boards via HTTP and maintains connection state
2. **Services** handle user actions (send IR, learn codes, manage devices)
3. **Storage** persists boards, device profiles, and controlled devices using HA's Store
4. **API** exposes endpoints for the Lovelace frontend card

Key data models:
- `BoardConfig` - ESP32 board configuration with port mappings
- `DeviceProfile` - IR codes for a device type (e.g., "Samsung TV")
- `ControlledDevice` - Physical device instance linked to board output and profile
- `IRCode` - Single IR command with protocol and raw code data

### GPIO Pin Constraints

ESP32-POE-ISO has restricted GPIO due to Ethernet PHY:
- **Output capable**: 0, 1, 2, 3, 4, 5, 13, 14, 15, 16, 32, 33
- **Input only** (IR receiver): 34, 35, 36, 39
- **Reserved for Ethernet**: 17, 18, 19, 21, 22, 23, 25, 26, 27

ESP32 DevKit (WiFi) has more GPIOs available - see `device_types.py`.

## Library Dependencies

### Firmware
- `ArduinoJson@^6.21.3` - JSON parsing (uses v6 syntax: `StaticJsonDocument`, `createNestedArray`)
- `IRremoteESP8266@^2.8.6` - IR transmission/reception
- `espressif32@6.4.0` - ESP32 platform

### Home Assistant Integration
- Standard HA libraries (aiohttp, voluptuous)
- No external Python dependencies

## Key Patterns

### ArduinoJson v6 Syntax
The firmware uses ArduinoJson v6, NOT v7:
```cpp
StaticJsonDocument<512> doc;           // Not JsonDocument
JsonArray arr = doc.createNestedArray("items");  // Not doc["items"].to<JsonArray>()
JsonObject obj = arr.createNestedObject();       // Not arr.add<JsonObject>()
```

### Conditional Compilation
Board-specific code uses `#ifdef USE_ETHERNET` / `#ifdef USE_WIFI` guards throughout `main.cpp`.

### HA Service Registration
Services in `services.py` use voluptuous schemas and `supports_response` for return values. GPIO ports use `vol.Range(min=0, max=39)`.

## Version Management & Release Process

**IMPORTANT**: When making changes to the firmware or integration, Claude must automatically handle versioning and releases.

### Version Locations

Update ALL of these when bumping versions:

1. **Firmware** (`firmware/src/main.cpp`):
   ```cpp
   Serial.println("   VDA IR Control Firmware v1.0.0");
   doc["firmware_version"] = "1.0.0";
   ```

2. **HA Integration** (`custom_components/vda_ir_control/manifest.json`):
   ```json
   "version": "1.0.0"
   ```

### When to Bump Versions

- **Patch (1.0.x)**: Bug fixes, minor tweaks
- **Minor (1.x.0)**: New features, non-breaking changes
- **Major (x.0.0)**: Breaking changes, major rewrites

### Release Workflow

After completing changes that warrant a new version:

1. **Update version strings** in all locations listed above

2. **Build firmware** (both environments):
   ```bash
   cd firmware && pio run
   ```

3. **Create merged firmware binaries** (includes bootloader + partition table):
   ```bash
   VERSION="X.Y.Z"  # e.g., "1.1.0"
   cd firmware

   # Create merged binary for POE-ISO
   pio pkg exec -p tool-esptoolpy -- esptool.py --chip esp32 merge_bin \
     -o "../releases/firmware-esp32-poe-iso-v${VERSION}.bin" \
     --flash_mode dio --flash_size 4MB \
     0x1000 .pio/build/esp32-poe-iso/bootloader.bin \
     0x8000 .pio/build/esp32-poe-iso/partitions.bin \
     0x10000 .pio/build/esp32-poe-iso/firmware.bin

   # Create merged binary for DevKit WiFi
   pio pkg exec -p tool-esptoolpy -- esptool.py --chip esp32 merge_bin \
     -o "../releases/firmware-esp32-devkit-wifi-v${VERSION}.bin" \
     --flash_mode dio --flash_size 4MB \
     0x1000 .pio/build/esp32-devkit/bootloader.bin \
     0x8000 .pio/build/esp32-devkit/partitions.bin \
     0x10000 .pio/build/esp32-devkit/firmware.bin
   ```

   **IMPORTANT**: Release binaries MUST be merged to include bootloader. Users flash to address `0x0`.

   **Firmware naming convention**: `firmware-<board>-v<version>.bin`
   - `firmware-esp32-poe-iso-v1.1.0.bin`
   - `firmware-esp32-devkit-wifi-v1.1.0.bin`

4. **Commit changes**:
   ```bash
   git add -A
   git commit -m "Release vX.Y.Z: <brief description>"
   ```

5. **Push to GitHub**:
   ```bash
   git push origin main
   ```

6. **Create GitHub Release** (for significant releases):
   ```bash
   VERSION="X.Y.Z"

   # Create release
   gh release create v${VERSION} \
     --title "v${VERSION}" \
     --notes "## Changes
   - Change 1
   - Change 2"

   # Upload firmware binaries (with version in filename)
   gh release upload v${VERSION} \
     "releases/firmware-esp32-poe-iso-v${VERSION}.bin" \
     "releases/firmware-esp32-devkit-wifi-v${VERSION}.bin"
   ```

### Automatic Actions

When the user requests changes to the firmware or integration code, Claude should:

1. Make the requested code changes
2. Determine if a version bump is warranted (new features = yes, bug fixes = yes, minor refactors = no)
3. If bumping version:
   - Update all version locations (main.cpp banner, main.cpp JSON response, manifest.json)
   - Rebuild firmware for both environments
   - Copy binaries to releases folder **with version suffix** (e.g., `firmware-esp32-devkit-wifi-v1.2.0.bin`)
4. Commit with a descriptive message
5. Push to GitHub
6. For significant releases (new features, important fixes), create a GitHub Release with versioned binaries

### Repository Info

- **GitHub**: https://github.com/vda-solutions/vda-ir-control
- **Main branch**: `main`
- **Release assets**: Pre-built firmware binaries for both board types
