#!/usr/bin/env python3
"""Mock IR Board HTTP Server for testing the Home Assistant integration."""

import json
import logging
import random
import string
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import threading
import time

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# ESP32-POE-ISO Available GPIO Pins for IR
# Based on official Olimex pinout diagram
# Ethernet reserved: GPIO17, GPIO18, GPIO19, GPIO21, GPIO22, GPIO23, GPIO25, GPIO26, GPIO27
ESP32_POE_ISO_GPIO_PINS = {
    # FREE pins - directly labeled on pinout
    0: {"gpio": 0, "name": "GPIO0", "can_input": True, "can_output": True, "notes": "FREE - Boot strapping pin, free after boot (WROOM only)"},
    1: {"gpio": 1, "name": "GPIO1", "can_input": True, "can_output": True, "notes": "FREE - USB programming, free after boot"},
    2: {"gpio": 2, "name": "GPIO2", "can_input": True, "can_output": True, "notes": "MUX SD CARD - Shared with SD card, 2.2k pull-up"},
    3: {"gpio": 3, "name": "GPIO3", "can_input": True, "can_output": True, "notes": "FREE - USB programming, free after boot"},
    4: {"gpio": 4, "name": "GPIO4", "can_input": True, "can_output": True, "notes": "FREE - UEXT connector"},
    5: {"gpio": 5, "name": "GPIO5", "can_input": True, "can_output": True, "notes": "FREE - 10k pull-up"},
    13: {"gpio": 13, "name": "GPIO13", "can_input": True, "can_output": True, "notes": "FREE - UEXT connector, 2.2k pull-up"},
    14: {"gpio": 14, "name": "GPIO14", "can_input": True, "can_output": True, "notes": "MUX SD CARD - Shared with SD card"},
    15: {"gpio": 15, "name": "GPIO15", "can_input": True, "can_output": True, "notes": "MUX SD CARD - Shared with SD card, 10k pull-up"},
    16: {"gpio": 16, "name": "GPIO16", "can_input": True, "can_output": True, "notes": "FREE - UEXT connector, 2.2k pull-up (NOT on WROVER)"},
    32: {"gpio": 32, "name": "GPIO32", "can_input": True, "can_output": True, "notes": "FREE"},
    33: {"gpio": 33, "name": "GPIO33", "can_input": True, "can_output": True, "notes": "FREE"},
    # Input-only pins (good for IR receiver)
    34: {"gpio": 34, "name": "GPIO34", "can_input": True, "can_output": False, "notes": "BUT1 - Input only, user button, 10k pull-up"},
    35: {"gpio": 35, "name": "GPIO35", "can_input": True, "can_output": False, "notes": "BAT M - Input only, battery voltage measurement"},
    36: {"gpio": 36, "name": "GPIO36", "can_input": True, "can_output": False, "notes": "FREE - Input only, UEXT connector, 2.2k pull-up"},
    39: {"gpio": 39, "name": "GPIO39", "can_input": True, "can_output": False, "notes": "PWR SENSE - Input only, external power detection"},
}

# Simulated board state
BOARD_STATE = {
    "board_id": "ir-test-board",
    "board_name": "Test Board",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "ip_address": "192.168.4.87",
    "firmware_version": "1.0.0",
    "total_ports": len(ESP32_POE_ISO_GPIO_PINS),
    "uptime_seconds": 3600,
    "adopted": False,
}

# Port configurations: gpio_number -> {mode, name}
# Initialize all ports - input-only pins as inputs, others as disabled by default
PORT_CONFIGS = {}
for gpio, pin_info in ESP32_POE_ISO_GPIO_PINS.items():
    if not pin_info["can_output"]:
        # Input-only pins default to ir_input
        PORT_CONFIGS[gpio] = {"mode": "ir_input", "name": f"IR Receiver ({pin_info['name']})"}
    elif gpio == 4:
        # Set GPIO4 as a default output for testing
        PORT_CONFIGS[gpio] = {"mode": "ir_output", "name": "Bar TV 1"}
    elif gpio == 5:
        PORT_CONFIGS[gpio] = {"mode": "ir_output", "name": "Bar TV 2"}
    else:
        PORT_CONFIGS[gpio] = {"mode": "disabled", "name": ""}

# Output states for IR outputs
OUTPUT_STATES = {gpio: "idle" for gpio, config in PORT_CONFIGS.items() if config["mode"] == "ir_output"}

# IR Learning state
LEARNING_STATE = {
    "active": False,
    "port": None,
    "timeout": 10,
    "start_time": None,
    "received_code": None,
}

# Simulated IR codes that can be "received" during learning
SIMULATED_IR_CODES = [
    {"protocol": "nec", "code": "0x20DF10EF", "raw": "9000,4500,560,560,560,1690,560,560,560,560"},
    {"protocol": "nec", "code": "0x20DF40BF", "raw": "9000,4500,560,1690,560,560,560,1690,560,560"},
    {"protocol": "rc5", "code": "0x1234", "raw": "889,889,1778,889,889,889,889,1778"},
    {"protocol": "sony", "code": "0xA90", "raw": "2400,600,1200,600,600,600,1200,600,600"},
]


class MockBoardHandler(BaseHTTPRequestHandler):
    """HTTP Request handler for mock IR board."""

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/info":
            self._handle_info()
        elif parsed_path.path == "/status":
            self._handle_status()
        elif parsed_path.path == "/ports":
            self._handle_get_ports()
        elif parsed_path.path == "/learning/status":
            self._handle_learning_status()
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        if parsed_path.path == "/adopt":
            self._handle_adopt(data)
        elif parsed_path.path == "/send_ir":
            self._handle_send_ir(data)
        elif parsed_path.path == "/test_output":
            self._handle_test_output(data)
        elif parsed_path.path == "/ports/configure":
            self._handle_configure_port(data)
        elif parsed_path.path == "/learning/start":
            self._handle_start_learning(data)
        elif parsed_path.path == "/learning/stop":
            self._handle_stop_learning()
        elif parsed_path.path == "/learning/receive":
            self._handle_receive_ir(data)
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_info(self):
        """Handle /info endpoint."""
        # Count outputs based on port config
        output_count = sum(1 for p in PORT_CONFIGS.values() if p["mode"] == "ir_output")
        input_count = sum(1 for p in PORT_CONFIGS.values() if p["mode"] == "ir_input")

        response = {
            "board_id": BOARD_STATE["board_id"],
            "board_name": BOARD_STATE["board_name"],
            "mac_address": BOARD_STATE["mac_address"],
            "ip_address": BOARD_STATE["ip_address"],
            "firmware_version": BOARD_STATE["firmware_version"],
            "total_ports": BOARD_STATE["total_ports"],
            "output_count": output_count,
            "input_count": input_count,
            "uptime_seconds": BOARD_STATE["uptime_seconds"],
            "adopted": BOARD_STATE["adopted"],
        }
        _LOGGER.info("GET /info - Returning board info")
        self._send_json(200, response)

    def _handle_status(self):
        """Handle /status endpoint."""
        response = {
            "board_id": BOARD_STATE["board_id"],
            "online": True,
            "uptime_seconds": BOARD_STATE["uptime_seconds"],
            "output_states": [
                {"output": i, "status": OUTPUT_STATES.get(i, "idle")}
                for i in range(2, BOARD_STATE["total_ports"] + 1)
                if PORT_CONFIGS.get(i, {}).get("mode") == "ir_output"
            ],
            "learning_active": LEARNING_STATE["active"],
        }
        _LOGGER.info("GET /status - Returning board status")
        self._send_json(200, response)

    def _handle_get_ports(self):
        """Handle /ports endpoint - get port configurations."""
        ports = []
        for gpio, config in sorted(PORT_CONFIGS.items()):
            pin_info = ESP32_POE_ISO_GPIO_PINS.get(gpio, {})
            ports.append({
                "port": gpio,
                "gpio": gpio,
                "mode": config["mode"],
                "name": config["name"],
                "gpio_name": pin_info.get("name", f"GPIO{gpio}"),
                "can_input": pin_info.get("can_input", True),
                "can_output": pin_info.get("can_output", True),
                "notes": pin_info.get("notes", ""),
            })

        response = {
            "total_ports": len(ESP32_POE_ISO_GPIO_PINS),
            "ports": ports,
        }
        _LOGGER.info("GET /ports - Returning port configurations")
        self._send_json(200, response)

    def _handle_configure_port(self, data):
        """Handle /ports/configure endpoint."""
        port = data.get("port")
        mode = data.get("mode")
        name = data.get("name")

        if port not in ESP32_POE_ISO_GPIO_PINS:
            self._send_json(400, {"error": f"Invalid GPIO port {port}. Available: {list(ESP32_POE_ISO_GPIO_PINS.keys())}"})
            return

        if mode not in ["ir_input", "ir_output", "disabled"]:
            self._send_json(400, {"error": f"Invalid mode {mode}"})
            return

        # Check if trying to set output on input-only pin
        pin_info = ESP32_POE_ISO_GPIO_PINS[port]
        if mode == "ir_output" and not pin_info["can_output"]:
            self._send_json(400, {"error": f"GPIO{port} is input-only and cannot be used as IR output"})
            return

        PORT_CONFIGS[port] = {
            "mode": mode,
            "name": name or f"Port {port}",
        }

        # Update output states
        if mode == "ir_output":
            OUTPUT_STATES[port] = "idle"
        elif port in OUTPUT_STATES:
            del OUTPUT_STATES[port]

        _LOGGER.info(f"POST /ports/configure - GPIO{port} set to {mode} ({name})")
        self._send_json(200, {"success": True, "port": port, "gpio": port, "mode": mode, "name": name})

    def _handle_adopt(self, data):
        """Handle /adopt endpoint."""
        board_id = data.get("board_id")
        board_name = data.get("board_name")

        if not board_id or not board_name:
            self._send_json(400, {"error": "Missing board_id or board_name"})
            return

        BOARD_STATE["board_id"] = board_id
        BOARD_STATE["board_name"] = board_name
        BOARD_STATE["adopted"] = True

        _LOGGER.info(f"POST /adopt - Adopted as '{board_id}' ({board_name})")
        self._send_json(200, {"success": True, "board_id": board_id})

    def _handle_send_ir(self, data):
        """Handle /send_ir endpoint."""
        output = data.get("output")
        code = data.get("code")

        if not output or not code:
            self._send_json(400, {"error": "Missing output or code"})
            return

        # Check port is configured as output
        port_config = PORT_CONFIGS.get(output, {})
        if port_config.get("mode") != "ir_output":
            self._send_json(400, {"error": f"Port {output} is not configured as output"})
            return

        OUTPUT_STATES[output] = "transmitting"
        _LOGGER.info(f"POST /send_ir - Sending IR code to output {output}: {code[:50]}...")

        # Simulate transmission
        def reset_state():
            time.sleep(0.2)
            OUTPUT_STATES[output] = "idle"

        threading.Thread(target=reset_state, daemon=True).start()

        self._send_json(200, {"success": True})

    def _handle_test_output(self, data):
        """Handle /test_output endpoint."""
        output = data.get("output")
        duration_ms = data.get("duration_ms", 500)

        if not output:
            self._send_json(400, {"error": "Missing output"})
            return

        # Check port is configured as output
        port_config = PORT_CONFIGS.get(output, {})
        if port_config.get("mode") != "ir_output":
            self._send_json(400, {"error": f"Port {output} is not configured as output"})
            return

        OUTPUT_STATES[output] = "testing"
        _LOGGER.info(f"POST /test_output - Testing output {output} for {duration_ms}ms")

        # Simulate test signal
        def reset_state():
            time.sleep(duration_ms / 1000.0)
            OUTPUT_STATES[output] = "idle"

        threading.Thread(target=reset_state, daemon=True).start()

        self._send_json(200, {"success": True})

    def _handle_start_learning(self, data):
        """Handle /learning/start endpoint - start IR learning mode."""
        port = data.get("port", 1)
        timeout = data.get("timeout", 10)

        # Check port is configured as input
        port_config = PORT_CONFIGS.get(port, {})
        if port_config.get("mode") != "ir_input":
            self._send_json(400, {"error": f"Port {port} is not configured as input"})
            return

        LEARNING_STATE["active"] = True
        LEARNING_STATE["port"] = port
        LEARNING_STATE["timeout"] = timeout
        LEARNING_STATE["start_time"] = time.time()
        LEARNING_STATE["received_code"] = None

        _LOGGER.info(f"POST /learning/start - Started learning on port {port}, timeout {timeout}s")

        # Auto-timeout learning mode
        def auto_timeout():
            time.sleep(timeout)
            if LEARNING_STATE["active"] and LEARNING_STATE["start_time"]:
                if time.time() - LEARNING_STATE["start_time"] >= timeout:
                    LEARNING_STATE["active"] = False
                    _LOGGER.info("Learning mode timed out")

        threading.Thread(target=auto_timeout, daemon=True).start()

        self._send_json(200, {"success": True, "port": port, "timeout": timeout})

    def _handle_stop_learning(self):
        """Handle /learning/stop endpoint - stop IR learning mode."""
        was_active = LEARNING_STATE["active"]
        LEARNING_STATE["active"] = False
        LEARNING_STATE["port"] = None
        LEARNING_STATE["received_code"] = None

        _LOGGER.info(f"POST /learning/stop - Stopped learning (was_active={was_active})")
        self._send_json(200, {"success": True})

    def _handle_learning_status(self):
        """Handle /learning/status endpoint - get learning status."""
        response = {
            "active": LEARNING_STATE["active"],
            "port": LEARNING_STATE["port"],
            "received_code": LEARNING_STATE["received_code"],
            "elapsed_seconds": (
                time.time() - LEARNING_STATE["start_time"]
                if LEARNING_STATE["start_time"] and LEARNING_STATE["active"]
                else 0
            ),
        }
        self._send_json(200, response)

    def _handle_receive_ir(self, data):
        """Handle /learning/receive endpoint - simulate receiving an IR code.

        In real firmware, this would be triggered by the IR receiver.
        For testing, we can call this endpoint to simulate a button press.
        """
        if not LEARNING_STATE["active"]:
            self._send_json(400, {"error": "Learning mode not active"})
            return

        # If code provided in request, use it; otherwise generate random one
        if "code" in data:
            received = {
                "protocol": data.get("protocol", "raw"),
                "code": data["code"],
                "raw": data.get("raw", data["code"]),
            }
        else:
            # Simulate receiving a random IR code
            received = random.choice(SIMULATED_IR_CODES).copy()

        LEARNING_STATE["received_code"] = received
        LEARNING_STATE["active"] = False

        _LOGGER.info(f"IR Code Received: {received['protocol']} - {received['code']}")
        self._send_json(200, {
            "success": True,
            "code": received,
        })

    def _send_json(self, status_code, data):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        body = json.dumps(data).encode()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_server(host="0.0.0.0", port=8080):
    """Run the mock board server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, MockBoardHandler)

    _LOGGER.info(f"Mock IR Board running on http://{host}:{port}")
    _LOGGER.info(f"Board MAC: {BOARD_STATE['mac_address']}")
    _LOGGER.info(f"\nEndpoints:")
    _LOGGER.info(f"  GET  /info              - Board information")
    _LOGGER.info(f"  GET  /status            - Board status")
    _LOGGER.info(f"  GET  /ports             - Port configurations")
    _LOGGER.info(f"  POST /adopt             - Adopt board")
    _LOGGER.info(f"  POST /ports/configure   - Configure a port")
    _LOGGER.info(f"  POST /send_ir           - Send IR code")
    _LOGGER.info(f"  POST /test_output       - Test output")
    _LOGGER.info(f"  POST /learning/start    - Start IR learning")
    _LOGGER.info(f"  POST /learning/stop     - Stop IR learning")
    _LOGGER.info(f"  GET  /learning/status   - Get learning status")
    _LOGGER.info(f"  POST /learning/receive  - Simulate IR receive (for testing)")
    _LOGGER.info(f"\nTest commands:")
    _LOGGER.info(f"  curl http://localhost:{port}/info")
    _LOGGER.info(f"  curl -X POST http://localhost:{port}/learning/start -H 'Content-Type: application/json' -d '{{\"port\": 1, \"timeout\": 10}}'")
    _LOGGER.info(f"  curl -X POST http://localhost:{port}/learning/receive -H 'Content-Type: application/json' -d '{{}}'")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _LOGGER.info("Shutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    run_server()
