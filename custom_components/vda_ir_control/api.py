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
from .models import SerialDevice, SerialConfig, DeviceCommand, ResponsePattern
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

    async def delete(self, request, profile_id):
        """Delete a user profile."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        profile = await storage.async_get_profile(profile_id)
        if profile is None:
            return self.json({"error": "Profile not found"}, status_code=404)

        await storage.async_delete_profile(profile_id)
        _LOGGER.info("Deleted user profile: %s", profile_id)

        return self.json({
            "success": True,
            "message": f"Deleted profile {profile_id}"
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


class VDAIRDeviceView(HomeAssistantView):
    """API endpoint for a single device."""

    url = "/api/vda_ir_control/devices/{device_id}"
    name = "api:vda_ir_control:device"
    requires_auth = True

    async def get(self, request, device_id):
        """Get a single device with its profile codes."""
        hass = request.app["hass"]
        storage = get_storage(hass)

        # Get all devices and find the one we need
        devices = await storage.async_get_all_devices()
        device = None
        for d in devices:
            if d.device_id == device_id:
                device = d
                break

        if device is None:
            return self.json({"error": "Device not found"}, status_code=404)

        # Get the profile to include codes
        # Check all sources: user storage, builtin, community
        profile = None
        codes = {}
        profile_dict = None

        if device.device_profile_id:
            # Try user profile first
            profile = await storage.async_get_profile(device.device_profile_id)
            if profile:
                codes = {cmd: code.to_dict() for cmd, code in profile.codes.items()}
                profile_dict = {
                    "profile_id": profile.profile_id,
                    "name": profile.name,
                    "device_type": profile.device_type.value,
                    "manufacturer": profile.manufacturer,
                    "model": profile.model,
                }
            else:
                # Try builtin profile
                builtin = get_profile_by_id(device.device_profile_id)
                if builtin:
                    codes = builtin.get("codes", {})
                    profile_dict = {
                        "profile_id": builtin["profile_id"],
                        "name": builtin["name"],
                        "device_type": builtin["device_type"],
                        "manufacturer": builtin.get("manufacturer", ""),
                        "model": builtin.get("model", ""),
                    }
                else:
                    # Try community profile
                    manager = get_profile_manager(hass)
                    await manager.async_load()
                    community = manager.get_community_profile(device.device_profile_id)
                    if community:
                        codes = community.get("codes", {})
                        profile_dict = {
                            "profile_id": community["profile_id"],
                            "name": community["name"],
                            "device_type": community["device_type"],
                            "manufacturer": community.get("manufacturer", ""),
                            "model": community.get("model", ""),
                        }

        result = device.to_dict()
        result["codes"] = codes
        result["profile_id"] = device.device_profile_id  # Add for compatibility
        if profile_dict:
            result["profile"] = profile_dict

        return self.json(result)


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
    """API endpoint for built-in IR profiles (includes synced community profiles)."""

    url = "/api/vda_ir_control/builtin_profiles"
    name = "api:vda_ir_control:builtin_profiles"
    requires_auth = True

    async def get(self, request):
        """Get all built-in IR profiles including synced community profiles.

        This merges builtin profiles with community profiles synced from GitHub,
        so they appear together in the admin UI.

        Optional query parameters:
        - device_type: Filter by device type (tv, cable_box, soundbar, streaming)
        - manufacturer: Filter by manufacturer name
        """
        hass = request.app["hass"]
        manager = get_profile_manager(hass)
        await manager.async_load()

        device_type = request.query.get("device_type")
        manufacturer = request.query.get("manufacturer")

        # Get builtin profiles
        if device_type:
            builtin_profiles = get_profiles_by_type(device_type)
        elif manufacturer:
            builtin_profiles = get_profiles_by_manufacturer(manufacturer)
        else:
            builtin_profiles = get_all_profiles()

        # Get community profiles and filter if needed
        community_profiles = manager.get_all_community_profiles()

        if device_type:
            community_profiles = [
                p for p in community_profiles
                if p.get("device_type") == device_type
            ]

        if manufacturer:
            community_profiles = [
                p for p in community_profiles
                if p.get("manufacturer", "").lower() == manufacturer.lower()
            ]

        # Merge profiles with deduplication by profile_id
        # Use a dict to deduplicate - community profiles override builtin if same ID
        merged_profiles = {}

        # Add builtin first
        for profile in builtin_profiles:
            profile_id = profile.get("profile_id")
            if profile_id:
                merged_profiles[profile_id] = {**profile, "_source": "builtin"}

        # Add community (will override builtin if same profile_id)
        for profile in community_profiles:
            profile_id = profile.get("profile_id")
            if profile_id:
                merged_profiles[profile_id] = profile  # Already has _source: "community"

        all_profiles = list(merged_profiles.values())

        # Count only unique profiles per source
        builtin_only_count = len([p for p in all_profiles if p.get("_source") == "builtin"])
        community_only_count = len([p for p in all_profiles if p.get("_source") == "community"])

        # Get all manufacturers and device types from merged list
        all_manufacturers = set()
        all_device_types = set()
        for p in all_profiles:
            if p.get("manufacturer"):
                all_manufacturers.add(p["manufacturer"])
            if p.get("device_type"):
                all_device_types.add(p["device_type"])

        return self.json({
            "profiles": all_profiles,
            "total": len(all_profiles),
            "builtin_count": builtin_only_count,
            "community_count": community_only_count,
            "available_device_types": sorted(list(all_device_types)),
            "available_manufacturers": sorted(list(all_manufacturers)),
            "sync_status": manager.get_sync_status(),
        })


class VDAIRBuiltinProfileView(HomeAssistantView):
    """API endpoint for a single built-in IR profile (includes community)."""

    url = "/api/vda_ir_control/builtin_profiles/{profile_id}"
    name = "api:vda_ir_control:builtin_profile"
    requires_auth = True

    async def get(self, request, profile_id):
        """Get a specific built-in IR profile by ID.

        Checks builtin profiles first, then community profiles.
        """
        hass = request.app["hass"]

        # Try builtin first
        profile = get_profile_by_id(profile_id)

        if profile is None:
            # Try community profiles
            manager = get_profile_manager(hass)
            await manager.async_load()
            profile = manager.get_community_profile(profile_id)

        if profile is None:
            return self.json({"error": "Profile not found"}, status_code=404)

        return self.json(profile)


# ============================================================================
# COMMUNITY PROFILE API ENDPOINTS
# ============================================================================


class VDAIRCommunityProfilesView(HomeAssistantView):
    """API endpoint for community IR profiles (available and downloaded)."""

    url = "/api/vda_ir_control/community_profiles"
    name = "api:vda_ir_control:community_profiles"
    requires_auth = True

    async def get(self, request):
        """Get available and downloaded community profiles.

        Query parameters:
        - status: "available" (from manifest - default), "downloaded", or "all"

        Returns:
        - For "available": List from manifest showing what can be downloaded
        - For "downloaded": Only profiles actually downloaded locally
        - For "all": Combined list with download status
        """
        hass = request.app["hass"]
        manager = get_profile_manager(hass)
        await manager.async_load()

        status_filter = request.query.get("status", "available")

        # Get downloaded profiles
        downloaded = manager.get_all_community_profiles()
        downloaded_ids = {p["profile_id"] for p in downloaded}

        # Only fetch manifest if status is "available" or "all"
        available = []
        if status_filter in ("available", "all"):
            manifest_result = await manager.async_fetch_manifest()
            available = manifest_result.get("available_profiles", [])

        if status_filter == "downloaded":
            # Only downloaded profiles
            return self.json({
                "profiles": downloaded,
                "total": len(downloaded),
                "status": "downloaded",
            })

        if status_filter == "available":
            # Only available profiles (from manifest)
            # Mark which ones are already downloaded and add command counts
            downloaded_dict = {p["profile_id"]: p for p in downloaded}

            for profile in available:
                profile_id = profile.get("profile_id") or profile.get("id")
                is_downloaded = profile_id in downloaded_ids
                profile["downloaded"] = is_downloaded

                # Add command count if downloaded
                if is_downloaded and profile_id in downloaded_dict:
                    codes = downloaded_dict[profile_id].get("codes", {})
                    profile["command_count"] = len(codes)
                else:
                    profile["command_count"] = None

            sync_status = manager.get_sync_status()

            return self.json({
                "profiles": available,
                "total": len(available),
                "status": "available",
                "downloaded_count": len(downloaded),
                "manifest_version": manifest_result.get("manifest_version") if manifest_result else None,
                "last_sync": sync_status.get("last_sync"),
                "repository_url": sync_status.get("repository_url"),
            })

        # All - merge available and downloaded
        # Start with available from manifest
        all_profiles = {}
        for profile in available:
            profile_id = profile.get("profile_id") or profile.get("id")
            if profile_id:
                all_profiles[profile_id] = {
                    **profile,
                    "downloaded": profile_id in downloaded_ids,
                }

        # Add any downloaded profiles not in manifest
        for profile in downloaded:
            profile_id = profile["profile_id"]
            if profile_id not in all_profiles:
                all_profiles[profile_id] = {
                    **profile,
                    "downloaded": True,
                    "_not_in_manifest": True,
                }

        sync_status = manager.get_sync_status()

        return self.json({
            "profiles": list(all_profiles.values()),
            "total": len(all_profiles),
            "downloaded_count": len(downloaded),
            "available_count": len(available),
            "status": "all",
            "manifest_version": manifest_result.get("manifest_version"),
            "last_sync": sync_status.get("last_sync"),
            "repository_url": sync_status.get("repository_url"),
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
    """API endpoint for fetching community profile manifest from GitHub."""

    url = "/api/vda_ir_control/sync_profiles"
    name = "api:vda_ir_control:sync_profiles"
    requires_auth = True

    async def post(self, request):
        """Fetch the manifest (list of available profiles) from GitHub.

        Only downloads the manifest, not the actual profiles.
        Profiles must be downloaded individually by the user.
        """
        hass = request.app["hass"]
        manager = get_profile_manager(hass)

        _LOGGER.info("Fetching community profile manifest")
        result = await manager.async_fetch_manifest()

        if result["success"]:
            _LOGGER.info(
                "Community profile manifest fetch completed: %s",
                result["message"]
            )
        else:
            _LOGGER.warning(
                "Community profile manifest fetch failed: %s",
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


class VDAIRAvailableProfilesView(HomeAssistantView):
    """API endpoint for listing available community profiles from manifest."""

    url = "/api/vda_ir_control/available_profiles"
    name = "api:vda_ir_control:available_profiles"
    requires_auth = True

    async def get(self, request):
        """Get list of available profiles from the manifest.

        This shows what CAN be downloaded from GitHub.
        Call POST /sync_profiles first to fetch the latest manifest.
        """
        hass = request.app["hass"]
        manager = get_profile_manager(hass)
        await manager.async_load()

        # Fetch the latest manifest
        manifest_result = await manager.async_fetch_manifest()

        if not manifest_result["success"]:
            return self.json({
                "error": manifest_result["message"],
                "profiles": [],
                "total": 0,
            }, status_code=500)

        available = manifest_result.get("available_profiles", [])

        # Get downloaded profiles to mark which are already downloaded
        downloaded = manager.get_all_community_profiles()
        downloaded_ids = {p["profile_id"] for p in downloaded}

        # Mark which profiles are already downloaded
        for profile in available:
            profile_id = profile.get("profile_id") or profile.get("id")
            profile["downloaded"] = profile_id in downloaded_ids

        return self.json({
            "profiles": available,
            "total": len(available),
            "downloaded_count": len(downloaded_ids),
            "manifest_version": manifest_result.get("manifest_version"),
        })


class VDAIRDownloadProfileView(HomeAssistantView):
    """API endpoint for downloading a specific community profile."""

    url = "/api/vda_ir_control/download_profile/{profile_id}"
    name = "api:vda_ir_control:download_profile"
    requires_auth = True

    async def post(self, request, profile_id):
        """Download a specific profile from GitHub.

        Args:
            profile_id: The profile ID to download
        """
        hass = request.app["hass"]
        manager = get_profile_manager(hass)

        _LOGGER.info("Downloading community profile: %s", profile_id)
        result = await manager.async_download_profile(profile_id)

        if result["success"]:
            _LOGGER.info("Successfully downloaded profile: %s", profile_id)
        else:
            _LOGGER.warning("Failed to download profile %s: %s", profile_id, result["message"])

        return self.json(result)


class VDAIRDeleteCommunityProfileView(HomeAssistantView):
    """API endpoint for deleting a downloaded community profile."""

    url = "/api/vda_ir_control/delete_community_profile/{profile_id}"
    name = "api:vda_ir_control:delete_community_profile"
    requires_auth = True

    async def delete(self, request, profile_id):
        """Delete a downloaded community profile.

        Args:
            profile_id: The profile ID to delete
        """
        hass = request.app["hass"]
        manager = get_profile_manager(hass)

        _LOGGER.info("Deleting community profile: %s", profile_id)
        result = await manager.async_delete_profile(profile_id)

        if result["success"]:
            _LOGGER.info("Successfully deleted profile: %s", profile_id)
        else:
            _LOGGER.warning("Failed to delete profile %s: %s", profile_id, result["message"])

        return self.json(result)


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
    hass.http.register_view(VDAIRDeviceView())
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
    hass.http.register_view(VDAIRAvailableProfilesView())
    hass.http.register_view(VDAIRDownloadProfileView())
    hass.http.register_view(VDAIRDeleteCommunityProfileView())
    hass.http.register_view(VDAIRExportProfileView())
    hass.http.register_view(VDAIRAllProfilesView())

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
