"""Coordinator for bidirectional network device communication."""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .device_types import CommandFormat, LineEnding
from .models import (
    NetworkDevice,
    NetworkConfig,
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


class NetworkDeviceCoordinator(DataUpdateCoordinator[DeviceState]):
    """Coordinator for bidirectional TCP/UDP device communication."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: NetworkDevice,
    ) -> None:
        """Initialize the network device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"VDA Network Device {device.name}",
            update_interval=timedelta(seconds=30),
        )
        self._device = device
        self._config = device.network_config
        self._device_state = DeviceState()

        # TCP connection
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

        # UDP socket
        self._udp_transport: Optional[asyncio.DatagramTransport] = None
        self._udp_protocol: Optional["UDPProtocol"] = None

        # State change listeners (for entities)
        self._state_listeners: List[Callable[[str, Any], None]] = []

        # Connection state
        self._connected = False
        self._connecting = False
        self._shutdown = False

        # Response buffer for collecting partial responses
        self._response_buffer = b""

        # Pending response future for synchronous command/response
        self._pending_response: Optional[asyncio.Future] = None

    @property
    def device(self) -> NetworkDevice:
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
            if self._config.protocol == "tcp":
                return await self._connect_tcp()
            else:
                return await self._connect_udp()
        finally:
            self._connecting = False

    async def _connect_tcp(self) -> bool:
        """Establish TCP connection."""
        try:
            _LOGGER.info(
                "Connecting to %s:%d via TCP",
                self._config.host,
                self._config.port,
            )

            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._config.host,
                    self._config.port,
                ),
                timeout=self._config.timeout,
            )

            self._connected = True
            self._device_state.connected = True
            self._device_state.last_updated = datetime.now()

            # Start background listener for responses
            if self._config.persistent_connection:
                self._listen_task = asyncio.create_task(self._listen_tcp())

            _LOGGER.info("Connected to %s:%d", self._config.host, self._config.port)
            self._notify_state_change("connected", True)
            return True

        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout connecting to %s:%d",
                self._config.host,
                self._config.port,
            )
            return False
        except OSError as err:
            _LOGGER.error(
                "Failed to connect to %s:%d: %s",
                self._config.host,
                self._config.port,
                err,
            )
            return False

    async def _connect_udp(self) -> bool:
        """Establish UDP connection."""
        try:
            _LOGGER.info(
                "Setting up UDP for %s:%d",
                self._config.host,
                self._config.port,
            )

            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self),
                remote_addr=(self._config.host, self._config.port),
            )

            self._udp_transport = transport
            self._udp_protocol = protocol
            self._connected = True
            self._device_state.connected = True
            self._device_state.last_updated = datetime.now()

            _LOGGER.info("UDP ready for %s:%d", self._config.host, self._config.port)
            self._notify_state_change("connected", True)
            return True

        except OSError as err:
            _LOGGER.error(
                "Failed to setup UDP for %s:%d: %s",
                self._config.host,
                self._config.port,
                err,
            )
            return False

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

        # Close TCP connection
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

        # Close UDP transport
        if self._udp_transport:
            self._udp_transport.close()
            self._udp_transport = None
            self._udp_protocol = None

        self._connected = False
        self._device_state.connected = False
        self._device_state.last_updated = datetime.now()
        self._notify_state_change("connected", False)
        _LOGGER.info("Disconnected from %s", self._device.name)

    async def _listen_tcp(self) -> None:
        """Background task to listen for TCP responses."""
        _LOGGER.debug("Starting TCP listener for %s", self._device.name)

        while not self._shutdown and self._reader:
            try:
                # Read data with timeout
                data = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=60.0,  # Keep-alive timeout
                )

                if not data:
                    # Connection closed by remote
                    _LOGGER.warning("Connection closed by %s", self._device.name)
                    break

                await self._handle_received_data(data)

            except asyncio.TimeoutError:
                # No data received, connection still alive
                continue
            except asyncio.CancelledError:
                _LOGGER.debug("TCP listener cancelled for %s", self._device.name)
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
            while not self._shutdown and not self._connected:
                _LOGGER.info(
                    "Attempting to reconnect to %s in %d seconds",
                    self._device.name,
                    self._config.reconnect_interval,
                )
                await asyncio.sleep(self._config.reconnect_interval)

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
            if self._config.protocol == "tcp":
                return await self._send_tcp(payload, wait_for_response, response_timeout)
            else:
                return await self._send_udp(payload, wait_for_response, response_timeout)
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

    async def _send_tcp(
        self,
        payload: bytes,
        wait_for_response: bool,
        timeout: float,
    ) -> Optional[str]:
        """Send command via TCP."""
        if not self._writer:
            raise ConnectionError("TCP connection not established")

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

    async def _send_udp(
        self,
        payload: bytes,
        wait_for_response: bool,
        timeout: float,
    ) -> Optional[str]:
        """Send command via UDP."""
        if not self._udp_transport:
            raise ConnectionError("UDP transport not established")

        # Set up response future if waiting
        if wait_for_response:
            self._pending_response = asyncio.Future()

        try:
            self._udp_transport.sendto(payload)

            if wait_for_response and self._pending_response:
                try:
                    return await asyncio.wait_for(self._pending_response, timeout)
                except asyncio.TimeoutError:
                    _LOGGER.warning("Timeout waiting for response from %s", self._device.name)
                    return None

            return None

        finally:
            self._pending_response = None

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


class UDPProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for network devices."""

    def __init__(self, coordinator: NetworkDeviceCoordinator) -> None:
        """Initialize the UDP protocol."""
        self._coordinator = coordinator

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        """Handle received UDP datagram."""
        asyncio.create_task(self._coordinator._handle_received_data(data))

    def error_received(self, exc: Exception) -> None:
        """Handle UDP error."""
        _LOGGER.error("UDP error: %s", exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection lost."""
        if exc:
            _LOGGER.warning("UDP connection lost: %s", exc)


def get_network_coordinator(
    hass: HomeAssistant,
    device_id: str,
) -> Optional[NetworkDeviceCoordinator]:
    """Get the coordinator for a network device."""
    coordinators = hass.data.get(DOMAIN, {}).get("network_coordinators", {})
    return coordinators.get(device_id)


async def async_setup_network_coordinator(
    hass: HomeAssistant,
    device: NetworkDevice,
) -> NetworkDeviceCoordinator:
    """Set up a network device coordinator."""
    coordinator = NetworkDeviceCoordinator(hass, device)

    # Store in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("network_coordinators", {})
    hass.data[DOMAIN]["network_coordinators"][device.device_id] = coordinator

    # Connect to device
    await coordinator.async_connect()

    return coordinator


async def async_remove_network_coordinator(
    hass: HomeAssistant,
    device_id: str,
) -> None:
    """Remove and disconnect a network device coordinator."""
    coordinators = hass.data.get(DOMAIN, {}).get("network_coordinators", {})
    coordinator = coordinators.pop(device_id, None)

    if coordinator:
        await coordinator.async_disconnect()
