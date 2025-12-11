# VDA IR Control Firmware Guide

This guide covers flashing the VDA IR Control firmware to Olimex ESP32-POE-ISO boards.

## Prerequisites

- Olimex ESP32-POE-ISO board
- USB-to-Serial adapter (FTDI, CP2102, or similar) OR USB cable if using board's built-in USB
- Computer with USB port
- PlatformIO (recommended) or Arduino IDE

## Option 1: Pre-built Binary (Easiest)

### Download

1. Go to [Releases](https://github.com/vda-solutions/vda-ir-control/releases)
2. Download `firmware.bin` from the latest release

### Flash with esptool

1. Install esptool:
   ```bash
   pip install esptool
   ```

2. Connect the ESP32-POE-ISO to your computer via USB

3. Put the board in flash mode:
   - Hold the BOOT button
   - Press and release the RESET button
   - Release the BOOT button

4. Flash the firmware:
   ```bash
   esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 \
     write_flash -z 0x1000 firmware.bin
   ```

   On macOS, the port is typically `/dev/cu.usbserial-XXXX`
   On Windows, use `COM3` or similar

5. Press RESET to start the firmware

### Flash with ESP Web Flasher (Browser-based)

1. Go to [ESP Web Tools](https://web.esphome.io/)
2. Click "Connect"
3. Select your serial port
4. Click "Install"
5. Select the downloaded `firmware.bin` file
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

2. Build the firmware:
   ```bash
   pio run
   ```

3. Connect the ESP32-POE-ISO via USB

4. Upload the firmware:
   ```bash
   pio run -t upload
   ```

5. Monitor serial output (optional):
   ```bash
   pio run -t monitor
   ```

### Build Flags

The firmware is configured for the Olimex ESP32-POE-ISO in `platformio.ini`:

```ini
[env:esp32-poe-iso]
platform = espressif32@6.4.0
board = esp32-poe-iso
framework = arduino

build_flags =
    -DETH_PHY_TYPE=ETH_PHY_LAN8720
    -DETH_PHY_ADDR=0
    -DETH_PHY_MDC=23
    -DETH_PHY_MDIO=18
    -DETH_PHY_POWER=12
    -DETH_CLK_MODE=ETH_CLOCK_GPIO17_OUT
```

## Option 3: Arduino IDE

### Setup

1. Install [Arduino IDE](https://www.arduino.cc/en/software)

2. Add ESP32 board support:
   - Go to **File** → **Preferences**
   - Add to "Additional Board Manager URLs":
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Go to **Tools** → **Board** → **Board Manager**
   - Search for "esp32" and install "esp32 by Espressif Systems"

3. Install required libraries via **Tools** → **Manage Libraries**:
   - ArduinoJson (by Benoit Blanchon)
   - IRremoteESP8266 (by David Conran, Mark Szabo, et al.)

### Configure Board

1. Go to **Tools** → **Board** and select "Olimex ESP32-POE-ISO"
2. Set upload speed to 921600
3. Select the correct port

### Flash

1. Open `firmware/src/main.cpp`
2. Click the Upload button (→)

## First Boot

After flashing, the board will:

1. Initialize Ethernet (wait for PoE or connect via USB power)
2. Obtain IP address via DHCP
3. Start mDNS service as `vda-ir-XXXXXX.local` (XXXXXX = last 6 digits of MAC)
4. Start HTTP server on port 8080

### Verify Installation

1. Connect the board to your PoE switch

2. Find the board's IP address:
   - Check your router's DHCP leases
   - Use mDNS: `ping vda-ir-XXXXXX.local`
   - Check serial output if connected via USB

3. Access the board info:
   ```bash
   curl http://<board-ip>:8080/info
   ```

   Expected response:
   ```json
   {
     "board_id": "vda-ir-abc123",
     "board_name": "VDA IR Controller",
     "mac_address": "AA:BB:CC:DD:EE:FF",
     "ip_address": "192.168.1.100",
     "firmware_version": "1.0.0",
     "adopted": false,
     "total_ports": 16
   }
   ```

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

### No Ethernet Connection

- Verify PoE switch is providing power (or use USB power for testing)
- Check Ethernet cable connection
- Verify network DHCP server is running
- Check serial output for Ethernet status messages

### Board Not Responding

- Verify IP address is correct
- Check firewall allows port 8080
- Ensure board is on same network/VLAN as your computer

## Updating Firmware

### OTA Update (Future Feature)

OTA updates are planned for future releases.

### Manual Update

1. Build or download new firmware
2. Flash using the same method as initial installation
3. Configuration (board ID, port settings) is preserved in NVS flash

## Serial Output

Connect via USB and monitor at 115200 baud to see:

```
========================================
   VDA IR Control Firmware v1.0.0
   For Olimex ESP32-POE-ISO
========================================

Loaded config: boardId=vda-ir-abc123, ports=16
ETH: Started
ETH: Connected
ETH: Got IP - 192.168.1.100
ETH: MAC - AA:BB:CC:DD:EE:FF
mDNS: vda-ir-abc123.local
HTTP server started on port 8080

=== Ready! ===
IP Address: 192.168.1.100
Board ID: vda-ir-abc123
HTTP Server: http://192.168.1.100:8080
```

## Building a Release Binary

To create a release binary for distribution:

```bash
cd firmware
pio run

# Binary will be at:
# .pio/build/esp32-poe-iso/firmware.bin
```

Copy this file to the `releases` directory or upload to GitHub Releases.
