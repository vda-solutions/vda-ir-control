"""Coordinator for bidirectional serial device communication."""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .device_types import CommandFormat, LineEnding
from .models import (
    SerialDevice,
    SerialConfig,
    DeviceCommand,
    DeviceState,
    ResponsePattern,
)

_LOGGER = logging.getLogger(__name__)

# Line ending mappings
LINE_ENDINGS = {
    LineEnding.NONE: b"",
    LineEnding.CR: b"\r",
    LineEnding.LF: b"\n",
    LineEnding.CRLF: b"\r\n",
    LineEnding.EXCLAMATION: b"!",
}


class SerialDeviceCoordinator(DataUpdateCoordinator[DeviceState]):
    """Coordinator for bidirectional serial device communication.

    Supports two modes:
    1. Direct serial - Using pyserial-asyncio to communicate with local serial ports
    2. ESP32 Bridge - Using HTTP API to send/receive serial data via ESP32 board
    """

    def __init__(
        self,
        hass: HomeAssistant,
        device: SerialDevice,
    ) -> None:
        """Initialize the serial device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"VDA Serial Device {device.name}",
            update_interval=timedelta(seconds=30),
        )
        self._device = device
        self._config = device.serial_config
        self._device_state = DeviceState()
        self._is_bridge_mode = bool(device.bridge_board_id)

        # Direct serial connection
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

        # State change listeners (for entities)
        self._state_listeners: List[Callable[[str, Any], None]] = []

        # Connection state
        self._connected = False
        self._connecting = False
        self._shutdown = False

        # Pending response future for synchronous command/response
        self._pending_response: Optional[asyncio.Future] = None

    @property
    def device(self) -> SerialDevice:
        """Return the device configuration."""
        return self._device

    @property
    def device_state(self) -> DeviceState:
        """Return current device state."""
        return self._device_state

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected

    @property
    def is_bridge_mode(self) -> bool:
        """Return True if using ESP32 bridge mode."""
        return self._is_bridge_mode

    def add_state_listener(self, callback_fn: Callable[[str, Any], None]) -> Callable[[], None]:
        """Add a listener for state changes. Returns function to remove listener."""
        self._state_listeners.append(callback_fn)
        return lambda: self._state_listeners.remove(callback_fn)

    async def async_connect(self) -> bool:
        """Establish connection to the device."""
        if self._connecting or self._connected:
            return self._connected

        self._connecting = True
        self._shutdown = False

        try:
            if self._is_bridge_mode:
                return await self._connect_bridge()
            else:
                return await self._connect_direct()
        finally:
            self._connecting = False

    async def _connect_direct(self) -> bool:
        """Establish direct serial connection using pyserial-asyncio."""
        try:
            import serial_asyncio

            _LOGGER.info(
                "Opening serial port %s at %d baud",
                self._config.port,
                self._config.baud_rate,
            )

            # Map parity string to serial constant
            parity_map = {"N": "N", "E": "E", "O": "O", "M": "M", "S": "S"}
            parity = parity_map.get(self._config.parity, "N")

            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self._config.port,
                baudrate=self._config.baud_rate,
                bytesize=self._config.data_bits,
                parity=parity,
                stopbits=self._config.stop_bits,
            )

            self._connected = True
            self._device_state.connected = True
            self._device_state.last_updated = datetime.now()

            # Start background listener for responses
            self._listen_task = asyncio.create_task(self._listen_serial())

            _LOGGER.info("Opened serial port %s", self._config.port)
            self._notify_state_change("connected", True)
            return True

        except ImportError:
            _LOGGER.error(
                "pyserial-asyncio not installed. Install with: pip install pyserial-asyncio"
            )
            return False
        except Exception as err:
            _LOGGER.error("Failed to open serial port %s: %s", self._config.port, err)
            return False

    async def _connect_bridge(self) -> bool:
        """Verify ESP32 bridge is available."""
        try:
            # Get the board coordinator to find the base URL
            board_coordinator = self._get_board_coordinator()
            if not board_coordinator:
                _LOGGER.error("ESP32 board %s not found", self._device.bridge_board_id)
                return False

            # Test connection by configuring the serial port on ESP32
            session = async_get_clientsession(self.hass)
            config_data = {
                "uart": self._config.uart_number,
                "baud": self._config.baud_rate,
                "rx_pin": self._config.rx_pin,
                "tx_pin": self._config.tx_pin,
            }

            async with session.post(
                f"{board_coordinator.base_url}/serial/config",
                json=config_data,
                timeout=5,
            ) as resp:
                if resp.status == 200:
                    self._connected = True
                    self._device_state.connected = True
                    self._device_state.last_updated = datetime.now()
                    _LOGGER.info(
                        "Connected to serial device via ESP32 bridge %s",
                        self._device.bridge_board_id,
                    )
                    self._notify_state_change("connected", True)
                    return True
                else:
                    _LOGGER.error(
                        "Failed to configure ESP32 serial: %s",
                        await resp.text(),
                    )
                    return False

        except Exception as err:
            _LOGGER.error("Failed to connect via ESP32 bridge: %s", err)
            return False

    def _get_board_coordinator(self):
        """Get the board coordinator for bridge mode."""
        for entry_id, coord in self.hass.data.get(DOMAIN, {}).items():
            if entry_id in ("storage", "network_coordinators", "serial_coordinators"):
                continue
            if hasattr(coord, "board_id") and coord.board_id == self._device.bridge_board_id:
                return coord
        return None

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""
        self._shutdown = True

        # Cancel listener task
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        # Cancel reconnect task
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        # Close serial connection
        if self._writer:
            try:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), timeout=2.0)
            except Exception:
                pass
            self._writer = None
            self._reader = None

        self._connected = False
        self._device_state.connected = False
        self._device_state.last_updated = datetime.now()
        self._notify_state_change("connected", False)
        _LOGGER.info("Disconnected from %s", self._device.name)

    async def _listen_serial(self) -> None:
        """Background task to listen for serial responses (direct mode only)."""
        _LOGGER.debug("Starting serial listener for %s", self._device.name)

        while not self._shutdown and self._reader:
            try:
                # Read data with timeout
                data = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=60.0,
                )

                if data:
                    await self._handle_received_data(data)

            except asyncio.TimeoutError:
                # No data received, connection still alive
                continue
            except asyncio.CancelledError:
                _LOGGER.debug("Serial listener cancelled for %s", self._device.name)
                return
            except Exception as err:
                _LOGGER.error("Error reading from %s: %s", self._device.name, err)
                break

        # Connection lost, attempt reconnect if not shutting down
        if not self._shutdown:
            self._connected = False
            self._device_state.connected = False
            self._notify_state_change("connected", False)
            await self._schedule_reconnect()

    async def _handle_received_data(self, data: bytes) -> None:
        """Handle received data from device."""
        try:
            # Decode the data
            text = data.decode("utf-8", errors="replace").strip()
            if not text:
                return

            _LOGGER.debug("Received from %s: %s", self._device.name, text)

            # Store last response
            self._device_state.last_response = text
            self._device_state.last_updated = datetime.now()

            # If waiting for synchronous response, fulfill it
            if self._pending_response and not self._pending_response.done():
                self._pending_response.set_result(text)

            # Parse response against patterns
            await self._parse_response(text)

            # Trigger coordinator update
            self.async_set_updated_data(self._device_state)

        except Exception as err:
            _LOGGER.error("Error handling data from %s: %s", self._device.name, err)

    async def _parse_response(self, response: str) -> None:
        """Parse device response against registered patterns."""
        # Check global patterns first
        for pattern in self._device.global_response_patterns:
            self._match_pattern(pattern, response)

        # Check command-specific patterns
        for command in self._device.commands.values():
            for pattern in command.response_patterns:
                self._match_pattern(pattern, response)

    def _match_pattern(self, pattern: ResponsePattern, response: str) -> bool:
        """Match a response against a pattern and update state."""
        if not pattern.pattern:
            return False

        try:
            match = re.search(pattern.pattern, response, re.IGNORECASE)
            if match:
                value = match.group(pattern.value_group)

                # Apply value mapping if present
                if pattern.value_map:
                    value = pattern.value_map.get(value, value)

                # Update device state
                self._device_state.update(pattern.state_key, value)

                _LOGGER.debug(
                    "Pattern matched: %s = %s (from %s)",
                    pattern.state_key,
                    value,
                    response,
                )

                # Notify listeners
                self._notify_state_change(pattern.state_key, value)
                return True

        except re.error as err:
            _LOGGER.error("Invalid regex pattern '%s': %s", pattern.pattern, err)
        except IndexError:
            _LOGGER.error(
                "Pattern '%s' matched but group %d not found",
                pattern.pattern,
                pattern.value_group,
            )

        return False

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._shutdown or self._reconnect_task:
            return

        async def reconnect():
            reconnect_interval = getattr(self._config, 'reconnect_interval', 30)
            while not self._shutdown and not self._connected:
                _LOGGER.info(
                    "Attempting to reconnect to %s in %d seconds",
                    self._device.name,
                    reconnect_interval,
                )
                await asyncio.sleep(reconnect_interval)

                if not self._shutdown:
                    if await self.async_connect():
                        _LOGGER.info("Reconnected to %s", self._device.name)
                        break

        self._reconnect_task = asyncio.create_task(reconnect())

    def _notify_state_change(self, key: str, value: Any) -> None:
        """Notify all listeners of a state change."""
        for listener in self._state_listeners:
            try:
                listener(key, value)
            except Exception as err:
                _LOGGER.error("Error in state listener: %s", err)

    async def async_send_command(
        self,
        command: DeviceCommand,
        wait_for_response: bool = False,
        response_timeout: float = 2.0,
    ) -> Optional[str]:
        """Send a command to the device."""
        if not self._connected:
            if not await self.async_connect():
                raise ConnectionError(f"Cannot connect to {self._device.name}")

        # Build the payload
        payload = self._build_payload(command)

        _LOGGER.debug("Sending to %s: %s", self._device.name, payload)

        try:
            if self._is_bridge_mode:
                return await self._send_bridge(payload, wait_for_response, response_timeout)
            else:
                return await self._send_direct(payload, wait_for_response, response_timeout)
        except Exception as err:
            _LOGGER.error("Error sending command to %s: %s", self._device.name, err)
            raise

    def _build_payload(self, command: DeviceCommand) -> bytes:
        """Build the payload bytes from a command."""
        if command.format == CommandFormat.HEX:
            # Convert hex string to bytes
            payload = bytes.fromhex(command.payload.replace(" ", ""))
        else:
            # Text command
            payload = command.payload.encode("utf-8")

        # Add line ending
        line_ending = LINE_ENDINGS.get(command.line_ending, b"")
        return payload + line_ending

    async def _send_direct(
        self,
        payload: bytes,
        wait_for_response: bool,
        timeout: float,
    ) -> Optional[str]:
        """Send command via direct serial connection."""
        if not self._writer:
            raise ConnectionError("Serial connection not established")

        # Set up response future if waiting
        if wait_for_response:
            self._pending_response = asyncio.Future()

        try:
            self._writer.write(payload)
            await self._writer.drain()

            if wait_for_response and self._pending_response:
                try:
                    return await asyncio.wait_for(self._pending_response, timeout)
                except asyncio.TimeoutError:
                    _LOGGER.warning("Timeout waiting for response from %s", self._device.name)
                    return None

            return None

        finally:
            self._pending_response = None

    async def _send_bridge(
        self,
        payload: bytes,
        wait_for_response: bool,
        timeout: float,
    ) -> Optional[str]:
        """Send command via ESP32 bridge."""
        board_coordinator = self._get_board_coordinator()
        if not board_coordinator:
            raise ConnectionError(f"ESP32 board {self._device.bridge_board_id} not found")

        session = async_get_clientsession(self.hass)

        # Convert payload to hex for transmission
        hex_data = payload.hex()

        try:
            async with session.post(
                f"{board_coordinator.base_url}/serial/send",
                json={
                    "data": hex_data,
                    "format": "hex",
                    "timeout": int(timeout * 1000) if wait_for_response else 0,
                },
                timeout=timeout + 2,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    response = result.get("response", "")

                    # Parse response if present
                    if response:
                        await self._handle_received_data(response.encode())

                    return response if wait_for_response else None
                else:
                    error = await resp.text()
                    raise ConnectionError(f"Bridge send failed: {error}")

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout sending via bridge to %s", self._device.name)
            return None

    async def async_send_raw(
        self,
        payload: str,
        format_type: str = "text",
        line_ending: str = "none",
        wait_for_response: bool = False,
        response_timeout: float = 2.0,
    ) -> Optional[str]:
        """Send a raw command string to the device."""
        # Create a temporary command
        cmd = DeviceCommand(
            command_id="_raw",
            name="Raw Command",
            format=CommandFormat(format_type),
            payload=payload,
            line_ending=LineEnding(line_ending),
        )
        return await self.async_send_command(cmd, wait_for_response, response_timeout)

    async def async_query_state(self) -> None:
        """Send all query commands to refresh device state."""
        for command in self._device.get_query_commands():
            try:
                await self.async_send_command(command, wait_for_response=True)
            except Exception as err:
                _LOGGER.error(
                    "Error sending query command %s: %s",
                    command.command_id,
                    err,
                )

    async def _async_update_data(self) -> DeviceState:
        """Fetch data from device (called by coordinator)."""
        # If we have query commands with poll intervals, send them
        for command in self._device.get_query_commands():
            if command.poll_interval > 0:
                try:
                    await self.async_send_command(command, wait_for_response=True)
                except Exception as err:
                    _LOGGER.warning("Error polling %s: %s", command.command_id, err)

        return self._device_state


async def get_available_serial_ports() -> List[Dict[str, Any]]:
    """Get list of available serial ports on the system."""
    try:
        import serial.tools.list_ports

        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                "device": port.device,
                "name": port.name,
                "description": port.description,
                "hwid": port.hwid,
                "manufacturer": port.manufacturer,
                "product": port.product,
                "serial_number": port.serial_number,
                "vid": port.vid,
                "pid": port.pid,
            })
        return ports

    except ImportError:
        _LOGGER.warning("pyserial not installed, cannot enumerate ports")
        return []
    except Exception as err:
        _LOGGER.error("Error enumerating serial ports: %s", err)
        return []


def get_serial_coordinator(
    hass: HomeAssistant,
    device_id: str,
) -> Optional[SerialDeviceCoordinator]:
    """Get the coordinator for a serial device."""
    coordinators = hass.data.get(DOMAIN, {}).get("serial_coordinators", {})
    return coordinators.get(device_id)


async def async_setup_serial_coordinator(
    hass: HomeAssistant,
    device: SerialDevice,
) -> SerialDeviceCoordinator:
    """Set up a serial device coordinator."""
    coordinator = SerialDeviceCoordinator(hass, device)

    # Store in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("serial_coordinators", {})
    hass.data[DOMAIN]["serial_coordinators"][device.device_id] = coordinator

    # Connect to device
    await coordinator.async_connect()

    return coordinator


async def async_remove_serial_coordinator(
    hass: HomeAssistant,
    device_id: str,
) -> None:
    """Remove and disconnect a serial device coordinator."""
    coordinators = hass.data.get(DOMAIN, {}).get("serial_coordinators", {})
    coordinator = coordinators.pop(device_id, None)

    if coordinator:
        await coordinator.async_disconnect()
