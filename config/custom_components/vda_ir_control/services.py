"""Service handlers for VDA IR Control integration."""

import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import VDAIRBoardCoordinator, VDAIRDiscoveryCoordinator
from .device_types import DeviceType, get_commands_for_device_type
from .models import DeviceProfile, ControlledDevice
from .storage import get_storage

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
})

DELETE_DEVICE_SCHEMA = vol.Schema({
    vol.Required("device_id"): str,
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

        # Verify profile exists
        profile = await storage.async_get_profile(call.data["profile_id"])
        if profile is None:
            raise ServiceValidationError(f"Profile '{call.data['profile_id']}' not found")

        device = ControlledDevice(
            device_id=call.data["device_id"],
            name=call.data["name"],
            location=call.data.get("location", ""),
            device_profile_id=call.data["profile_id"],
            board_id=call.data["board_id"],
            output_port=call.data["output_port"],
        )

        await storage.async_save_device(device)
        _LOGGER.info("Created device: %s", device.device_id)

        return {"success": True, "device_id": device.device_id}

    async def handle_delete_device(call: ServiceCall) -> Dict[str, Any]:
        """Handle delete_device service."""
        storage = get_storage(hass)
        device_id = call.data["device_id"]

        await storage.async_delete_device(device_id)
        _LOGGER.info("Deleted device: %s", device_id)

        return {"success": True}

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

        # Get profile
        profile = await storage.async_get_profile(device.device_profile_id)
        if profile is None:
            raise ServiceValidationError(f"Profile '{device.device_profile_id}' not found")

        # Get IR code
        ir_code = profile.get_code(command)
        if ir_code is None:
            raise ServiceValidationError(f"Command '{command}' not found in profile")

        # Get coordinator and send
        coordinator = _get_board_coordinator(device.board_id)
        if coordinator is None:
            raise ServiceValidationError(f"Board '{device.board_id}' not found")

        success = await coordinator.send_ir_code(device.output_port, ir_code.raw_code)

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

    _LOGGER.info("VDA IR Control services registered")
