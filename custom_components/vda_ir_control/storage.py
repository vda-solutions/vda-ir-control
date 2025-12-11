"""Storage manager for VDA IR Control data."""

import logging
from typing import Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .models import BoardConfig, DeviceProfile, ControlledDevice

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_BOARDS = f"{DOMAIN}_boards"
STORAGE_KEY_PROFILES = f"{DOMAIN}_profiles"
STORAGE_KEY_DEVICES = f"{DOMAIN}_devices"


class VDAIRStorage:
    """Manages persistent storage for VDA IR Control."""

    def __init__(self, hass: HomeAssistant):
        """Initialize storage manager."""
        self.hass = hass
        self._boards_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_BOARDS)
        self._profiles_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_PROFILES)
        self._devices_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_DEVICES)

        # In-memory cache
        self._boards: Dict[str, BoardConfig] = {}
        self._profiles: Dict[str, DeviceProfile] = {}
        self._devices: Dict[str, ControlledDevice] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load all data from storage."""
        if self._loaded:
            return

        # Load boards
        boards_data = await self._boards_store.async_load()
        if boards_data:
            for board_id, board_dict in boards_data.items():
                try:
                    self._boards[board_id] = BoardConfig.from_dict(board_dict)
                except Exception as err:
                    _LOGGER.error("Failed to load board %s: %s", board_id, err)

        # Load device profiles
        profiles_data = await self._profiles_store.async_load()
        if profiles_data:
            for profile_id, profile_dict in profiles_data.items():
                try:
                    self._profiles[profile_id] = DeviceProfile.from_dict(profile_dict)
                except Exception as err:
                    _LOGGER.error("Failed to load profile %s: %s", profile_id, err)

        # Load controlled devices
        devices_data = await self._devices_store.async_load()
        if devices_data:
            for device_id, device_dict in devices_data.items():
                try:
                    self._devices[device_id] = ControlledDevice.from_dict(device_dict)
                except Exception as err:
                    _LOGGER.error("Failed to load device %s: %s", device_id, err)

        self._loaded = True
        _LOGGER.info(
            "Loaded %d boards, %d profiles, %d devices",
            len(self._boards),
            len(self._profiles),
            len(self._devices),
        )

    async def _async_save_boards(self) -> None:
        """Save boards to storage."""
        data = {k: v.to_dict() for k, v in self._boards.items()}
        await self._boards_store.async_save(data)

    async def _async_save_profiles(self) -> None:
        """Save profiles to storage."""
        data = {k: v.to_dict() for k, v in self._profiles.items()}
        await self._profiles_store.async_save(data)

    async def _async_save_devices(self) -> None:
        """Save devices to storage."""
        data = {k: v.to_dict() for k, v in self._devices.items()}
        await self._devices_store.async_save(data)

    # Board operations
    async def async_get_board(self, board_id: str) -> Optional[BoardConfig]:
        """Get a board by ID."""
        await self.async_load()
        return self._boards.get(board_id)

    async def async_get_all_boards(self) -> List[BoardConfig]:
        """Get all boards."""
        await self.async_load()
        return list(self._boards.values())

    async def async_save_board(self, board: BoardConfig) -> None:
        """Save or update a board."""
        await self.async_load()
        self._boards[board.board_id] = board
        await self._async_save_boards()

    async def async_delete_board(self, board_id: str) -> None:
        """Delete a board."""
        await self.async_load()
        if board_id in self._boards:
            del self._boards[board_id]
            await self._async_save_boards()

    # Profile operations
    async def async_get_profile(self, profile_id: str) -> Optional[DeviceProfile]:
        """Get a device profile by ID."""
        await self.async_load()
        return self._profiles.get(profile_id)

    async def async_get_all_profiles(self) -> List[DeviceProfile]:
        """Get all device profiles."""
        await self.async_load()
        return list(self._profiles.values())

    async def async_get_profiles_by_type(self, device_type: str) -> List[DeviceProfile]:
        """Get all profiles of a specific device type."""
        await self.async_load()
        return [p for p in self._profiles.values() if p.device_type.value == device_type]

    async def async_save_profile(self, profile: DeviceProfile) -> None:
        """Save or update a device profile."""
        await self.async_load()
        self._profiles[profile.profile_id] = profile
        await self._async_save_profiles()

    async def async_delete_profile(self, profile_id: str) -> None:
        """Delete a device profile."""
        await self.async_load()
        if profile_id in self._profiles:
            del self._profiles[profile_id]
            await self._async_save_profiles()

    async def async_add_ir_code_to_profile(
        self,
        profile_id: str,
        command: str,
        raw_code: str,
        protocol: str = "raw",
        frequency: int = 38000,
    ) -> bool:
        """Add an IR code to a profile."""
        await self.async_load()
        profile = self._profiles.get(profile_id)
        if profile is None:
            _LOGGER.error("Profile %s not found", profile_id)
            return False

        profile.add_code(command, raw_code, protocol, frequency)
        await self._async_save_profiles()
        _LOGGER.info("Added code for %s to profile %s", command, profile_id)
        return True

    # Controlled device operations
    async def async_get_device(self, device_id: str) -> Optional[ControlledDevice]:
        """Get a controlled device by ID."""
        await self.async_load()
        return self._devices.get(device_id)

    async def async_get_all_devices(self) -> List[ControlledDevice]:
        """Get all controlled devices."""
        await self.async_load()
        return list(self._devices.values())

    async def async_get_devices_by_location(self, location: str) -> List[ControlledDevice]:
        """Get all devices in a specific location."""
        await self.async_load()
        return [d for d in self._devices.values() if d.location == location]

    async def async_get_devices_by_board(self, board_id: str) -> List[ControlledDevice]:
        """Get all devices controlled by a specific board."""
        await self.async_load()
        return [d for d in self._devices.values() if d.board_id == board_id]

    async def async_save_device(self, device: ControlledDevice) -> None:
        """Save or update a controlled device."""
        await self.async_load()
        self._devices[device.device_id] = device
        await self._async_save_devices()

    async def async_delete_device(self, device_id: str) -> None:
        """Delete a controlled device."""
        await self.async_load()
        if device_id in self._devices:
            del self._devices[device_id]
            await self._async_save_devices()

    async def async_get_locations(self) -> List[str]:
        """Get list of unique locations."""
        await self.async_load()
        locations = set()
        for device in self._devices.values():
            if device.location:
                locations.add(device.location)
        return sorted(list(locations))


def get_storage(hass: HomeAssistant) -> VDAIRStorage:
    """Get or create storage instance."""
    if "storage" not in hass.data.get(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["storage"] = VDAIRStorage(hass)
    return hass.data[DOMAIN]["storage"]
