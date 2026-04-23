"""Profile manager for serial device profiles.

Manages serial device profiles from multiple sources:
1. Built-in profiles (common devices like OREI matrices)
2. Community profiles (synced from GitHub vda-serial-profiles repo)
3. User profiles (created locally)

Priority order: User > Community > Built-in
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .models import SerialDeviceProfile, DeviceCommand, ResponsePattern
from .device_types import DeviceType, CommandFormat, LineEnding

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_SERIAL_PROFILES = f"{DOMAIN}_serial_profiles"
STORAGE_KEY_SERIAL_META = f"{DOMAIN}_serial_meta"

# GitHub repository URLs for serial profiles
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/vda-solutions/vda-serial-profiles/main"
GITHUB_API_BASE = "https://api.github.com/repos/vda-solutions/vda-serial-profiles"
GITHUB_REPO_URL = "https://github.com/vda-solutions/vda-serial-profiles"


# ============================================================================
# BUILT-IN SERIAL PROFILES
# ============================================================================

BUILTIN_SERIAL_PROFILES: List[Dict[str, Any]] = [
    {
        "profile_id": "orei_hdmi_matrix_generic",
        "name": "OREI HDMI Matrix (Generic)",
        "manufacturer": "OREI",
        "model": "HD-EX Series",
        "device_type": "hdmi_matrix",
        "baud_rate": 115200,
        "data_bits": 8,
        "stop_bits": 1,
        "parity": "N",
        "routing_template": "s in {input} av out {output}!",
        "query_template": "r av out {output}!",
        "default_inputs": 8,
        "default_outputs": 8,
        "commands": {
            "power_on": {
                "command_id": "power_on",
                "name": "Power On",
                "format": "text",
                "payload": "s power 1!",
                "line_ending": "none",
            },
            "power_off": {
                "command_id": "power_off",
                "name": "Power Off",
                "format": "text",
                "payload": "s power 0!",
                "line_ending": "none",
            },
        },
        "global_response_patterns": [],
    },
    {
        "profile_id": "epson_projector_rs232",
        "name": "Epson Projector (RS232)",
        "manufacturer": "Epson",
        "model": "Home Cinema / Pro Cinema Series",
        "device_type": "projector",
        "baud_rate": 9600,
        "data_bits": 8,
        "stop_bits": 1,
        "parity": "N",
        "commands": {
            "power_on": {
                "command_id": "power_on",
                "name": "Power On",
                "format": "text",
                "payload": "PWR ON",
                "line_ending": "cr",
            },
            "power_off": {
                "command_id": "power_off",
                "name": "Power Off",
                "format": "text",
                "payload": "PWR OFF",
                "line_ending": "cr",
            },
            "hdmi1": {
                "command_id": "hdmi1",
                "name": "HDMI 1",
                "format": "text",
                "payload": "SOURCE 30",
                "line_ending": "cr",
                "is_input_option": True,
                "input_value": "HDMI1",
            },
            "hdmi2": {
                "command_id": "hdmi2",
                "name": "HDMI 2",
                "format": "text",
                "payload": "SOURCE A0",
                "line_ending": "cr",
                "is_input_option": True,
                "input_value": "HDMI2",
            },
            "query_power": {
                "command_id": "query_power",
                "name": "Query Power",
                "format": "text",
                "payload": "PWR?",
                "line_ending": "cr",
                "is_query": True,
                "response_patterns": [
                    {"pattern": "PWR=(\\d+)", "state_key": "power", "value_group": 1, "value_map": {"0": "off", "1": "on"}}
                ],
            },
            "query_source": {
                "command_id": "query_source",
                "name": "Query Source",
                "format": "text",
                "payload": "SOURCE?",
                "line_ending": "cr",
                "is_query": True,
                "response_patterns": [
                    {"pattern": "SOURCE=([0-9A-F]+)", "state_key": "current_input", "value_group": 1}
                ],
            },
        },
        "global_response_patterns": [],
    },
]


def get_builtin_serial_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    """Get a built-in serial profile by ID."""
    for profile in BUILTIN_SERIAL_PROFILES:
        if profile["profile_id"] == profile_id:
            return profile
    return None


class SerialProfileManager:
    """Manages serial device profiles from multiple sources with priority."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the serial profile manager."""
        self.hass = hass
        self._community_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_SERIAL_PROFILES)
        self._meta_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_SERIAL_META)

        # Cached data
        self._community_profiles: Dict[str, Dict[str, Any]] = {}
        self._user_profiles: Dict[str, Dict[str, Any]] = {}
        self._meta: Dict[str, Any] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load cached community profiles from storage."""
        if self._loaded:
            return

        # Load community profiles cache
        profiles_data = await self._community_store.async_load()
        if profiles_data:
            self._community_profiles = profiles_data
            _LOGGER.debug("Loaded %d community serial profiles from cache", len(self._community_profiles))

        # Load metadata
        meta_data = await self._meta_store.async_load()
        if meta_data:
            self._meta = meta_data

        self._loaded = True
        _LOGGER.info(
            "SerialProfileManager loaded: %d community profiles, last sync: %s",
            len(self._community_profiles),
            self._meta.get("last_sync", "never")
        )

    async def async_fetch_manifest(self) -> Dict[str, Any]:
        """Fetch the manifest (list of available profiles) from GitHub."""
        session = async_get_clientsession(self.hass)

        headers = {
            "Accept": "application/json",
            "User-Agent": "VDA-IR-Control-HomeAssistant/1.0"
        }

        result = {
            "success": False,
            "available_profiles": [],
            "message": "",
        }

        try:
            manifest_url = f"{GITHUB_RAW_BASE}/manifest.json"
            _LOGGER.debug("Fetching serial profiles manifest from %s", manifest_url)

            async with session.get(manifest_url, headers=headers, timeout=30) as resp:
                if resp.status == 404:
                    result["message"] = "Community serial profile repository not found"
                    _LOGGER.error("Manifest not found at %s", manifest_url)
                    return result

                if resp.status != 200:
                    result["message"] = f"GitHub error: HTTP {resp.status}"
                    _LOGGER.error("Failed to fetch manifest: HTTP %d", resp.status)
                    return result

                manifest = await resp.json(content_type=None)

            # Parse manifest
            profiles_raw = manifest.get("profiles", [])
            available_profiles = []

            for item in profiles_raw:
                if isinstance(item, str):
                    # Simple format - just a path
                    parts = item.split("/")
                    profile_id = parts[-1].replace(".json", "")
                    device_type = parts[0] if len(parts) > 0 else "unknown"
                    manufacturer = parts[1] if len(parts) > 1 else "Unknown"

                    # Fetch command count
                    command_count = None
                    try:
                        profile_url = f"{GITHUB_RAW_BASE}/{item}"
                        async with session.get(profile_url, timeout=5) as profile_resp:
                            if profile_resp.status == 200:
                                profile_data = await profile_resp.json(content_type=None)
                                commands = profile_data.get("commands", {})
                                command_count = len(commands)
                    except Exception as err:
                        _LOGGER.warning("Failed to fetch command count for %s: %s", profile_id, err)

                    available_profiles.append({
                        "profile_id": profile_id,
                        "path": item,
                        "name": profile_id.replace("_", " ").title(),
                        "manufacturer": manufacturer.replace("_", " ").title(),
                        "device_type": device_type,
                        "downloaded": profile_id in self._community_profiles,
                        "command_count": command_count,
                    })
                elif isinstance(item, dict):
                    if "downloaded" not in item:
                        item["downloaded"] = item.get("profile_id", "") in self._community_profiles
                    available_profiles.append(item)

            result["success"] = True
            result["available_profiles"] = available_profiles
            result["manifest_version"] = manifest.get("version", "unknown")
            result["manifest_updated"] = manifest.get("updated", "unknown")
            result["message"] = f"Found {len(available_profiles)} available profiles"

            # Update metadata
            self._meta["manifest_last_fetch"] = datetime.now().isoformat()
            self._meta["manifest_version"] = manifest.get("version", "unknown")
            await self._meta_store.async_save(self._meta)

            _LOGGER.info("Fetched serial profiles manifest with %d profiles", len(available_profiles))

        except Exception as err:
            _LOGGER.error("Failed to fetch serial profiles manifest: %s", err)
            result["message"] = f"Fetch failed: {str(err)}"

        return result

    async def async_download_profile(self, profile_id: str) -> Dict[str, Any]:
        """Download a specific profile from GitHub."""
        await self.async_load()
        session = async_get_clientsession(self.hass)

        result = {
            "success": False,
            "message": "",
            "profile": None,
        }

        try:
            # Fetch manifest to find profile path
            manifest_url = f"{GITHUB_RAW_BASE}/manifest.json"
            async with session.get(manifest_url, timeout=30) as resp:
                if resp.status != 200:
                    result["message"] = f"Failed to fetch manifest: HTTP {resp.status}"
                    return result
                manifest = await resp.json(content_type=None)

            # Find profile path
            profile_path = None
            profiles_raw = manifest.get("profiles", [])

            for item in profiles_raw:
                if isinstance(item, str):
                    item_profile_id = item.split("/")[-1].replace(".json", "")
                    if item_profile_id == profile_id:
                        profile_path = item
                        break
                elif isinstance(item, dict):
                    if item.get("profile_id") == profile_id or item.get("id") == profile_id:
                        profile_path = item.get("path")
                        break

            if not profile_path:
                result["message"] = f"Profile {profile_id} not found in manifest"
                return result

            # Download profile
            profile_url = f"{GITHUB_RAW_BASE}/{profile_path}"
            _LOGGER.debug("Downloading serial profile from %s", profile_url)

            async with session.get(profile_url, timeout=10) as profile_resp:
                if profile_resp.status != 200:
                    result["message"] = f"Failed to download profile: HTTP {profile_resp.status}"
                    return result

                profile_data = await profile_resp.json(content_type=None)

            # Save to storage
            self._community_profiles[profile_id] = profile_data
            await self._community_store.async_save(self._community_profiles)

            result["success"] = True
            result["profile"] = profile_data
            result["message"] = f"Downloaded profile {profile_id}"

            _LOGGER.info("Downloaded community serial profile: %s", profile_id)

        except Exception as err:
            _LOGGER.error("Failed to download serial profile %s: %s", profile_id, err)
            result["message"] = f"Download failed: {str(err)}"

        return result

    async def async_delete_profile(self, profile_id: str) -> Dict[str, Any]:
        """Delete a downloaded community profile."""
        await self.async_load()

        result = {
            "success": False,
            "message": "",
        }

        if profile_id not in self._community_profiles:
            result["message"] = f"Profile {profile_id} not found in downloaded profiles"
            return result

        del self._community_profiles[profile_id]
        await self._community_store.async_save(self._community_profiles)

        result["success"] = True
        result["message"] = f"Deleted profile {profile_id}"
        _LOGGER.info("Deleted community serial profile: %s", profile_id)

        return result

    def get_builtin_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get a built-in profile by ID."""
        profile = get_builtin_serial_profile(profile_id)
        if profile:
            return {**profile, "_source": "builtin"}
        return None

    def get_community_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get a community profile by ID."""
        profile = self._community_profiles.get(profile_id)
        if profile:
            return {**profile, "_source": "community"}

        # Search by internal profile_id
        for key, prof in self._community_profiles.items():
            if prof.get("profile_id") == profile_id:
                return {**prof, "_source": "community"}

        return None

    def get_profile(self, profile_id: str, source: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a profile by ID with optional source filter."""
        if source == "builtin":
            return self.get_builtin_profile(profile_id)

        if source == "community":
            return self.get_community_profile(profile_id)

        # Check community first (higher priority)
        community = self.get_community_profile(profile_id)
        if community:
            return community

        return self.get_builtin_profile(profile_id)

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all available profiles (built-in + community)."""
        profiles = []

        # Add built-in profiles
        for profile in BUILTIN_SERIAL_PROFILES:
            profiles.append({**profile, "_source": "builtin"})

        # Add community profiles (may override built-in)
        for profile_id, profile in self._community_profiles.items():
            # Check if this overrides a built-in
            overrides_builtin = any(p["profile_id"] == profile_id for p in BUILTIN_SERIAL_PROFILES)
            profiles.append({
                **profile,
                "_source": "community",
                "_overrides_builtin": overrides_builtin
            })

        return profiles

    def get_all_community_profiles(self) -> List[Dict[str, Any]]:
        """Get all cached community profiles."""
        return [
            {**profile, "_source": "community"}
            for profile in self._community_profiles.values()
        ]

    def get_all_builtin_profiles(self) -> List[Dict[str, Any]]:
        """Get all built-in profiles."""
        return [
            {**profile, "_source": "builtin"}
            for profile in BUILTIN_SERIAL_PROFILES
        ]

    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status information."""
        return {
            "last_sync": self._meta.get("manifest_last_fetch"),
            "manifest_version": self._meta.get("manifest_version"),
            "manifest_updated": self._meta.get("manifest_updated"),
            "community_profile_count": len(self._community_profiles),
            "builtin_profile_count": len(BUILTIN_SERIAL_PROFILES),
            "repository_url": GITHUB_REPO_URL,
        }

    def apply_profile_to_device(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get profile data formatted for applying to a new serial device."""
        profile = self.get_profile(profile_id)
        if not profile:
            return None

        return {
            "serial_config": {
                "baud_rate": profile.get("baud_rate", 9600),
                "data_bits": profile.get("data_bits", 8),
                "stop_bits": profile.get("stop_bits", 1),
                "parity": profile.get("parity", "N"),
            },
            "device_type": profile.get("device_type", "custom"),
            "commands": profile.get("commands", {}),
            "global_response_patterns": profile.get("global_response_patterns", []),
            "routing_template": profile.get("routing_template", ""),
            "query_template": profile.get("query_template", ""),
            "default_inputs": profile.get("default_inputs", 0),
            "default_outputs": profile.get("default_outputs", 0),
        }


def get_serial_profile_manager(hass: HomeAssistant) -> SerialProfileManager:
    """Get or create SerialProfileManager instance."""
    if "serial_profile_manager" not in hass.data.get(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["serial_profile_manager"] = SerialProfileManager(hass)
    return hass.data[DOMAIN]["serial_profile_manager"]
