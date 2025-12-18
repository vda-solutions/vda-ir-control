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
    TransportType,
    CommandFormat,
    LineEnding,
    ESP32_POE_ISO_PINS,
    ESP32_POE_ISO_RESERVED,
    get_available_ir_pins,
)
from .ir_profiles import (
    get_all_profiles,
    get_profiles_by_type,
    get_profiles_by_manufacturer,
    get_profile_by_id,
    get_available_manufacturers,
    get_available_device_types,
)
from .profile_manager import get_profile_manager
from .models import NetworkDevice, NetworkConfig, SerialDevice, SerialConfig, DeviceCommand, ResponsePattern
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


class VDAIRBuiltinProfilesView(HomeAssistantView):
    """API endpoint for built-in IR profiles."""

    url = "/api/vda_ir_control/builtin_profiles"
    name = "api:vda_ir_control:builtin_profiles"
    requires_auth = True

    async def get(self, request):
        """Get all built-in IR profiles.

        Optional query parameters:
        - device_type: Filter by device type (tv, cable_box, soundbar, streaming)
        - manufacturer: Filter by manufacturer name
        """
        device_type = request.query.get("device_type")
        manufacturer = request.query.get("manufacturer")

        if device_type:
            profiles = get_profiles_by_type(device_type)
        elif manufacturer:
            profiles = get_profiles_by_manufacturer(manufacturer)
        else:
            profiles = get_all_profiles()

        return self.json({
            "profiles": profiles,
            "total": len(profiles),
            "available_device_types": get_available_device_types(),
            "available_manufacturers": get_available_manufacturers(),
        })


class VDAIRBuiltinProfileView(HomeAssistantView):
    """API endpoint for a single built-in IR profile."""

    url = "/api/vda_ir_control/builtin_profiles/{profile_id}"
    name = "api:vda_ir_control:builtin_profile"
    requires_auth = True

    async def get(self, request, profile_id):
        """Get a specific built-in IR profile by ID."""
        profile = get_profile_by_id(profile_id)

        if profile is None:
            return self.json({"error": "Profile not found"}, status_code=404)

        return self.json(profile)


# ============================================================================
# COMMUNITY PROFILE API ENDPOINTS
# ============================================================================


class VDAIRCommunityProfilesView(HomeAssistantView):
    """API endpoint for community IR profiles (synced from GitHub)."""

    url = "/api/vda_ir_control/community_profiles"
    name = "api:vda_ir_control:community_profiles"
    requires_auth = True

    async def get(self, request):
        """Get all cached community profiles.

        Returns profiles synced from the community GitHub repository.
        """
        hass = request.app["hass"]
        manager = get_profile_manager(hass)
        await manager.async_load()

        profiles = manager.get_all_community_profiles()
        status = manager.get_sync_status()

        return self.json({
            "profiles": profiles,
            "total": len(profiles),
            "last_sync": status.get("last_sync"),
            "manifest_version": status.get("manifest_version"),
            "repository_url": status.get("repository_url"),
        })


class VDAIRCommunityProfileView(HomeAssistantView):
    """API endpoint for a single community profile."""

    url = "/api/vda_ir_control/community_profiles/{profile_id}"
    name = "api:vda_ir_control:community_profile"
    requires_auth = True

    async def get(self, request, profile_id):
        """Get a specific community profile by ID."""
        hass = request.app["hass"]
        manager = get_profile_manager(hass)
        await manager.async_load()

        profile = manager.get_community_profile(profile_id)
        if profile is None:
            return self.json({"error": "Profile not found"}, status_code=404)

        return self.json(profile)


class VDAIRSyncProfilesView(HomeAssistantView):
    """API endpoint for syncing community profiles from GitHub."""

    url = "/api/vda_ir_control/sync_profiles"
    name = "api:vda_ir_control:sync_profiles"
    requires_auth = True

    async def post(self, request):
        """Trigger sync of community profiles from GitHub.

        Downloads the manifest and all profiles from the community repository.
        Uses ETag for conditional requests to respect GitHub API rate limits.
        """
        hass = request.app["hass"]
        manager = get_profile_manager(hass)

        _LOGGER.info("Starting community profile sync")
        result = await manager.async_sync_community_profiles()

        if result["success"]:
            _LOGGER.info(
                "Community profile sync completed: %s",
                result["message"]
            )
        else:
            _LOGGER.warning(
                "Community profile sync failed: %s",
                result["message"]
            )

        return self.json(result)

    async def get(self, request):
        """Get sync status without triggering a sync."""
        hass = request.app["hass"]
        manager = get_profile_manager(hass)
        await manager.async_load()

        status = manager.get_sync_status()
        return self.json(status)


class VDAIRExportProfileView(HomeAssistantView):
    """API endpoint for exporting a user profile for contribution."""

    url = "/api/vda_ir_control/export_profile/{profile_id}"
    name = "api:vda_ir_control:export_profile"
    requires_auth = True

    async def get(self, request, profile_id):
        """Export a user profile as JSON for contribution to the community repo.

        Returns the profile formatted according to the community repository schema,
        along with a link to submit a contribution.
        """
        hass = request.app["hass"]
        storage = get_storage(hass)

        profile = await storage.async_get_profile(profile_id)
        if profile is None:
            return self.json({"error": "Profile not found"}, status_code=404)

        manager = get_profile_manager(hass)
        export_result = manager.export_profile_for_contribution(profile.to_dict())

        return self.json({
            "profile_id": profile_id,
            "profile_name": profile.name,
            **export_result,
        })


class VDAIRAllProfilesView(HomeAssistantView):
    """API endpoint for all profiles merged from all sources."""

    url = "/api/vda_ir_control/all_profiles"
    name = "api:vda_ir_control:all_profiles"
    requires_auth = True

    async def get(self, request):
        """Get all profiles from all sources with priority applied.

        Returns profiles from all sources (builtin, community, user) with
        duplicates resolved by priority: user > community > builtin.
        """
        hass = request.app["hass"]
        storage = get_storage(hass)
        manager = get_profile_manager(hass)
        await manager.async_load()

        # Build merged profile dict with priority
        all_profiles = {}

        # 1. Add builtin profiles (lowest priority)
        for profile in manager.get_all_builtin_profiles():
            pid = profile["profile_id"]
            all_profiles[pid] = {
                **profile,
                "_source": "builtin",
                "_prefix": f"builtin:{pid}",
            }

        # 2. Add community profiles (overrides builtin)
        for profile in manager.get_all_community_profiles():
            pid = profile["profile_id"]
            all_profiles[pid] = {
                **profile,
                "_source": "community",
                "_prefix": f"community:{pid}",
            }

        # 3. Add user profiles (highest priority, overrides all)
        user_profiles = await storage.async_get_all_profiles()
        for profile in user_profiles:
            pid = profile.profile_id
            profile_dict = profile.to_dict()
            all_profiles[pid] = {
                **profile_dict,
                "_source": "user",
                "_prefix": pid,  # No prefix for user profiles
            }

        # Get counts by source
        builtin_count = len(manager.get_all_builtin_profiles())
        community_count = len(manager.get_all_community_profiles())
        user_count = len(user_profiles)

        return self.json({
            "profiles": list(all_profiles.values()),
            "total": len(all_profiles),
            "by_source": {
                "builtin": builtin_count,
                "community": community_count,
                "user": user_count,
            },
            "sync_status": manager.get_sync_status(),
        })


# ============================================================================
# NETWORK DEVICE API ENDPOINTS
# ============================================================================


class VDAIRNetworkDevicesView(HomeAssistantView):
    """API endpoint for network devices."""

    url = "/api/vda_ir_control/network_devices"
    name = "api:vda_ir_control:network_devices"
    requires_auth = True

    async def get(self, request):
        """Get all network devices."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        devices = await storage.async_get_all_network_devices()

        result = []
        for device in devices:
            coordinator = get_network_coordinator(hass, device.device_id)
            result.append({
                "device_id": device.device_id,
                "name": device.name,
                "device_type": device.device_type.value,
                "transport_type": device.transport_type.value,
                "host": device.network_config.host,
                "port": device.network_config.port,
                "protocol": device.network_config.protocol,
                "location": device.location,
                "connected": coordinator.is_connected if coordinator else False,
                "command_count": len(device.commands),
            })

        return self.json({
            "devices": result,
            "total": len(result),
        })

    async def post(self, request):
        """Create a new network device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        # Validate required fields
        required = ["device_id", "name", "host", "port"]
        for field in required:
            if field not in data:
                return self.json({"error": f"Missing required field: {field}"}, status_code=400)

        network_config = NetworkConfig(
            host=data["host"],
            port=data["port"],
            protocol=data.get("protocol", "tcp"),
            timeout=data.get("timeout", 5.0),
            persistent_connection=data.get("persistent_connection", True),
        )

        transport_type = (
            TransportType.NETWORK_TCP
            if network_config.protocol == "tcp"
            else TransportType.NETWORK_UDP
        )

        device = NetworkDevice(
            device_id=data["device_id"],
            name=data["name"],
            device_type=DeviceType(data.get("device_type", "custom")),
            transport_type=transport_type,
            location=data.get("location", ""),
            network_config=network_config,
        )

        # If matrix_config is provided, auto-create routing commands
        matrix_config = data.get("matrix_config")
        if matrix_config and data.get("device_type") == "hdmi_matrix":
            inputs = matrix_config.get("inputs", [])
            outputs = matrix_config.get("outputs", [])
            command_template = matrix_config.get("command_template", "")
            line_ending_str = matrix_config.get("line_ending", "crlf")

            # Map line ending string to enum
            line_ending_map = {
                "none": LineEnding.NONE,
                "cr": LineEnding.CR,
                "lf": LineEnding.LF,
                "crlf": LineEnding.CRLF,
            }
            line_ending = line_ending_map.get(line_ending_str, LineEnding.CRLF)

            # If we have a command template, generate routing commands for each input/output combo
            if command_template and "{input}" in command_template and "{output}" in command_template:
                # Generate routing commands: one for each output, each input is an option
                for output_info in outputs:
                    output_idx = output_info.get("index", 1)
                    output_name = output_info.get("name", f"Output {output_idx}")

                    for input_info in inputs:
                        input_idx = input_info.get("index", 1)
                        input_name = input_info.get("name", f"HDMI {input_idx}")

                        # Generate the actual command by replacing placeholders
                        payload = command_template.replace("{input}", str(input_idx)).replace("{output}", str(output_idx))

                        command = DeviceCommand(
                            command_id=f"route_in{input_idx}_out{output_idx}",
                            name=f"{input_name} → {output_name}",
                            format=CommandFormat.TEXT,
                            payload=payload,
                            line_ending=line_ending,
                            is_input_option=True,  # Makes it appear in input selector
                            input_value=str(input_idx),  # The input this command selects
                        )
                        device.add_command(command)

                _LOGGER.info("Created %d routing commands from template for matrix device %s",
                            len(inputs) * len(outputs), device.device_id)
            else:
                # No template - create placeholder input commands (old behavior)
                for input_info in inputs:
                    idx = input_info.get("index", 1)
                    input_name = input_info.get("name", f"HDMI {idx}")
                    command = DeviceCommand(
                        command_id=f"input_{idx}",
                        name=input_name,
                        format=CommandFormat.TEXT,
                        payload=f"input_{idx}",  # Placeholder - user will update with actual command
                        line_ending=LineEnding.NONE,
                        is_input_option=True,
                        input_value=str(idx),
                    )
                    device.add_command(command)

            # Create status query command(s) if provided
            status_template = matrix_config.get("status_command", "")
            if status_template:
                if "{output}" in status_template:
                    # Per-output status queries
                    for output_info in outputs:
                        output_idx = output_info.get("index", 1)
                        output_name = output_info.get("name", f"Output {output_idx}")
                        payload = status_template.replace("{output}", str(output_idx))

                        status_cmd = DeviceCommand(
                            command_id=f"query_status_out{output_idx}",
                            name=f"Query {output_name} Status",
                            format=CommandFormat.TEXT,
                            payload=payload,
                            line_ending=line_ending,
                            is_query=True,
                            state_key=f"output_{output_idx}_status",
                        )
                        device.add_command(status_cmd)
                    _LOGGER.info("Created %d per-output status query commands for matrix device %s",
                                len(outputs), device.device_id)
                else:
                    # Single global status query
                    status_cmd = DeviceCommand(
                        command_id="query_status",
                        name="Query Status",
                        format=CommandFormat.TEXT,
                        payload=status_template,
                        line_ending=line_ending,
                        is_query=True,
                        state_key="matrix_status",
                    )
                    device.add_command(status_cmd)
                    _LOGGER.info("Created global status query command for matrix device %s", device.device_id)

            # Store input/output configuration for matrix routing
            from .models import MatrixInput, MatrixOutput
            device.matrix_inputs = [
                MatrixInput(index=i_info.get("index", i+1), name=i_info.get("name", f"Input {i+1}"))
                for i, i_info in enumerate(inputs)
            ]
            device.matrix_outputs = [
                MatrixOutput(index=o.get("index", i+1), name=o.get("name", f"Output {i+1}"))
                for i, o in enumerate(outputs)
            ]
            _LOGGER.info("Created %d inputs and %d outputs for matrix device %s",
                        len(inputs), len(outputs), device.device_id)

        await storage.async_save_network_device(device)
        _LOGGER.info("Created network device: %s", device.device_id)

        # Setup coordinator
        try:
            coordinator = await async_setup_network_coordinator(hass, device)
            connected = coordinator.is_connected
        except Exception as err:
            _LOGGER.warning("Failed to connect to network device %s: %s", device.device_id, err)
            connected = False

        return self.json({
            "success": True,
            "device_id": device.device_id,
            "connected": connected,
        })


class VDAIRNetworkDeviceView(HomeAssistantView):
    """API endpoint for a single network device."""

    url = "/api/vda_ir_control/network_devices/{device_id}"
    name = "api:vda_ir_control:network_device"
    requires_auth = True

    async def get(self, request, device_id):
        """Get a single network device."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        device = await storage.async_get_network_device(device_id)

        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        coordinator = get_network_coordinator(hass, device.device_id)

        return self.json({
            "device_id": device.device_id,
            "name": device.name,
            "device_type": device.device_type.value,
            "transport_type": device.transport_type.value,
            "location": device.location,
            "network_config": device.network_config.to_dict(),
            "commands": {k: v.to_dict() for k, v in device.commands.items()},
            "global_response_patterns": [p.to_dict() for p in device.global_response_patterns],
            "matrix_inputs": [i.to_dict() for i in device.matrix_inputs],
            "matrix_outputs": [o.to_dict() for o in device.matrix_outputs],
            "connected": coordinator.is_connected if coordinator else False,
            "device_state": coordinator.device_state.to_dict() if coordinator else None,
        })

    async def put(self, request, device_id):
        """Update a network device (matrix I/O assignments)."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        device = await storage.async_get_network_device(device_id)
        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        # Update matrix inputs if provided
        if "matrix_inputs" in data:
            from .models import MatrixInput
            device.matrix_inputs = [
                MatrixInput(
                    index=i.get("index", idx+1),
                    name=i.get("name", ""),
                    device_id=i.get("device_id"),
                )
                for idx, i in enumerate(data["matrix_inputs"])
            ]

        # Update matrix outputs if provided
        if "matrix_outputs" in data:
            from .models import MatrixOutput
            device.matrix_outputs = [
                MatrixOutput(
                    index=o.get("index", idx+1),
                    name=o.get("name", ""),
                    device_id=o.get("device_id"),
                )
                for idx, o in enumerate(data["matrix_outputs"])
            ]

        await storage.async_save_network_device(device)
        _LOGGER.info("Updated network device: %s", device_id)

        return self.json({"success": True})

    async def delete(self, request, device_id):
        """Delete a network device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        # Check device exists
        device = await storage.async_get_network_device(device_id)
        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        # Disconnect and remove coordinator
        await async_remove_network_coordinator(hass, device_id)

        # Delete from storage
        await storage.async_delete_network_device(device_id)
        _LOGGER.info("Deleted network device: %s", device_id)

        return self.json({"success": True})


class VDAIRNetworkDeviceCommandsView(HomeAssistantView):
    """API endpoint for network device commands."""

    url = "/api/vda_ir_control/network_devices/{device_id}/commands"
    name = "api:vda_ir_control:network_device_commands"
    requires_auth = True

    async def get(self, request, device_id):
        """Get all commands for a network device."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        device = await storage.async_get_network_device(device_id)

        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        return self.json({
            "device_id": device_id,
            "commands": {k: v.to_dict() for k, v in device.commands.items()},
            "total": len(device.commands),
        })

    async def post(self, request, device_id):
        """Add a command to a network device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        device = await storage.async_get_network_device(device_id)
        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        # Validate required fields
        required = ["command_id", "name", "payload"]
        for field in required:
            if field not in data:
                return self.json({"error": f"Missing required field: {field}"}, status_code=400)

        # Build response patterns if provided
        response_patterns = []
        if data.get("response_pattern") and data.get("response_state_key"):
            response_patterns.append(ResponsePattern(
                pattern=data["response_pattern"],
                state_key=data["response_state_key"],
                value_group=data.get("value_group", 1),
                value_map=data.get("value_map", {}),
            ))

        command = DeviceCommand(
            command_id=data["command_id"],
            name=data["name"],
            format=CommandFormat(data.get("format", "text")),
            payload=data["payload"],
            line_ending=LineEnding(data.get("line_ending", "none")),
            is_input_option=data.get("is_input_option", False),
            input_value=data.get("input_value", ""),
            is_query=data.get("is_query", False),
            response_patterns=response_patterns,
            poll_interval=data.get("poll_interval", 0.0),
        )

        await storage.async_add_command_to_network_device(device_id, command)
        _LOGGER.info("Added command %s to network device %s", command.command_id, device_id)

        return self.json({"success": True, "command_id": command.command_id})


class VDAIRNetworkDeviceCommandView(HomeAssistantView):
    """API endpoint for a single network device command."""

    url = "/api/vda_ir_control/network_devices/{device_id}/commands/{command_id}"
    name = "api:vda_ir_control:network_device_command"
    requires_auth = True

    async def delete(self, request, device_id, command_id):
        """Delete a command from a network device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        success = await storage.async_delete_command_from_network_device(device_id, command_id)
        if not success:
            return self.json({"error": "Command not found"}, status_code=404)

        return self.json({"success": True})


class VDAIRNetworkDeviceSendView(HomeAssistantView):
    """API endpoint for sending commands to network devices."""

    url = "/api/vda_ir_control/network_devices/{device_id}/send"
    name = "api:vda_ir_control:network_device_send"
    requires_auth = True

    async def post(self, request, device_id):
        """Send a command to a network device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        # Get or setup coordinator
        coordinator = get_network_coordinator(hass, device_id)
        if coordinator is None:
            device = await storage.async_get_network_device(device_id)
            if device is None:
                return self.json({"error": "Device not found"}, status_code=404)
            coordinator = await async_setup_network_coordinator(hass, device)

        wait_for_response = data.get("wait_for_response", False)
        timeout = data.get("timeout", 2.0)

        # Check if sending a named command or raw payload
        if "command_id" in data:
            command = coordinator.device.get_command(data["command_id"])
            if command is None:
                return self.json({"error": "Command not found"}, status_code=404)

            try:
                response = await coordinator.async_send_command(command, wait_for_response, timeout)
                return self.json({
                    "success": True,
                    "command_id": data["command_id"],
                    "response": response,
                })
            except Exception as err:
                return self.json({"error": str(err)}, status_code=500)

        elif "payload" in data:
            # Send raw command
            try:
                response = await coordinator.async_send_raw(
                    data["payload"],
                    data.get("format", "text"),
                    data.get("line_ending", "none"),
                    wait_for_response,
                    timeout,
                )
                return self.json({
                    "success": True,
                    "response": response,
                })
            except Exception as err:
                return self.json({"error": str(err)}, status_code=500)

        else:
            return self.json({"error": "Must provide command_id or payload"}, status_code=400)


class VDAIRNetworkDeviceStateView(HomeAssistantView):
    """API endpoint for network device state."""

    url = "/api/vda_ir_control/network_devices/{device_id}/state"
    name = "api:vda_ir_control:network_device_state"
    requires_auth = True

    async def get(self, request, device_id):
        """Get current state of a network device."""
        hass = request.app["hass"]

        coordinator = get_network_coordinator(hass, device_id)
        if coordinator is None:
            return self.json({"error": "Device not connected"}, status_code=404)

        return self.json({
            "device_id": device_id,
            "connected": coordinator.is_connected,
            "state": coordinator.device_state.to_dict(),
        })


class VDAIRTestConnectionView(HomeAssistantView):
    """API endpoint for testing network connections."""

    url = "/api/vda_ir_control/test_connection"
    name = "api:vda_ir_control:test_connection"
    requires_auth = True

    async def post(self, request):
        """Test a network connection."""
        import asyncio

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        required = ["host", "port"]
        for field in required:
            if field not in data:
                return self.json({"error": f"Missing required field: {field}"}, status_code=400)

        host = data["host"]
        port = data["port"]
        protocol = data.get("protocol", "tcp")
        timeout = data.get("timeout", 5.0)

        try:
            if protocol == "tcp":
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                return self.json({
                    "success": True,
                    "host": host,
                    "port": port,
                    "protocol": protocol,
                    "message": "TCP connection successful",
                })
            else:
                loop = asyncio.get_event_loop()
                transport, _ = await loop.create_datagram_endpoint(
                    asyncio.DatagramProtocol,
                    remote_addr=(host, port),
                )
                transport.close()
                return self.json({
                    "success": True,
                    "host": host,
                    "port": port,
                    "protocol": protocol,
                    "message": "UDP endpoint created successfully",
                })
        except asyncio.TimeoutError:
            return self.json({
                "success": False,
                "host": host,
                "port": port,
                "protocol": protocol,
                "message": f"Connection timeout after {timeout}s",
            })
        except OSError as err:
            return self.json({
                "success": False,
                "host": host,
                "port": port,
                "protocol": protocol,
                "message": f"Connection failed: {err}",
            })


# ============================================================================
# SERIAL DEVICE API ENDPOINTS
# ============================================================================


class VDAIRSerialPortsView(HomeAssistantView):
    """API endpoint for listing available serial ports."""

    url = "/api/vda_ir_control/serial_ports"
    name = "api:vda_ir_control:serial_ports"
    requires_auth = True

    async def get(self, request):
        """Get available serial ports on the system."""
        ports = await get_available_serial_ports()
        return self.json({
            "ports": ports,
            "total": len(ports),
        })


class VDAIRSerialDevicesView(HomeAssistantView):
    """API endpoint for serial devices."""

    url = "/api/vda_ir_control/serial_devices"
    name = "api:vda_ir_control:serial_devices"
    requires_auth = True

    async def get(self, request):
        """Get all serial devices."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        devices = await storage.async_get_all_serial_devices()

        result = []
        for device in devices:
            coordinator = get_serial_coordinator(hass, device.device_id)
            # mode: 'direct' if serial_direct, otherwise 'bridge'
            mode = 'direct' if device.transport_type == TransportType.SERIAL_DIRECT else 'bridge'
            result.append({
                "device_id": device.device_id,
                "name": device.name,
                "device_type": device.device_type.value,
                "transport_type": device.transport_type.value,
                "mode": mode,
                "port": device.serial_config.port,
                "baud_rate": device.serial_config.baud_rate,
                "board_id": device.bridge_board_id,
                "bridge_board_id": device.bridge_board_id,
                "uart_num": device.serial_config.uart_number,
                "location": device.location,
                "connected": coordinator.is_connected if coordinator else False,
                "command_count": len(device.commands),
            })

        return self.json({
            "devices": result,
            "total": len(result),
        })

    async def post(self, request):
        """Create a new serial device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        # Validate required fields
        required = ["device_id", "name"]
        for field in required:
            if field not in data:
                return self.json({"error": f"Missing required field: {field}"}, status_code=400)

        # Must have either port (direct) or bridge_board_id (bridge mode)
        if not data.get("port") and not data.get("bridge_board_id"):
            return self.json({"error": "Must provide either 'port' or 'bridge_board_id'"}, status_code=400)

        # Determine transport type
        bridge_board_id = data.get("bridge_board_id", "")
        if bridge_board_id:
            transport_type = TransportType.SERIAL_BRIDGE
        else:
            transport_type = TransportType.SERIAL_DIRECT

        serial_config = SerialConfig(
            port=data.get("port", ""),
            baud_rate=data.get("baud_rate", 115200),
            data_bits=data.get("data_bits", 8),
            stop_bits=data.get("stop_bits", 1),
            parity=data.get("parity", "N"),
            uart_number=data.get("uart_number", 1),
            rx_pin=data.get("rx_pin", 16),
            tx_pin=data.get("tx_pin", 17),
        )

        device = SerialDevice(
            device_id=data["device_id"],
            name=data["name"],
            device_type=DeviceType(data.get("device_type", "custom")),
            transport_type=transport_type,
            location=data.get("location", ""),
            serial_config=serial_config,
            bridge_board_id=bridge_board_id,
        )

        await storage.async_save_serial_device(device)
        _LOGGER.info("Created serial device: %s", device.device_id)

        # Setup coordinator
        try:
            coordinator = await async_setup_serial_coordinator(hass, device)
            connected = coordinator.is_connected
        except Exception as err:
            _LOGGER.warning("Failed to connect to serial device %s: %s", device.device_id, err)
            connected = False

        return self.json({
            "success": True,
            "device_id": device.device_id,
            "connected": connected,
        })


class VDAIRSerialDeviceView(HomeAssistantView):
    """API endpoint for a single serial device."""

    url = "/api/vda_ir_control/serial_devices/{device_id}"
    name = "api:vda_ir_control:serial_device"
    requires_auth = True

    async def get(self, request, device_id):
        """Get a single serial device."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        device = await storage.async_get_serial_device(device_id)

        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        coordinator = get_serial_coordinator(hass, device.device_id)

        return self.json({
            "device_id": device.device_id,
            "name": device.name,
            "device_type": device.device_type.value,
            "transport_type": device.transport_type.value,
            "location": device.location,
            "serial_config": device.serial_config.to_dict(),
            "bridge_board_id": device.bridge_board_id,
            "commands": {k: v.to_dict() for k, v in device.commands.items()},
            "global_response_patterns": [p.to_dict() for p in device.global_response_patterns],
            "matrix_inputs": [i.to_dict() for i in device.matrix_inputs],
            "matrix_outputs": [o.to_dict() for o in device.matrix_outputs],
            "connected": coordinator.is_connected if coordinator else False,
            "device_state": coordinator.device_state.to_dict() if coordinator else None,
        })

    async def put(self, request, device_id):
        """Update a serial device (matrix I/O assignments)."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        device = await storage.async_get_serial_device(device_id)
        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        # Update matrix inputs if provided
        if "matrix_inputs" in data:
            from .models import MatrixInput
            device.matrix_inputs = [
                MatrixInput(
                    index=i.get("index", idx+1),
                    name=i.get("name", ""),
                    device_id=i.get("device_id"),
                )
                for idx, i in enumerate(data["matrix_inputs"])
            ]

        # Update matrix outputs if provided
        if "matrix_outputs" in data:
            from .models import MatrixOutput
            device.matrix_outputs = [
                MatrixOutput(
                    index=o.get("index", idx+1),
                    name=o.get("name", ""),
                    device_id=o.get("device_id"),
                )
                for idx, o in enumerate(data["matrix_outputs"])
            ]

        await storage.async_save_serial_device(device)
        _LOGGER.info("Updated serial device: %s", device_id)

        return self.json({"success": True})

    async def delete(self, request, device_id):
        """Delete a serial device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        # Check device exists
        device = await storage.async_get_serial_device(device_id)
        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        # Disconnect and remove coordinator
        await async_remove_serial_coordinator(hass, device_id)

        # Delete from storage
        await storage.async_delete_serial_device(device_id)
        _LOGGER.info("Deleted serial device: %s", device_id)

        return self.json({"success": True})


class VDAIRSerialDeviceCommandsView(HomeAssistantView):
    """API endpoint for serial device commands."""

    url = "/api/vda_ir_control/serial_devices/{device_id}/commands"
    name = "api:vda_ir_control:serial_device_commands"
    requires_auth = True

    async def get(self, request, device_id):
        """Get all commands for a serial device."""
        hass = request.app["hass"]
        storage = get_storage(hass)
        device = await storage.async_get_serial_device(device_id)

        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        return self.json({
            "device_id": device_id,
            "commands": {k: v.to_dict() for k, v in device.commands.items()},
            "total": len(device.commands),
        })

    async def post(self, request, device_id):
        """Add a command to a serial device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        device = await storage.async_get_serial_device(device_id)
        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        # Validate required fields
        required = ["command_id", "name", "payload"]
        for field in required:
            if field not in data:
                return self.json({"error": f"Missing required field: {field}"}, status_code=400)

        # Build response patterns if provided
        response_patterns = []
        if data.get("response_pattern") and data.get("response_state_key"):
            response_patterns.append(ResponsePattern(
                pattern=data["response_pattern"],
                state_key=data["response_state_key"],
                value_group=data.get("value_group", 1),
                value_map=data.get("value_map", {}),
            ))

        command = DeviceCommand(
            command_id=data["command_id"],
            name=data["name"],
            format=CommandFormat(data.get("format", "text")),
            payload=data["payload"],
            line_ending=LineEnding(data.get("line_ending", "none")),
            is_input_option=data.get("is_input_option", False),
            input_value=data.get("input_value", ""),
            is_query=data.get("is_query", False),
            response_patterns=response_patterns,
            poll_interval=data.get("poll_interval", 0.0),
        )

        await storage.async_add_command_to_serial_device(device_id, command)
        _LOGGER.info("Added command %s to serial device %s", command.command_id, device_id)

        return self.json({"success": True, "command_id": command.command_id})


class VDAIRSerialDeviceCommandView(HomeAssistantView):
    """API endpoint for a single serial device command."""

    url = "/api/vda_ir_control/serial_devices/{device_id}/commands/{command_id}"
    name = "api:vda_ir_control:serial_device_command"
    requires_auth = True

    async def delete(self, request, device_id, command_id):
        """Delete a command from a serial device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        success = await storage.async_delete_command_from_serial_device(device_id, command_id)
        if not success:
            return self.json({"error": "Command not found"}, status_code=404)

        return self.json({"success": True})


class VDAIRSerialDeviceSendView(HomeAssistantView):
    """API endpoint for sending commands to serial devices."""

    url = "/api/vda_ir_control/serial_devices/{device_id}/send"
    name = "api:vda_ir_control:serial_device_send"
    requires_auth = True

    async def post(self, request, device_id):
        """Send a command to a serial device."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        try:
            data = await request.json()
        except Exception:
            return self.json({"error": "Invalid JSON"}, status_code=400)

        # Get or setup coordinator
        coordinator = get_serial_coordinator(hass, device_id)
        if coordinator is None:
            device = await storage.async_get_serial_device(device_id)
            if device is None:
                return self.json({"error": "Device not found"}, status_code=404)
            coordinator = await async_setup_serial_coordinator(hass, device)

        wait_for_response = data.get("wait_for_response", False)
        timeout = data.get("timeout", 2.0)

        # Check if sending a named command or raw payload
        if "command_id" in data:
            command = coordinator.device.get_command(data["command_id"])
            if command is None:
                return self.json({"error": "Command not found"}, status_code=404)

            try:
                response = await coordinator.async_send_command(command, wait_for_response, timeout)
                return self.json({
                    "success": True,
                    "command_id": data["command_id"],
                    "response": response,
                })
            except Exception as err:
                return self.json({"error": str(err)}, status_code=500)

        elif "payload" in data:
            # Send raw command
            try:
                response = await coordinator.async_send_raw(
                    data["payload"],
                    data.get("format", "text"),
                    data.get("line_ending", "none"),
                    wait_for_response,
                    timeout,
                )
                return self.json({
                    "success": True,
                    "response": response,
                })
            except Exception as err:
                return self.json({"error": str(err)}, status_code=500)

        else:
            return self.json({"error": "Must provide command_id or payload"}, status_code=400)


class VDAIRSerialDeviceStateView(HomeAssistantView):
    """API endpoint for serial device state."""

    url = "/api/vda_ir_control/serial_devices/{device_id}/state"
    name = "api:vda_ir_control:serial_device_state"
    requires_auth = True

    async def get(self, request, device_id):
        """Get current state of a serial device."""
        hass = request.app["hass"]

        coordinator = get_serial_coordinator(hass, device_id)
        if coordinator is None:
            return self.json({"error": "Device not connected"}, status_code=404)

        return self.json({
            "device_id": device_id,
            "connected": coordinator.is_connected,
            "is_bridge_mode": coordinator.is_bridge_mode,
            "state": coordinator.device_state.to_dict(),
        })


class VDAIRBoardSerialConfigView(HomeAssistantView):
    """API endpoint for ESP32 board serial pin configuration info."""

    url = "/api/vda_ir_control/boards/{board_id}/serial_config"
    name = "api:vda_ir_control:board_serial_config"
    requires_auth = True

    async def get(self, request, board_id):
        """Get serial pin configuration for a board."""
        # Return recommended pins based on board type
        # Olimex ESP32-POE-ISO: UART1 on GPIO9 (RX) / GPIO10 (TX)
        # ESP32 DevKit: UART1 on GPIO16 (RX) / GPIO17 (TX) or UART2 on GPIO25/26

        return self.json({
            "board_id": board_id,
            "configurations": {
                "olimex_poe_iso": {
                    "name": "Olimex ESP32-POE-ISO",
                    "uart_options": [
                        {
                            "uart": 1,
                            "rx_pin": 9,
                            "tx_pin": 10,
                            "notes": "Recommended - UEXT connector compatible",
                        }
                    ],
                },
                "esp32_devkit": {
                    "name": "ESP32 DevKit",
                    "uart_options": [
                        {
                            "uart": 1,
                            "rx_pin": 16,
                            "tx_pin": 17,
                            "notes": "UART1 - most common",
                        },
                        {
                            "uart": 2,
                            "rx_pin": 25,
                            "tx_pin": 26,
                            "notes": "UART2 - alternative pins",
                        },
                    ],
                },
            },
            "baud_rates": [9600, 19200, 38400, 57600, 115200, 230400],
            "default_baud": 115200,
        })


async def async_setup_api(hass: HomeAssistant) -> None:
    """Set up the REST API."""
    # IR device endpoints
    hass.http.register_view(VDAIRBoardsView())
    hass.http.register_view(VDAIRProfilesView())
    hass.http.register_view(VDAIRProfileView())
    hass.http.register_view(VDAIRDevicesView())
    hass.http.register_view(VDAIRPortsView())
    hass.http.register_view(VDAIRCommandsView())
    hass.http.register_view(VDAIRLearningStatusView())
    hass.http.register_view(VDAIRGPIOPinsView())
    hass.http.register_view(VDAIRPortAssignmentsView())
    hass.http.register_view(VDAIRBuiltinProfilesView())
    hass.http.register_view(VDAIRBuiltinProfileView())

    # Community profile endpoints
    hass.http.register_view(VDAIRCommunityProfilesView())
    hass.http.register_view(VDAIRCommunityProfileView())
    hass.http.register_view(VDAIRSyncProfilesView())
    hass.http.register_view(VDAIRExportProfileView())
    hass.http.register_view(VDAIRAllProfilesView())

    # Network device endpoints
    hass.http.register_view(VDAIRNetworkDevicesView())
    hass.http.register_view(VDAIRNetworkDeviceView())
    hass.http.register_view(VDAIRNetworkDeviceCommandsView())
    hass.http.register_view(VDAIRNetworkDeviceCommandView())
    hass.http.register_view(VDAIRNetworkDeviceSendView())
    hass.http.register_view(VDAIRNetworkDeviceStateView())
    hass.http.register_view(VDAIRTestConnectionView())

    # Serial device endpoints
    hass.http.register_view(VDAIRSerialPortsView())
    hass.http.register_view(VDAIRSerialDevicesView())
    hass.http.register_view(VDAIRSerialDeviceView())
    hass.http.register_view(VDAIRSerialDeviceCommandsView())
    hass.http.register_view(VDAIRSerialDeviceCommandView())
    hass.http.register_view(VDAIRSerialDeviceSendView())
    hass.http.register_view(VDAIRSerialDeviceStateView())
    hass.http.register_view(VDAIRBoardSerialConfigView())

    _LOGGER.info("VDA IR Control REST API registered")
