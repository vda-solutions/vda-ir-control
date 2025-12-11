"""REST API endpoints for VDA IR Control."""

import logging
from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .storage import get_storage
from .device_types import (
    get_commands_for_device_type,
    DeviceType,
    ESP32_POE_ISO_PINS,
    ESP32_POE_ISO_RESERVED,
    get_available_ir_pins,
)

_LOGGER = logging.getLogger(__name__)


class VDAIRBoardsView(HomeAssistantView):
    """API endpoint for boards."""

    url = "/api/vda_ir_control/boards"
    name = "api:vda_ir_control:boards"
    requires_auth = True

    async def get(self, request):
        """Get all configured boards."""
        hass = request.app["hass"]
        boards = []

        for entry_id, coord in hass.data.get(DOMAIN, {}).items():
            if entry_id == "storage":
                continue
            if hasattr(coord, "board_id"):
                boards.append({
                    "board_id": coord.board_id,
                    "board_name": coord.board_info.get("board_name", coord.board_id),
                    "ip_address": coord.ip_address,
                    "mac_address": coord.mac_address,
                    "firmware_version": coord.board_info.get("firmware_version", "Unknown"),
                    "output_count": len(coord.ir_outputs),
                    "online": True,  # If we have a coordinator, it's online
                })

        return self.json({
            "boards": boards,
            "total": len(boards),
        })


class VDAIRProfilesView(HomeAssistantView):
    """API endpoint for profiles."""

    url = "/api/vda_ir_control/profiles"
    name = "api:vda_ir_control:profiles"
    requires_auth = True

    async def get(self, request):
        """Get all profiles."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        profiles = await storage.async_get_all_profiles()

        return self.json({
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
        })


class VDAIRProfileView(HomeAssistantView):
    """API endpoint for a single profile."""

    url = "/api/vda_ir_control/profiles/{profile_id}"
    name = "api:vda_ir_control:profile"
    requires_auth = True

    async def get(self, request, profile_id):
        """Get a single profile."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        profile = await storage.async_get_profile(profile_id)

        if profile is None:
            return self.json({"error": "Profile not found"}, status_code=404)

        return self.json({
            "profile_id": profile.profile_id,
            "name": profile.name,
            "device_type": profile.device_type.value,
            "manufacturer": profile.manufacturer,
            "model": profile.model,
            "codes": {cmd: code.to_dict() for cmd, code in profile.codes.items()},
            "learned_commands": profile.get_learned_commands(),
            "available_commands": get_commands_for_device_type(profile.device_type),
        })


class VDAIRDevicesView(HomeAssistantView):
    """API endpoint for devices."""

    url = "/api/vda_ir_control/devices"
    name = "api:vda_ir_control:devices"
    requires_auth = True

    async def get(self, request):
        """Get all devices."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        devices = await storage.async_get_all_devices()

        return self.json({
            "devices": [d.to_dict() for d in devices],
            "total": len(devices),
        })


class VDAIRPortsView(HomeAssistantView):
    """API endpoint for board ports."""

    url = "/api/vda_ir_control/ports/{board_id}"
    name = "api:vda_ir_control:ports"
    requires_auth = True

    async def get(self, request, board_id):
        """Get ports for a board."""
        hass = request.app["hass"]

        # Find the coordinator for this board
        coordinator = None
        for entry_id, coord in hass.data.get(DOMAIN, {}).items():
            if entry_id == "storage":
                continue
            if hasattr(coord, "board_id") and coord.board_id == board_id:
                coordinator = coord
                break

        if coordinator is None:
            return self.json({"error": "Board not found"}, status_code=404)

        # Fetch ports from board
        session = async_get_clientsession(hass)
        try:
            async with session.get(f"{coordinator.base_url}/ports", timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self.json(data)
                else:
                    return self.json({"error": "Failed to get ports"}, status_code=resp.status)
        except Exception as err:
            _LOGGER.error("Failed to get ports: %s", err)
            return self.json({"error": str(err)}, status_code=500)


class VDAIRCommandsView(HomeAssistantView):
    """API endpoint for device type commands."""

    url = "/api/vda_ir_control/commands/{device_type}"
    name = "api:vda_ir_control:commands"
    requires_auth = True

    async def get(self, request, device_type):
        """Get commands for a device type."""
        try:
            dt = DeviceType(device_type)
            commands = get_commands_for_device_type(dt)
            return self.json({
                "device_type": device_type,
                "commands": commands,
            })
        except ValueError:
            return self.json({"error": "Invalid device type"}, status_code=400)


class VDAIRLearningStatusView(HomeAssistantView):
    """API endpoint for learning status."""

    url = "/api/vda_ir_control/learning/{board_id}"
    name = "api:vda_ir_control:learning"
    requires_auth = True

    async def get(self, request, board_id):
        """Get learning status for a board."""
        hass = request.app["hass"]

        # Find the coordinator for this board
        coordinator = None
        for entry_id, coord in hass.data.get(DOMAIN, {}).items():
            if entry_id == "storage":
                continue
            if hasattr(coord, "board_id") and coord.board_id == board_id:
                coordinator = coord
                break

        if coordinator is None:
            return self.json({"error": "Board not found"}, status_code=404)

        # Fetch learning status from board
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

                    return self.json(status)
                else:
                    return self.json({"error": "Failed to get status"}, status_code=resp.status)
        except Exception as err:
            _LOGGER.error("Failed to get learning status: %s", err)
            return self.json({"error": str(err)}, status_code=500)


class VDAIRGPIOPinsView(HomeAssistantView):
    """API endpoint for GPIO pin information."""

    url = "/api/vda_ir_control/gpio_pins"
    name = "api:vda_ir_control:gpio_pins"
    requires_auth = True

    async def get(self, request):
        """Get all available GPIO pins for ESP32-POE-ISO."""
        # Get query params for filtering
        for_input = request.query.get("for_input", "").lower() == "true"
        for_output = request.query.get("for_output", "").lower() == "true"

        if for_input or for_output:
            pins = get_available_ir_pins(for_input=for_input, for_output=for_output)
        else:
            pins = list(ESP32_POE_ISO_PINS.values())

        return self.json({
            "pins": [
                {
                    "gpio": p.gpio,
                    "name": p.name,
                    "can_input": p.can_input,
                    "can_output": p.can_output,
                    "notes": p.notes,
                    "ir_capable": p.ir_capable,
                }
                for p in sorted(pins, key=lambda x: x.gpio)
            ],
            "reserved": [
                {
                    "gpio": gpio,
                    "reason": reason,
                }
                for gpio, reason in sorted(ESP32_POE_ISO_RESERVED.items())
            ],
            "total_available": len(pins),
            "total_reserved": len(ESP32_POE_ISO_RESERVED),
        })


class VDAIRPortAssignmentsView(HomeAssistantView):
    """API endpoint for port assignments (which devices use which ports)."""

    url = "/api/vda_ir_control/port_assignments/{board_id}"
    name = "api:vda_ir_control:port_assignments"
    requires_auth = True

    async def get(self, request, board_id):
        """Get port assignments for a board."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        devices = await storage.async_get_all_devices()

        # Build port assignment map
        assignments = {}
        for device in devices:
            if device.board_id == board_id:
                port = device.output_port
                if port not in assignments:
                    assignments[port] = []
                assignments[port].append({
                    "device_id": device.device_id,
                    "name": device.name,
                    "profile_id": device.profile_id,
                    "location": device.location,
                })

        return self.json({
            "board_id": board_id,
            "assignments": assignments,
        })


async def async_setup_api(hass: HomeAssistant) -> None:
    """Set up the REST API."""
    hass.http.register_view(VDAIRBoardsView())
    hass.http.register_view(VDAIRProfilesView())
    hass.http.register_view(VDAIRProfileView())
    hass.http.register_view(VDAIRDevicesView())
    hass.http.register_view(VDAIRPortsView())
    hass.http.register_view(VDAIRCommandsView())
    hass.http.register_view(VDAIRLearningStatusView())
    hass.http.register_view(VDAIRGPIOPinsView())
    hass.http.register_view(VDAIRPortAssignmentsView())
    _LOGGER.info("VDA IR Control REST API registered")
