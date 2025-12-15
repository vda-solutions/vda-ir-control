"""Service handlers for VDA IR Control integration."""

import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import VDAIRBoardCoordinator, VDAIRDiscoveryCoordinator
from .device_types import DeviceType, TransportType, CommandFormat, LineEnding, get_commands_for_device_type
from .models import (
    DeviceProfile,
    ControlledDevice,
    NetworkDevice,
    NetworkConfig,
    SerialDevice,
    SerialConfig,
    DeviceCommand,
    ResponsePattern,
)
from .storage import get_storage
from .ir_profiles import get_profile_by_id as get_builtin_profile
from .network_coordinator import (
    get_network_coordinator,
    async_setup_network_coordinator,
    async_remove_network_coordinator,
)
from .serial_coordinator import (
    get_serial_coordinator,
    async_setup_serial_coordinator,
    async_remove_serial_coordinator,
    get_available_serial_ports,
)

_LOGGER = logging.getLogger(__name__)

# GPIO range for ESP32-POE-ISO (0-39, though only specific pins are usable)
GPIO_PORT_RANGE = vol.Range(min=0, max=39)

# Service schemas
SEND_IR_CODE_SCHEMA = vol.Schema({
    vol.Required("board_id"): str,
    vol.Required("output"): GPIO_PORT_RANGE,
    vol.Required("code"): str,
})

TEST_OUTPUT_SCHEMA = vol.Schema({
    vol.Required("board_id"): str,
    vol.Required("output"): GPIO_PORT_RANGE,
    vol.Optional("duration_ms", default=500): vol.Range(min=100, max=5000),
})

DISCOVER_BOARDS_SCHEMA = vol.Schema({
    vol.Optional("subnet", default="192.168.1"): str,
})

GET_BOARD_STATUS_SCHEMA = vol.Schema({
    vol.Required("board_id"): str,
})

# Profile management schemas
CREATE_PROFILE_SCHEMA = vol.Schema({
    vol.Required("profile_id"): str,
    vol.Required("name"): str,
    vol.Required("device_type"): vol.In([dt.value for dt in DeviceType]),
    vol.Optional("manufacturer", default=""): str,
    vol.Optional("model", default=""): str,
})

DELETE_PROFILE_SCHEMA = vol.Schema({
    vol.Required("profile_id"): str,
})

GET_COMMANDS_SCHEMA = vol.Schema({
    vol.Required("device_type"): vol.In([dt.value for dt in DeviceType]),
})

LIST_PROFILES_SCHEMA = vol.Schema({})

GET_PROFILE_SCHEMA = vol.Schema({
    vol.Required("profile_id"): str,
})

# IR Learning schemas
START_LEARNING_SCHEMA = vol.Schema({
    vol.Required("board_id"): str,
    vol.Required("profile_id"): str,
    vol.Required("command"): str,
    vol.Optional("port", default=34): GPIO_PORT_RANGE,  # Default to GPIO34 (input-only)
    vol.Optional("timeout", default=10): vol.Range(min=5, max=60),
})

GET_LEARNING_STATUS_SCHEMA = vol.Schema({
    vol.Required("board_id"): str,
})

STOP_LEARNING_SCHEMA = vol.Schema({
    vol.Required("board_id"): str,
})

# Device management schemas
CREATE_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("name"): str,
    vol.Required("profile_id"): str,
    vol.Required("board_id"): str,
    vol.Required("output_port"): GPIO_PORT_RANGE,
    vol.Optional("location", default=""): str,
    # Matrix linking (optional)
    vol.Optional("matrix_device_id"): vol.Any(str, None),
    vol.Optional("matrix_device_type"): vol.Any(vol.In(["network", "serial"]), None),
    vol.Optional("matrix_output"): vol.Any(str, None),
})

DELETE_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
})

UPDATE_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Optional("name"): str,
    vol.Optional("location"): vol.Any(str, None),
    vol.Optional("device_profile_id"): str,
    vol.Optional("board_id"): str,
    vol.Optional("output_port"): GPIO_PORT_RANGE,
    vol.Optional("matrix_device_id"): vol.Any(str, None),
    vol.Optional("matrix_device_type"): vol.Any(vol.In(["network", "serial"]), None),
    vol.Optional("matrix_output"): vol.Any(str, None),
})

LIST_DEVICES_SCHEMA = vol.Schema({})

SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("command"): str,
})

# Port configuration schemas
CONFIGURE_PORT_SCHEMA = vol.Schema({
    vol.Required("board_id"): str,
    vol.Required("port"): GPIO_PORT_RANGE,
    vol.Required("mode"): vol.In(["ir_input", "ir_output", "disabled"]),
    vol.Optional("name", default=""): str,
})

GET_PORTS_SCHEMA = vol.Schema({
    vol.Required("board_id"): str,
})

# ========== Network Device Schemas ==========

CREATE_NETWORK_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("name"): str,
    vol.Required("host"): str,
    vol.Required("port"): vol.Range(min=1, max=65535),
    vol.Optional("protocol", default="tcp"): vol.In(["tcp", "udp"]),
    vol.Optional("device_type", default="custom"): vol.In([dt.value for dt in DeviceType]),
    vol.Optional("location", default=""): str,
    vol.Optional("timeout", default=5.0): float,
    vol.Optional("persistent_connection", default=True): bool,
})

DELETE_NETWORK_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
})

LIST_NETWORK_DEVICES_SCHEMA = vol.Schema({})

GET_NETWORK_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
})

ADD_NETWORK_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("command_id"): str,
    vol.Required("name"): str,
    vol.Required("payload"): str,
    vol.Optional("format", default="text"): vol.In(["text", "hex"]),
    vol.Optional("line_ending", default="none"): vol.In(["none", "cr", "lf", "crlf", "!"]),
    vol.Optional("is_input_option", default=False): bool,
    vol.Optional("input_value", default=""): str,
    vol.Optional("is_query", default=False): bool,
    vol.Optional("response_pattern", default=""): str,
    vol.Optional("response_state_key", default=""): str,
    vol.Optional("poll_interval", default=0.0): float,
})

DELETE_NETWORK_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("command_id"): str,
})

SEND_NETWORK_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("command_id"): str,
    vol.Optional("wait_for_response", default=False): bool,
    vol.Optional("timeout", default=2.0): float,
})

SEND_RAW_NETWORK_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("payload"): str,
    vol.Optional("format", default="text"): vol.In(["text", "hex"]),
    vol.Optional("line_ending", default="none"): vol.In(["none", "cr", "lf", "crlf", "!"]),
    vol.Optional("wait_for_response", default=False): bool,
    vol.Optional("timeout", default=2.0): float,
})

TEST_NETWORK_CONNECTION_SCHEMA = vol.Schema({
    vol.Required("host"): str,
    vol.Required("port"): vol.Range(min=1, max=65535),
    vol.Optional("protocol", default="tcp"): vol.In(["tcp", "udp"]),
    vol.Optional("timeout", default=5.0): float,
})

# ========== Serial Device Schemas ==========

CREATE_SERIAL_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("name"): str,
    # For direct serial
    vol.Optional("port"): str,  # e.g., /dev/ttyUSB0, COM3
    vol.Optional("baud_rate", default=115200): vol.In([9600, 19200, 38400, 57600, 115200, 230400]),
    vol.Optional("data_bits", default=8): vol.In([5, 6, 7, 8]),
    vol.Optional("stop_bits", default=1): vol.In([1, 2]),
    vol.Optional("parity", default="N"): vol.In(["N", "E", "O"]),
    # For ESP32 bridge mode
    vol.Optional("bridge_board_id"): str,
    vol.Optional("uart_number", default=1): vol.In([1, 2]),
    vol.Optional("rx_pin"): vol.Range(min=0, max=39),
    vol.Optional("tx_pin"): vol.Range(min=0, max=39),
    # Common
    vol.Optional("device_type", default="custom"): vol.In([dt.value for dt in DeviceType]),
    vol.Optional("location", default=""): str,
})

DELETE_SERIAL_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
})

LIST_SERIAL_DEVICES_SCHEMA = vol.Schema({})

GET_SERIAL_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
})

LIST_SERIAL_PORTS_SCHEMA = vol.Schema({})

ADD_SERIAL_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("command_id"): str,
    vol.Required("name"): str,
    vol.Required("payload"): str,
    vol.Optional("format", default="text"): vol.In(["text", "hex"]),
    vol.Optional("line_ending", default="none"): vol.In(["none", "cr", "lf", "crlf", "!"]),
    vol.Optional("is_input_option", default=False): bool,
    vol.Optional("input_value", default=""): str,
    vol.Optional("is_query", default=False): bool,
    vol.Optional("response_pattern", default=""): str,
    vol.Optional("response_state_key", default=""): str,
    vol.Optional("poll_interval", default=0.0): float,
})

DELETE_SERIAL_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("command_id"): str,
})

SEND_SERIAL_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("command_id"): str,
    vol.Optional("wait_for_response", default=False): bool,
    vol.Optional("timeout", default=2.0): float,
})

SEND_RAW_SERIAL_COMMAND_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
    vol.Required("payload"): str,
    vol.Optional("format", default="text"): vol.In(["text", "hex"]),
    vol.Optional("line_ending", default="none"): vol.In(["none", "cr", "lf", "crlf", "!"]),
    vol.Optional("wait_for_response", default=False): bool,
    vol.Optional("timeout", default=2.0): float,
})


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register service handlers."""

    def _get_board_coordinator(board_id: str) -> VDAIRBoardCoordinator | None:
        """Get a board coordinator by board_id."""
        data = hass.data.get(DOMAIN, {})
        for coordinator in data.values():
            if isinstance(coordinator, VDAIRBoardCoordinator):
                if coordinator.board_id == board_id:
                    return coordinator
        return None

    # ========== Original Services ==========

    async def handle_send_ir_code(call: ServiceCall) -> None:
        """Handle send IR code service."""
        board_id = call.data["board_id"]
        output = call.data["output"]
        code = call.data["code"]

        coordinator = _get_board_coordinator(board_id)
        if not coordinator:
            raise ServiceValidationError(f"Board '{board_id}' not found")

        success = await coordinator.send_ir_code(output, code)
        if not success:
            raise ServiceValidationError(
                f"Failed to send IR code to {board_id} output {output}"
            )

        _LOGGER.info("Sent IR code to %s output %d", board_id, output)

    async def handle_test_output(call: ServiceCall) -> None:
        """Handle test output service."""
        board_id = call.data["board_id"]
        output = call.data["output"]
        duration_ms = call.data["duration_ms"]

        coordinator = _get_board_coordinator(board_id)
        if not coordinator:
            raise ServiceValidationError(f"Board '{board_id}' not found")

        success = await coordinator.test_output(output, duration_ms)
        if not success:
            raise ServiceValidationError(
                f"Failed to test output {output} on board {board_id}"
            )

        _LOGGER.info("Tested output %d on board %s", output, board_id)

    async def handle_discover_boards(call: ServiceCall) -> Dict[str, Any]:
        """Handle discover boards service."""
        subnet = call.data["subnet"]

        discovery = VDAIRDiscoveryCoordinator(hass)
        boards = await discovery.discover_boards(subnet)

        result = {
            "discovered_boards": [
                {
                    "mac_address": mac,
                    "ip_address": info.get("ip_address"),
                    "board_id": info.get("board_id"),
                    "board_name": info.get("board_name"),
                    "firmware_version": info.get("firmware_version"),
                    "output_count": info.get("output_count"),
                }
                for mac, info in boards.items()
            ],
            "total_found": len(boards),
        }

        _LOGGER.info("Board discovery completed: found %d boards", len(boards))
        return result

    async def handle_get_board_status(call: ServiceCall) -> Dict[str, Any]:
        """Handle get board status service."""
        board_id = call.data["board_id"]

        coordinator = _get_board_coordinator(board_id)
        if not coordinator:
            raise ServiceValidationError(f"Board '{board_id}' not found")

        status = await coordinator.get_board_status()
        if status is None:
            raise ServiceValidationError(f"Failed to get status for board {board_id}")

        return status

    # ========== Profile Management Services ==========

    async def handle_create_profile(call: ServiceCall) -> Dict[str, Any]:
        """Handle create_profile service."""
        storage = get_storage(hass)

        profile = DeviceProfile(
            profile_id=call.data["profile_id"],
            name=call.data["name"],
            device_type=DeviceType(call.data["device_type"]),
            manufacturer=call.data.get("manufacturer", ""),
            model=call.data.get("model", ""),
        )

        await storage.async_save_profile(profile)
        _LOGGER.info("Created profile: %s", profile.profile_id)

        return {
            "success": True,
            "profile_id": profile.profile_id,
            "available_commands": get_commands_for_device_type(profile.device_type),
        }

    async def handle_delete_profile(call: ServiceCall) -> Dict[str, Any]:
        """Handle delete_profile service."""
        storage = get_storage(hass)
        profile_id = call.data["profile_id"]

        await storage.async_delete_profile(profile_id)
        _LOGGER.info("Deleted profile: %s", profile_id)

        return {"success": True}

    async def handle_get_commands(call: ServiceCall) -> Dict[str, Any]:
        """Handle get_commands service - returns available commands for a device type."""
        device_type = DeviceType(call.data["device_type"])
        commands = get_commands_for_device_type(device_type)

        return {
            "device_type": device_type.value,
            "commands": commands,
        }

    async def handle_list_profiles(call: ServiceCall) -> Dict[str, Any]:
        """Handle list_profiles service."""
        storage = get_storage(hass)
        profiles = await storage.async_get_all_profiles()

        return {
            "profiles": [
                {
                    "profile_id": p.profile_id,
                    "name": p.name,
                    "device_type": p.device_type.value,
                    "manufacturer": p.manufacturer,
                    "model": p.model,
                    "learned_commands": p.get_learned_commands(),
                }
                for p in profiles
            ],
            "total": len(profiles),
        }

    async def handle_get_profile(call: ServiceCall) -> Dict[str, Any]:
        """Handle get_profile service."""
        storage = get_storage(hass)
        profile = await storage.async_get_profile(call.data["profile_id"])

        if profile is None:
            raise ServiceValidationError(f"Profile '{call.data['profile_id']}' not found")

        return {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "device_type": profile.device_type.value,
            "manufacturer": profile.manufacturer,
            "model": profile.model,
            "codes": {cmd: code.to_dict() for cmd, code in profile.codes.items()},
            "learned_commands": profile.get_learned_commands(),
            "available_commands": get_commands_for_device_type(profile.device_type),
        }

    # ========== IR Learning Services ==========

    async def handle_start_learning(call: ServiceCall) -> Dict[str, Any]:
        """Handle start_learning service."""
        board_id = call.data["board_id"]
        profile_id = call.data["profile_id"]
        command = call.data["command"]
        port = call.data.get("port", 1)
        timeout = call.data.get("timeout", 10)

        # Verify profile exists
        storage = get_storage(hass)
        profile = await storage.async_get_profile(profile_id)
        if profile is None:
            raise ServiceValidationError(f"Profile '{profile_id}' not found")

        # Get board coordinator
        coordinator = _get_board_coordinator(board_id)
        if coordinator is None:
            raise ServiceValidationError(f"Board '{board_id}' not found")

        # Start learning on board
        session = async_get_clientsession(hass)
        try:
            async with session.post(
                f"{coordinator.base_url}/learning/start",
                json={"port": port, "timeout": timeout},
                timeout=5,
            ) as resp:
                if resp.status == 200:
                    # Store learning context
                    hass.data.setdefault(DOMAIN, {})
                    hass.data[DOMAIN]["learning_context"] = {
                        "board_id": board_id,
                        "profile_id": profile_id,
                        "command": command,
                        "port": port,
                    }
                    _LOGGER.info(
                        "Started learning for %s.%s on board %s port %d",
                        profile_id, command, board_id, port
                    )
                    return {
                        "success": True,
                        "message": f"Press the '{command}' button on your remote...",
                        "profile_id": profile_id,
                        "command": command,
                    }
                else:
                    error = await resp.text()
                    raise ServiceValidationError(f"Failed to start learning: {error}")
        except Exception as err:
            _LOGGER.error("Failed to start learning: %s", err)
            raise ServiceValidationError(f"Failed to start learning: {err}")

    async def handle_get_learning_status(call: ServiceCall) -> Dict[str, Any]:
        """Handle get_learning_status service."""
        board_id = call.data["board_id"]

        coordinator = _get_board_coordinator(board_id)
        if coordinator is None:
            raise ServiceValidationError(f"Board '{board_id}' not found")

        session = async_get_clientsession(hass)
        try:
            async with session.get(f"{coordinator.base_url}/learning/status", timeout=5) as resp:
                if resp.status == 200:
                    status = await resp.json()

                    # If we received a code, save it to the profile
                    if status.get("received_code") and "learning_context" in hass.data.get(DOMAIN, {}):
                        ctx = hass.data[DOMAIN]["learning_context"]
                        if ctx["board_id"] == board_id:
                            storage = get_storage(hass)
                            code_data = status["received_code"]

                            await storage.async_add_ir_code_to_profile(
                                profile_id=ctx["profile_id"],
                                command=ctx["command"],
                                raw_code=code_data.get("raw", code_data.get("code", "")),
                                protocol=code_data.get("protocol", "raw"),
                            )

                            status["saved"] = True
                            status["profile_id"] = ctx["profile_id"]
                            status["command"] = ctx["command"]

                            # Clear learning context
                            del hass.data[DOMAIN]["learning_context"]

                    return status
                else:
                    raise ServiceValidationError("Failed to get learning status")
        except Exception as err:
            _LOGGER.error("Failed to get learning status: %s", err)
            raise ServiceValidationError(f"Failed to get learning status: {err}")

    async def handle_stop_learning(call: ServiceCall) -> Dict[str, Any]:
        """Handle stop_learning service."""
        board_id = call.data["board_id"]

        coordinator = _get_board_coordinator(board_id)
        if coordinator is None:
            raise ServiceValidationError(f"Board '{board_id}' not found")

        session = async_get_clientsession(hass)
        try:
            async with session.post(f"{coordinator.base_url}/learning/stop", timeout=5) as resp:
                if resp.status == 200:
                    # Clear learning context
                    if "learning_context" in hass.data.get(DOMAIN, {}):
                        del hass.data[DOMAIN]["learning_context"]
                    return {"success": True}
                else:
                    raise ServiceValidationError("Failed to stop learning")
        except Exception as err:
            _LOGGER.error("Failed to stop learning: %s", err)
            raise ServiceValidationError(f"Failed to stop learning: {err}")

    # ========== Device Management Services ==========

    async def handle_create_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle create_device service."""
        storage = get_storage(hass)
        profile_id = call.data["profile_id"]

        # Check if it's a built-in profile (prefixed with "builtin:")
        if profile_id.startswith("builtin:"):
            builtin_id = profile_id[8:]  # Remove "builtin:" prefix
            builtin_profile = get_builtin_profile(builtin_id)
            if builtin_profile is None:
                raise ServiceValidationError(f"Built-in profile '{builtin_id}' not found")
            # Use the builtin profile ID as-is
            device_profile_id = profile_id
        else:
            # Verify user profile exists
            profile = await storage.async_get_profile(profile_id)
            if profile is None:
                raise ServiceValidationError(f"Profile '{profile_id}' not found")
            device_profile_id = profile_id

        device = ControlledDevice(
            device_id=call.data["device_id"],
            name=call.data["name"],
            location=call.data.get("location", ""),
            device_profile_id=device_profile_id,
            board_id=call.data["board_id"],
            output_port=call.data["output_port"],
            matrix_device_id=call.data.get("matrix_device_id"),
            matrix_device_type=call.data.get("matrix_device_type"),
            matrix_output=call.data.get("matrix_output"),
        )

        await storage.async_save_device(device)
        _LOGGER.info("Created device: %s", device.device_id)

        # Reload the config entry to create button entities
        for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
            if entry_id == "storage":
                continue
            if hasattr(coordinator, "board_id") and coordinator.board_id == call.data["board_id"]:
                entry = hass.config_entries.async_get_entry(entry_id)
                if entry:
                    await hass.config_entries.async_reload(entry_id)
                    _LOGGER.info("Reloaded config entry to create entities for device: %s", device.device_id)
                break

        return {"success": True, "device_id": device.device_id}

    async def handle_delete_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle delete_device service."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]

        # Get device info before deleting
        device = await storage.async_get_device(device_id)
        board_id = device.board_id if device else None

        await storage.async_delete_device(device_id)
        _LOGGER.info("Deleted device: %s", device_id)

        # Reload the config entry to remove button entities
        if board_id:
            for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
                if entry_id == "storage":
                    continue
                if hasattr(coordinator, "board_id") and coordinator.board_id == board_id:
                    entry = hass.config_entries.async_get_entry(entry_id)
                    if entry:
                        await hass.config_entries.async_reload(entry_id)
                        _LOGGER.info("Reloaded config entry after deleting device: %s", device_id)
                    break

        return {"success": True}

    async def handle_update_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle update_device service - update an existing device."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]

        # Get existing device
        device = await storage.async_get_device(device_id)
        if device is None:
            raise ServiceValidationError(f"Device '{device_id}' not found")

        old_board_id = device.board_id

        # Update fields if provided
        if "name" in call.data:
            device.name = call.data["name"]
        if "location" in call.data:
            device.location = call.data["location"] or ""
        if "device_profile_id" in call.data:
            profile_id = call.data["device_profile_id"]
            # Validate profile exists
            if profile_id.startswith("builtin:"):
                builtin_id = profile_id[8:]
                builtin_profile = get_builtin_profile(builtin_id)
                if builtin_profile is None:
                    raise ServiceValidationError(f"Built-in profile '{builtin_id}' not found")
            else:
                profile = await storage.async_get_profile(profile_id)
                if profile is None:
                    raise ServiceValidationError(f"Profile '{profile_id}' not found")
            device.device_profile_id = profile_id
        if "board_id" in call.data:
            device.board_id = call.data["board_id"]
        if "output_port" in call.data:
            device.output_port = call.data["output_port"]

        # Update matrix link fields
        if "matrix_device_id" in call.data:
            device.matrix_device_id = call.data["matrix_device_id"]
        if "matrix_device_type" in call.data:
            device.matrix_device_type = call.data["matrix_device_type"]
        if "matrix_output" in call.data:
            device.matrix_output = call.data["matrix_output"]

        await storage.async_save_device(device)
        _LOGGER.info("Updated device: %s", device_id)

        # Reload config entry if board changed or to update entities
        board_ids_to_reload = set()
        if old_board_id:
            board_ids_to_reload.add(old_board_id)
        if device.board_id:
            board_ids_to_reload.add(device.board_id)

        for board_id in board_ids_to_reload:
            for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
                if entry_id == "storage":
                    continue
                if hasattr(coordinator, "board_id") and coordinator.board_id == board_id:
                    entry = hass.config_entries.async_get_entry(entry_id)
                    if entry:
                        await hass.config_entries.async_reload(entry_id)
                        _LOGGER.info("Reloaded config entry after updating device: %s", device_id)
                    break

        return {"success": True, "device_id": device_id}

    async def handle_list_devices(call: ServiceCall) -> Dict[str, Any]:
        """Handle list_devices service."""
        storage = get_storage(hass)
        devices = await storage.async_get_all_devices()

        return {
            "devices": [d.to_dict() for d in devices],
            "total": len(devices),
        }

    async def handle_send_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle send_command service - send a command to a device."""
        device_id = call.data["device_id"]
        command = call.data["command"]

        storage = get_storage(hass)

        # Get device
        device = await storage.async_get_device(device_id)
        if device is None:
            raise ServiceValidationError(f"Device '{device_id}' not found")

        # Check if using a built-in profile
        profile_id = device.device_profile_id
        ir_code_data = None
        protocol = None

        if profile_id.startswith("builtin:"):
            builtin_id = profile_id[8:]  # Remove "builtin:" prefix
            builtin_profile = get_builtin_profile(builtin_id)
            if builtin_profile is None:
                raise ServiceValidationError(f"Built-in profile '{builtin_id}' not found")

            # Get IR code from built-in profile
            codes = builtin_profile.get("codes", {})
            if command not in codes:
                raise ServiceValidationError(f"Command '{command}' not found in built-in profile")

            ir_code_data = codes[command]
            protocol = builtin_profile.get("protocol", "NEC")
        else:
            # Get user profile
            profile = await storage.async_get_profile(profile_id)
            if profile is None:
                raise ServiceValidationError(f"Profile '{profile_id}' not found")

            # Get IR code
            ir_code = profile.get_code(command)
            if ir_code is None:
                raise ServiceValidationError(f"Command '{command}' not found in profile")

            ir_code_data = ir_code.raw_code
            protocol = ir_code.protocol

        # Get coordinator and send
        coordinator = _get_board_coordinator(device.board_id)
        if coordinator is None:
            raise ServiceValidationError(f"Board '{device.board_id}' not found")

        success = await coordinator.send_ir_code(device.output_port, ir_code_data, protocol)

        if not success:
            raise ServiceValidationError(f"Failed to send command to device")

        return {"success": True, "device_id": device_id, "command": command}

    # ========== Port Configuration Services ==========

    async def handle_configure_port(call: ServiceCall) -> Dict[str, Any]:
        """Handle configure_port service."""
        board_id = call.data["board_id"]
        port = call.data["port"]
        mode = call.data["mode"]
        name = call.data.get("name", "")

        coordinator = _get_board_coordinator(board_id)
        if coordinator is None:
            raise ServiceValidationError(f"Board '{board_id}' not found")

        session = async_get_clientsession(hass)
        try:
            async with session.post(
                f"{coordinator.base_url}/ports/configure",
                json={"port": port, "mode": mode, "name": name},
                timeout=5,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error = await resp.text()
                    raise ServiceValidationError(f"Failed to configure port: {error}")
        except Exception as err:
            _LOGGER.error("Failed to configure port: %s", err)
            raise ServiceValidationError(f"Failed to configure port: {err}")

    async def handle_get_ports(call: ServiceCall) -> Dict[str, Any]:
        """Handle get_ports service."""
        board_id = call.data["board_id"]

        coordinator = _get_board_coordinator(board_id)
        if coordinator is None:
            raise ServiceValidationError(f"Board '{board_id}' not found")

        session = async_get_clientsession(hass)
        try:
            async with session.get(f"{coordinator.base_url}/ports", timeout=5) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise ServiceValidationError("Failed to get ports")
        except Exception as err:
            _LOGGER.error("Failed to get ports: %s", err)
            raise ServiceValidationError(f"Failed to get ports: {err}")

    # ========== Network Device Services ==========

    async def handle_create_network_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle create_network_device service."""
        storage = get_storage(hass)

        network_config = NetworkConfig(
            host=call.data["host"],
            port=call.data["port"],
            protocol=call.data.get("protocol", "tcp"),
            timeout=call.data.get("timeout", 5.0),
            persistent_connection=call.data.get("persistent_connection", True),
        )

        transport_type = (
            TransportType.NETWORK_TCP
            if network_config.protocol == "tcp"
            else TransportType.NETWORK_UDP
        )

        device = NetworkDevice(
            device_id=call.data["device_id"],
            name=call.data["name"],
            device_type=DeviceType(call.data.get("device_type", "custom")),
            transport_type=transport_type,
            location=call.data.get("location", ""),
            network_config=network_config,
        )

        await storage.async_save_network_device(device)
        _LOGGER.info("Created network device: %s", device.device_id)

        # Setup coordinator and connect
        try:
            coordinator = await async_setup_network_coordinator(hass, device)
            connected = coordinator.is_connected
        except Exception as err:
            _LOGGER.warning("Failed to connect to network device %s: %s", device.device_id, err)
            connected = False

        return {
            "success": True,
            "device_id": device.device_id,
            "connected": connected,
        }

    async def handle_delete_network_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle delete_network_device service."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]

        # Disconnect and remove coordinator
        await async_remove_network_coordinator(hass, device_id)

        # Delete from storage
        await storage.async_delete_network_device(device_id)
        _LOGGER.info("Deleted network device: %s", device_id)

        return {"success": True}

    async def handle_list_network_devices(call: ServiceCall) -> Dict[str, Any]:
        """Handle list_network_devices service."""
        storage = get_storage(hass)
        devices = await storage.async_get_all_network_devices()

        result = []
        for device in devices:
            coordinator = get_network_coordinator(hass, device.device_id)
            result.append({
                "device_id": device.device_id,
                "name": device.name,
                "device_type": device.device_type.value,
                "host": device.network_config.host,
                "port": device.network_config.port,
                "protocol": device.network_config.protocol,
                "location": device.location,
                "connected": coordinator.is_connected if coordinator else False,
                "command_count": len(device.commands),
            })

        return {"devices": result, "total": len(result)}

    async def handle_get_network_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle get_network_device service."""
        storage = get_storage(hass)
        device = await storage.async_get_network_device(call.data["device_id"])

        if device is None:
            raise ServiceValidationError(f"Network device '{call.data['device_id']}' not found")

        coordinator = get_network_coordinator(hass, device.device_id)

        return {
            "device_id": device.device_id,
            "name": device.name,
            "device_type": device.device_type.value,
            "transport_type": device.transport_type.value,
            "location": device.location,
            "network_config": device.network_config.to_dict(),
            "commands": {k: v.to_dict() for k, v in device.commands.items()},
            "connected": coordinator.is_connected if coordinator else False,
            "device_state": coordinator.device_state.to_dict() if coordinator else None,
        }

    async def handle_add_network_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle add_network_command service."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]

        device = await storage.async_get_network_device(device_id)
        if device is None:
            raise ServiceValidationError(f"Network device '{device_id}' not found")

        # Build response patterns if provided
        response_patterns = []
        if call.data.get("response_pattern") and call.data.get("response_state_key"):
            response_patterns.append(ResponsePattern(
                pattern=call.data["response_pattern"],
                state_key=call.data["response_state_key"],
            ))

        command = DeviceCommand(
            command_id=call.data["command_id"],
            name=call.data["name"],
            format=CommandFormat(call.data.get("format", "text")),
            payload=call.data["payload"],
            line_ending=LineEnding(call.data.get("line_ending", "none")),
            is_input_option=call.data.get("is_input_option", False),
            input_value=call.data.get("input_value", ""),
            is_query=call.data.get("is_query", False),
            response_patterns=response_patterns,
            poll_interval=call.data.get("poll_interval", 0.0),
        )

        await storage.async_add_command_to_network_device(device_id, command)
        _LOGGER.info("Added command %s to network device %s", command.command_id, device_id)

        return {"success": True, "command_id": command.command_id}

    async def handle_delete_network_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle delete_network_command service."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]
        command_id = call.data["command_id"]

        success = await storage.async_delete_command_from_network_device(device_id, command_id)
        if not success:
            raise ServiceValidationError(f"Command '{command_id}' not found in device '{device_id}'")

        return {"success": True}

    async def handle_send_network_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle send_network_command service."""
        device_id = call.data["device_id"]
        command_id = call.data["command_id"]
        wait_for_response = call.data.get("wait_for_response", False)
        timeout = call.data.get("timeout", 2.0)

        # Get coordinator
        coordinator = get_network_coordinator(hass, device_id)
        if coordinator is None:
            # Try to load from storage and setup
            storage = get_storage(hass)
            device = await storage.async_get_network_device(device_id)
            if device is None:
                raise ServiceValidationError(f"Network device '{device_id}' not found")
            coordinator = await async_setup_network_coordinator(hass, device)

        # Get command
        command = coordinator.device.get_command(command_id)
        if command is None:
            raise ServiceValidationError(f"Command '{command_id}' not found")

        try:
            response = await coordinator.async_send_command(command, wait_for_response, timeout)
            return {
                "success": True,
                "device_id": device_id,
                "command_id": command_id,
                "response": response,
            }
        except Exception as err:
            raise ServiceValidationError(f"Failed to send command: {err}")

    async def handle_send_raw_network_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle send_raw_network_command service."""
        device_id = call.data["device_id"]
        payload = call.data["payload"]
        format_type = call.data.get("format", "text")
        line_ending = call.data.get("line_ending", "none")
        wait_for_response = call.data.get("wait_for_response", False)
        timeout = call.data.get("timeout", 2.0)

        # Get coordinator
        coordinator = get_network_coordinator(hass, device_id)
        if coordinator is None:
            storage = get_storage(hass)
            device = await storage.async_get_network_device(device_id)
            if device is None:
                raise ServiceValidationError(f"Network device '{device_id}' not found")
            coordinator = await async_setup_network_coordinator(hass, device)

        try:
            response = await coordinator.async_send_raw(
                payload, format_type, line_ending, wait_for_response, timeout
            )
            return {
                "success": True,
                "device_id": device_id,
                "response": response,
            }
        except Exception as err:
            raise ServiceValidationError(f"Failed to send command: {err}")

    async def handle_test_network_connection(call: ServiceCall) -> Dict[str, Any]:
        """Handle test_network_connection service."""
        import asyncio

        host = call.data["host"]
        port = call.data["port"]
        protocol = call.data.get("protocol", "tcp")
        timeout = call.data.get("timeout", 5.0)

        try:
            if protocol == "tcp":
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                return {
                    "success": True,
                    "host": host,
                    "port": port,
                    "protocol": protocol,
                    "message": "TCP connection successful",
                }
            else:
                # UDP - just verify we can create the endpoint
                loop = asyncio.get_event_loop()
                transport, _ = await loop.create_datagram_endpoint(
                    asyncio.DatagramProtocol,
                    remote_addr=(host, port),
                )
                transport.close()
                return {
                    "success": True,
                    "host": host,
                    "port": port,
                    "protocol": protocol,
                    "message": "UDP endpoint created successfully",
                }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "host": host,
                "port": port,
                "protocol": protocol,
                "message": f"Connection timeout after {timeout}s",
            }
        except OSError as err:
            return {
                "success": False,
                "host": host,
                "port": port,
                "protocol": protocol,
                "message": f"Connection failed: {err}",
            }

    # ========== Serial Device Services ==========

    async def handle_list_serial_ports(call: ServiceCall) -> Dict[str, Any]:
        """Handle list_serial_ports service."""
        ports = await get_available_serial_ports()
        return {"ports": ports, "total": len(ports)}

    async def handle_create_serial_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle create_serial_device service."""
        storage = get_storage(hass)

        # Determine transport type
        bridge_board_id = call.data.get("bridge_board_id", "")
        if bridge_board_id:
            transport_type = TransportType.SERIAL_BRIDGE
        else:
            transport_type = TransportType.SERIAL_DIRECT

        serial_config = SerialConfig(
            port=call.data.get("port", ""),
            baud_rate=call.data.get("baud_rate", 115200),
            data_bits=call.data.get("data_bits", 8),
            stop_bits=call.data.get("stop_bits", 1),
            parity=call.data.get("parity", "N"),
            uart_number=call.data.get("uart_number", 1),
            rx_pin=call.data.get("rx_pin", 16),
            tx_pin=call.data.get("tx_pin", 17),
        )

        device = SerialDevice(
            device_id=call.data["device_id"],
            name=call.data["name"],
            device_type=DeviceType(call.data.get("device_type", "custom")),
            transport_type=transport_type,
            location=call.data.get("location", ""),
            serial_config=serial_config,
            bridge_board_id=bridge_board_id,
        )

        await storage.async_save_serial_device(device)
        _LOGGER.info("Created serial device: %s", device.device_id)

        # Setup coordinator and connect
        try:
            coordinator = await async_setup_serial_coordinator(hass, device)
            connected = coordinator.is_connected
        except Exception as err:
            _LOGGER.warning("Failed to connect to serial device %s: %s", device.device_id, err)
            connected = False

        return {
            "success": True,
            "device_id": device.device_id,
            "connected": connected,
        }

    async def handle_delete_serial_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle delete_serial_device service."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]

        # Disconnect and remove coordinator
        await async_remove_serial_coordinator(hass, device_id)

        # Delete from storage
        await storage.async_delete_serial_device(device_id)
        _LOGGER.info("Deleted serial device: %s", device_id)

        return {"success": True}

    async def handle_list_serial_devices(call: ServiceCall) -> Dict[str, Any]:
        """Handle list_serial_devices service."""
        storage = get_storage(hass)
        devices = await storage.async_get_all_serial_devices()

        result = []
        for device in devices:
            coordinator = get_serial_coordinator(hass, device.device_id)
            result.append({
                "device_id": device.device_id,
                "name": device.name,
                "device_type": device.device_type.value,
                "transport_type": device.transport_type.value,
                "port": device.serial_config.port,
                "baud_rate": device.serial_config.baud_rate,
                "bridge_board_id": device.bridge_board_id,
                "location": device.location,
                "connected": coordinator.is_connected if coordinator else False,
                "command_count": len(device.commands),
            })

        return {"devices": result, "total": len(result)}

    async def handle_get_serial_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle get_serial_device service."""
        storage = get_storage(hass)
        device = await storage.async_get_serial_device(call.data["device_id"])

        if device is None:
            raise ServiceValidationError(f"Serial device '{call.data['device_id']}' not found")

        coordinator = get_serial_coordinator(hass, device.device_id)

        return {
            "device_id": device.device_id,
            "name": device.name,
            "device_type": device.device_type.value,
            "transport_type": device.transport_type.value,
            "location": device.location,
            "serial_config": device.serial_config.to_dict(),
            "bridge_board_id": device.bridge_board_id,
            "commands": {k: v.to_dict() for k, v in device.commands.items()},
            "connected": coordinator.is_connected if coordinator else False,
            "device_state": coordinator.device_state.to_dict() if coordinator else None,
        }

    async def handle_add_serial_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle add_serial_command service."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]

        device = await storage.async_get_serial_device(device_id)
        if device is None:
            raise ServiceValidationError(f"Serial device '{device_id}' not found")

        # Build response patterns if provided
        response_patterns = []
        if call.data.get("response_pattern") and call.data.get("response_state_key"):
            response_patterns.append(ResponsePattern(
                pattern=call.data["response_pattern"],
                state_key=call.data["response_state_key"],
            ))

        command = DeviceCommand(
            command_id=call.data["command_id"],
            name=call.data["name"],
            format=CommandFormat(call.data.get("format", "text")),
            payload=call.data["payload"],
            line_ending=LineEnding(call.data.get("line_ending", "none")),
            is_input_option=call.data.get("is_input_option", False),
            input_value=call.data.get("input_value", ""),
            is_query=call.data.get("is_query", False),
            response_patterns=response_patterns,
            poll_interval=call.data.get("poll_interval", 0.0),
        )

        await storage.async_add_command_to_serial_device(device_id, command)
        _LOGGER.info("Added command %s to serial device %s", command.command_id, device_id)

        return {"success": True, "command_id": command.command_id}

    async def handle_delete_serial_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle delete_serial_command service."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]
        command_id = call.data["command_id"]

        success = await storage.async_delete_command_from_serial_device(device_id, command_id)
        if not success:
            raise ServiceValidationError(f"Command '{command_id}' not found in device '{device_id}'")

        return {"success": True}

    async def handle_send_serial_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle send_serial_command service."""
        device_id = call.data["device_id"]
        command_id = call.data["command_id"]
        wait_for_response = call.data.get("wait_for_response", False)
        timeout = call.data.get("timeout", 2.0)

        # Get coordinator
        coordinator = get_serial_coordinator(hass, device_id)
        if coordinator is None:
            # Try to load from storage and setup
            storage = get_storage(hass)
            device = await storage.async_get_serial_device(device_id)
            if device is None:
                raise ServiceValidationError(f"Serial device '{device_id}' not found")
            coordinator = await async_setup_serial_coordinator(hass, device)

        # Get command
        command = coordinator.device.get_command(command_id)
        if command is None:
            raise ServiceValidationError(f"Command '{command_id}' not found")

        try:
            response = await coordinator.async_send_command(command, wait_for_response, timeout)
            return {
                "success": True,
                "device_id": device_id,
                "command_id": command_id,
                "response": response,
            }
        except Exception as err:
            raise ServiceValidationError(f"Failed to send command: {err}")

    async def handle_send_raw_serial_command(call: ServiceCall) -> Dict[str, Any]:
        """Handle send_raw_serial_command service."""
        device_id = call.data["device_id"]
        payload = call.data["payload"]
        format_type = call.data.get("format", "text")
        line_ending = call.data.get("line_ending", "none")
        wait_for_response = call.data.get("wait_for_response", False)
        timeout = call.data.get("timeout", 2.0)

        # Get coordinator
        coordinator = get_serial_coordinator(hass, device_id)
        if coordinator is None:
            storage = get_storage(hass)
            device = await storage.async_get_serial_device(device_id)
            if device is None:
                raise ServiceValidationError(f"Serial device '{device_id}' not found")
            coordinator = await async_setup_serial_coordinator(hass, device)

        try:
            response = await coordinator.async_send_raw(
                payload, format_type, line_ending, wait_for_response, timeout
            )
            return {
                "success": True,
                "device_id": device_id,
                "response": response,
            }
        except Exception as err:
            raise ServiceValidationError(f"Failed to send command: {err}")

    # ========== Register All Services ==========

    # Original services
    hass.services.async_register(
        DOMAIN, "send_ir_code", handle_send_ir_code, schema=SEND_IR_CODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "test_output", handle_test_output, schema=TEST_OUTPUT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "discover_boards", handle_discover_boards,
        schema=DISCOVER_BOARDS_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "get_board_status", handle_get_board_status,
        schema=GET_BOARD_STATUS_SCHEMA, supports_response=SupportsResponse.ONLY
    )

    # Profile management services
    hass.services.async_register(
        DOMAIN, "create_profile", handle_create_profile,
        schema=CREATE_PROFILE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "delete_profile", handle_delete_profile,
        schema=DELETE_PROFILE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "get_commands", handle_get_commands,
        schema=GET_COMMANDS_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "list_profiles", handle_list_profiles,
        schema=LIST_PROFILES_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "get_profile", handle_get_profile,
        schema=GET_PROFILE_SCHEMA, supports_response=SupportsResponse.ONLY
    )

    # IR Learning services
    hass.services.async_register(
        DOMAIN, "start_learning", handle_start_learning,
        schema=START_LEARNING_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "get_learning_status", handle_get_learning_status,
        schema=GET_LEARNING_STATUS_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "stop_learning", handle_stop_learning,
        schema=STOP_LEARNING_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )

    # Device management services
    hass.services.async_register(
        DOMAIN, "create_device", handle_create_device,
        schema=CREATE_DEVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "delete_device", handle_delete_device,
        schema=DELETE_DEVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "update_device", handle_update_device,
        schema=UPDATE_DEVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "list_devices", handle_list_devices,
        schema=LIST_DEVICES_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "send_command", handle_send_command,
        schema=SEND_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )

    # Port configuration services
    hass.services.async_register(
        DOMAIN, "configure_port", handle_configure_port,
        schema=CONFIGURE_PORT_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "get_ports", handle_get_ports,
        schema=GET_PORTS_SCHEMA, supports_response=SupportsResponse.ONLY
    )

    # Network device services
    hass.services.async_register(
        DOMAIN, "create_network_device", handle_create_network_device,
        schema=CREATE_NETWORK_DEVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "delete_network_device", handle_delete_network_device,
        schema=DELETE_NETWORK_DEVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "list_network_devices", handle_list_network_devices,
        schema=LIST_NETWORK_DEVICES_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "get_network_device", handle_get_network_device,
        schema=GET_NETWORK_DEVICE_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "add_network_command", handle_add_network_command,
        schema=ADD_NETWORK_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "delete_network_command", handle_delete_network_command,
        schema=DELETE_NETWORK_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "send_network_command", handle_send_network_command,
        schema=SEND_NETWORK_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "send_raw_network_command", handle_send_raw_network_command,
        schema=SEND_RAW_NETWORK_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "test_network_connection", handle_test_network_connection,
        schema=TEST_NETWORK_CONNECTION_SCHEMA, supports_response=SupportsResponse.ONLY
    )

    # Serial device services
    hass.services.async_register(
        DOMAIN, "list_serial_ports", handle_list_serial_ports,
        schema=LIST_SERIAL_PORTS_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "create_serial_device", handle_create_serial_device,
        schema=CREATE_SERIAL_DEVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "delete_serial_device", handle_delete_serial_device,
        schema=DELETE_SERIAL_DEVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "list_serial_devices", handle_list_serial_devices,
        schema=LIST_SERIAL_DEVICES_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "get_serial_device", handle_get_serial_device,
        schema=GET_SERIAL_DEVICE_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "add_serial_command", handle_add_serial_command,
        schema=ADD_SERIAL_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "delete_serial_command", handle_delete_serial_command,
        schema=DELETE_SERIAL_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "send_serial_command", handle_send_serial_command,
        schema=SEND_SERIAL_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "send_raw_serial_command", handle_send_raw_serial_command,
        schema=SEND_RAW_SERIAL_COMMAND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )

    _LOGGER.info("VDA IR Control services registered")
