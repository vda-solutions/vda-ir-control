# VDA IR Control Firmware Guide

This guide covers flashing the VDA IR Control firmware to ESP32 boards.

## Supported Boards

| Board | Connection | Firmware File |
|-------|------------|---------------|
| Olimex ESP32-POE-ISO | Ethernet (PoE) | `firmware-esp32-poe-iso.bin` |
| ESP32 DevKit | WiFi | `firmware-esp32-devkit-wifi.bin` |

## Prerequisites

- ESP32 board (see supported boards above)
- USB cable for flashing
- Computer with USB port
- PlatformIO (recommended) or Arduino IDE

## Option 1: Pre-built Binary (Easiest)

### Download

1. Go to [Releases](https://github.com/vda-solutions/vda-ir-control/releases)
2. Download the appropriate firmware file for your board:
   - **Olimex ESP32-POE-ISO**: `firmware-esp32-poe-iso.bin`
   - **ESP32 DevKit (WiFi)**: `firmware-esp32-devkit-wifi.bin`

### Flash with esptool

1. Install esptool:
   ```bash
   pip install esptool
   ```

2. Connect your ESP32 to your computer via USB

3. Put the board in flash mode:
   - Hold the BOOT button
   - Press and release the RESET button
   - Release the BOOT button

4. Flash the firmware:
   ```bash
   # For ESP32-POE-ISO (Ethernet)
   esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 \
     write_flash -z 0x0 firmware-esp32-poe-iso.bin

   # For ESP32 DevKit (WiFi)
   esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 \
     write_flash -z 0x0 firmware-esp32-devkit-wifi.bin
   ```

   > **Note**: The pre-built firmware binaries include the bootloader and partition table, so they must be flashed to address `0x0`.

   On macOS, the port is typically `/dev/cu.usbserial-XXXX` or `/dev/cu.SLAB_USBtoUART`
   On Windows, use `COM3` or similar

5. Press RESET to start the firmware

### Flash with ESP Web Flasher (Browser-based)

1. Go to [ESP Web Tools](https://web.esphome.io/)
2. Click "Connect"
3. Select your serial port
4. Click "Install"
5. Select the downloaded firmware file
6. Wait for flashing to complete

## Option 2: Build from Source with PlatformIO (Recommended)

### Install PlatformIO

**VS Code Extension (Recommended):**
1. Install [VS Code](https://code.visualstudio.com/)
2. Install the PlatformIO extension from the marketplace

**CLI Installation:**
```bash
pip install platformio
```

### Build and Flash

1. Clone the repository:
   ```bash
   git clone https://github.com/vda-solutions/vda-ir-control.git
   cd vda-ir-control/firmware
   ```

2. Build for your target board:
   ```bash
   # For ESP32-POE-ISO (Ethernet) - default
   pio run -e esp32-poe-iso

   # For ESP32 DevKit (WiFi)
   pio run -e esp32-devkit
   ```

3. Connect your ESP32 via USB

4. Upload the firmware:
   ```bash
   # For ESP32-POE-ISO
   pio run -e esp32-poe-iso -t upload

   # For ESP32 DevKit
   pio run -e esp32-devkit -t upload
   ```

5. Monitor serial output (optional):
   ```bash
   pio run -t monitor
   ```

### Build Both Versions

To build both firmware versions:
```bash
pio run
```

Binaries will be at:
- `.pio/build/esp32-poe-iso/firmware.bin`
- `.pio/build/esp32-devkit/firmware.bin`

## First Boot

### Olimex ESP32-POE-ISO (Ethernet)

After flashing, the board will:

1. Initialize Ethernet (wait for PoE or connect via USB power)
2. Obtain IP address via DHCP
3. Start mDNS service as `vda-ir-XXXXXX.local`
4. Start HTTP server on port 80

### ESP32 DevKit (WiFi)

After flashing, the board will:

1. Check for saved WiFi credentials
2. If no credentials saved, start AP mode:
   - SSID: `VDA-IR-XXXXXX`
   - Password: `vda-ir-setup`
   - IP: `192.168.4.1`
   - Built-in LED blinks fast to indicate AP mode ready
3. Connect to the AP and a captive portal will auto-open for WiFi setup
4. After WiFi configured, board reboots and connects to your network
5. LED turns solid on when connected successfully

#### Configure WiFi (DevKit)

The easiest method is to use the captive portal:
1. Connect to the `VDA-IR-XXXXXX` WiFi network (password: `vda-ir-setup`)
2. A captive portal will auto-open with a setup page
3. Select your WiFi network from the list and enter the password
4. Board will reboot and connect to your WiFi

Alternatively, use the REST API:
1. Connect to the `VDA-IR-XXXXXX` WiFi network (password: `vda-ir-setup`)
2. Scan for networks:
   ```bash
   curl http://192.168.4.1/wifi/scan
   ```
3. Configure WiFi:
   ```bash
   curl -X POST http://192.168.4.1/wifi/config \
     -H "Content-Type: application/json" \
     -d '{"ssid":"YourNetwork","password":"YourPassword"}'
   ```
4. Board will reboot and connect to your WiFi

### Verify Installation

1. Find the board's IP address:
   - Check your router's DHCP leases
   - Use mDNS: `ping vda-ir-XXXXXX.local`
   - Check serial output if connected via USB

2. Access the board info:
   ```bash
   curl http://<board-ip>/info
   ```

   Expected response:
   ```json
   {
     "board_id": "vda-ir-abc123",
     "board_name": "VDA IR Controller",
     "mac_address": "AA:BB:CC:DD:EE:FF",
     "ip_address": "192.168.1.100",
     "firmware_version": "1.1.0",
     "connection_type": "ethernet",
     "adopted": false,
     "total_ports": 16
   }
   ```

## Available GPIO Pins

### ESP32-POE-ISO (Ethernet)

| GPIO | Type | Notes |
|------|------|-------|
| 0, 1, 2, 3, 4, 5 | Output | General purpose |
| 13, 14, 15, 16 | Output | General purpose |
| 32, 33 | Output | General purpose |
| 34, 35, 36, 39 | Input Only | Best for IR receiver |

**Note**: GPIO 17, 18, 19, 21, 22, 23, 25, 26, 27 are reserved for Ethernet.

### ESP32 DevKit (WiFi)

| GPIO | Type | Notes |
|------|------|-------|
| 2, 4, 5, 12, 13, 14, 15 | Output | General purpose |
| 16, 17, 18, 19, 21, 22, 23 | Output | General purpose |
| 25, 26, 27, 32, 33 | Output | General purpose |
| 34, 35, 36, 39 | Input Only | Best for IR receiver |

## Hardware Wiring

### IR LED Output

Connect IR LEDs to output-capable GPIO pins:

```
GPIO Pin ──┬── 100Ω Resistor ──── IR LED Anode (+)
           │
           └── IR LED Cathode (-) ──── GND
```

For longer range, use a transistor driver:

```
GPIO Pin ──── 1kΩ ──── NPN Base
                       NPN Collector ──── IR LED Cathode
                       NPN Emitter ──── GND
                       IR LED Anode ──── 5V via 10Ω resistor
```

### IR Receiver

Connect an IR receiver (TSOP38238 or similar) to input-only pins:

```
IR Receiver VCC ──── 3.3V
IR Receiver GND ──── GND
IR Receiver OUT ──── GPIO34 (or 35, 36, 39)
```

## Troubleshooting

### Upload Failed

- **"No serial data received"**: Put the board in boot mode (hold BOOT, press RESET)
- **"Failed to connect"**: Check USB cable and port selection
- **Permission denied**: Add user to dialout group (Linux) or run as administrator

### No Ethernet Connection (POE-ISO)

- Verify PoE switch is providing power (or use USB power for testing)
- Check Ethernet cable connection
- Verify network DHCP server is running
- Check serial output for Ethernet status messages

### No WiFi Connection (DevKit)

- Verify WiFi credentials are correct
- Check signal strength (move closer to router)
- Try resetting WiFi config by erasing flash:
  ```bash
  esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash
  ```
  Then re-flash the firmware

### Board Not Responding

- Verify IP address is correct
- Check firewall allows port 8080
- Ensure board is on same network/VLAN as your computer

## Serial Output

Connect via USB and monitor at 115200 baud to see:

**Ethernet (POE-ISO):**
```
========================================
   VDA IR Control Firmware v1.1.0
   Mode: Ethernet (ESP32-POE-ISO)
========================================

Loaded config: boardId=vda-ir-abc123, ports=16
ETH: Started
ETH: Connected
ETH: Got IP - 192.168.1.100
mDNS: vda-ir-abc123.local
HTTP server started on port 80

=== Ready! ===
IP Address: 192.168.1.100
```

**WiFi (DevKit):**
```
========================================
   VDA IR Control Firmware v1.1.0
   Mode: WiFi (ESP32 DevKit)
========================================

Loaded config: boardId=vda-ir-xyz789, ports=23
Connecting to WiFi: MyNetwork
WiFi: Got IP - 192.168.1.101
mDNS: vda-ir-xyz789.local
HTTP server started on port 80

=== Ready! ===
IP Address: 192.168.1.101
LED: Solid ON (connected)
```

## Updating Firmware

### Manual Update

1. Build or download new firmware
2. Flash using the same method as initial installation
3. Configuration (board ID, port settings, WiFi credentials) is preserved in NVS flash

### Factory Reset

To clear all saved settings and start fresh:
```bash
esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash
```
Then re-flash the firmware.
