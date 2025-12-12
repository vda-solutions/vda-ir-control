"""Button platform for VDA IR Control devices."""

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .storage import get_storage
from .ir_profiles import get_profile_by_id as get_builtin_profile

_LOGGER = logging.getLogger(__name__)

# Command display names and icons
COMMAND_INFO = {
    # Power
    "power": {"name": "Power", "icon": "mdi:power"},
    "power_on": {"name": "Power On", "icon": "mdi:power-on"},
    "power_off": {"name": "Power Off", "icon": "mdi:power-off"},
    "power_toggle": {"name": "Power Toggle", "icon": "mdi:power"},
    # Volume
    "volume_up": {"name": "Volume Up", "icon": "mdi:volume-plus"},
    "volume_down": {"name": "Volume Down", "icon": "mdi:volume-minus"},
    "mute": {"name": "Mute", "icon": "mdi:volume-mute"},
    # Channel
    "channel_up": {"name": "Channel Up", "icon": "mdi:chevron-up"},
    "channel_down": {"name": "Channel Down", "icon": "mdi:chevron-down"},
    # Navigation
    "up": {"name": "Up", "icon": "mdi:chevron-up"},
    "down": {"name": "Down", "icon": "mdi:chevron-down"},
    "left": {"name": "Left", "icon": "mdi:chevron-left"},
    "right": {"name": "Right", "icon": "mdi:chevron-right"},
    "enter": {"name": "Enter", "icon": "mdi:checkbox-blank-circle"},
    "select": {"name": "Select", "icon": "mdi:checkbox-blank-circle"},
    "back": {"name": "Back", "icon": "mdi:arrow-left"},
    "exit": {"name": "Exit", "icon": "mdi:exit-to-app"},
    "menu": {"name": "Menu", "icon": "mdi:menu"},
    "home": {"name": "Home", "icon": "mdi:home"},
    "guide": {"name": "Guide", "icon": "mdi:television-guide"},
    "info": {"name": "Info", "icon": "mdi:information"},
    # Numbers
    "0": {"name": "0", "icon": "mdi:numeric-0"},
    "1": {"name": "1", "icon": "mdi:numeric-1"},
    "2": {"name": "2", "icon": "mdi:numeric-2"},
    "3": {"name": "3", "icon": "mdi:numeric-3"},
    "4": {"name": "4", "icon": "mdi:numeric-4"},
    "5": {"name": "5", "icon": "mdi:numeric-5"},
    "6": {"name": "6", "icon": "mdi:numeric-6"},
    "7": {"name": "7", "icon": "mdi:numeric-7"},
    "8": {"name": "8", "icon": "mdi:numeric-8"},
    "9": {"name": "9", "icon": "mdi:numeric-9"},
    # Inputs
    "source": {"name": "Source", "icon": "mdi:video-input-hdmi"},
    "hdmi": {"name": "HDMI", "icon": "mdi:video-input-hdmi"},
    "hdmi1": {"name": "HDMI 1", "icon": "mdi:video-input-hdmi"},
    "hdmi2": {"name": "HDMI 2", "icon": "mdi:video-input-hdmi"},
    "hdmi3": {"name": "HDMI 3", "icon": "mdi:video-input-hdmi"},
    "hdmi4": {"name": "HDMI 4", "icon": "mdi:video-input-hdmi"},
    # Playback
    "play": {"name": "Play", "icon": "mdi:play"},
    "pause": {"name": "Pause", "icon": "mdi:pause"},
    "play_pause": {"name": "Play/Pause", "icon": "mdi:play-pause"},
    "stop": {"name": "Stop", "icon": "mdi:stop"},
    "rewind": {"name": "Rewind", "icon": "mdi:rewind"},
    "fast_forward": {"name": "Fast Forward", "icon": "mdi:fast-forward"},
    "record": {"name": "Record", "icon": "mdi:record"},
    "replay": {"name": "Replay", "icon": "mdi:replay"},
}

# Device type icons
DEVICE_TYPE_ICONS = {
    "tv": "mdi:television",
    "cable_box": "mdi:set-top-box",
    "soundbar": "mdi:speaker",
    "streaming": "mdi:cast",
    "audio_receiver": "mdi:audio-video",
    "dvd_bluray": "mdi:disc-player",
    "projector": "mdi:projector",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VDA IR Control button entities."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator is None:
        return

    storage = get_storage(hass)

    # Get all controlled devices
    devices = await storage.async_get_all_devices()

    entities = []
    for device in devices:
        # Only create entities for devices using this board
        if device.board_id != coordinator.board_id:
            continue

        # Get commands from profile
        commands = await _get_device_commands(hass, device.device_profile_id)

        if not commands:
            _LOGGER.warning("No commands found for device %s", device.device_id)
            continue

        # Get device type for icon
        device_type = await _get_device_type(hass, device.device_profile_id)

        # Create a button entity for each command
        for command, code_info in commands.items():
            entities.append(
                VDAIRCommandButton(
                    coordinator=coordinator,
                    device=device,
                    command=command,
                    code_info=code_info,
                    device_type=device_type,
                )
            )

        _LOGGER.info(
            "Created %d button entities for device %s",
            len(commands),
            device.device_id,
        )

    if entities:
        async_add_entities(entities)


async def _get_device_commands(hass: HomeAssistant, profile_id: str) -> dict:
    """Get commands from a profile (builtin or custom)."""
    if profile_id.startswith("builtin:"):
        builtin_id = profile_id[8:]
        profile = get_builtin_profile(builtin_id)
        if profile:
            # Return codes with protocol info
            return {
                cmd: {"code": code, "protocol": profile.get("protocol", "NEC")}
                for cmd, code in profile.get("codes", {}).items()
            }
        return {}
    else:
        storage = get_storage(hass)
        profile = await storage.async_get_profile(profile_id)
        if profile:
            return {
                cmd: {"code": ir_code.raw_code, "protocol": ir_code.protocol}
                for cmd, ir_code in profile.codes.items()
            }
        return {}


async def _get_device_type(hass: HomeAssistant, profile_id: str) -> str:
    """Get device type from a profile."""
    if profile_id.startswith("builtin:"):
        builtin_id = profile_id[8:]
        profile = get_builtin_profile(builtin_id)
        if profile:
            return profile.get("device_type", "tv")
        return "tv"
    else:
        storage = get_storage(hass)
        profile = await storage.async_get_profile(profile_id)
        if profile:
            return profile.device_type.value
        return "tv"


class VDAIRCommandButton(CoordinatorEntity, ButtonEntity):
    """Button entity for a VDA IR command."""

    def __init__(
        self,
        coordinator,
        device,
        command: str,
        code_info: dict,
        device_type: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._device = device
        self._command = command
        self._code = code_info.get("code", "")
        self._protocol = code_info.get("protocol", "NEC")
        self._device_type = device_type

        # Get command display info
        cmd_info = COMMAND_INFO.get(command, {})
        self._cmd_name = cmd_info.get("name", command.replace("_", " ").title())
        self._cmd_icon = cmd_info.get("icon", "mdi:remote")

        # Entity attributes
        self._attr_unique_id = f"vda_ir_{device.device_id}_{command}"
        self._attr_name = f"{device.name} {self._cmd_name}"
        self._attr_icon = self._cmd_icon

        # Device info - groups all buttons under one device
        device_icon = DEVICE_TYPE_ICONS.get(device_type, "mdi:remote")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"controlled_{device.device_id}")},
            name=device.name,
            manufacturer="VDA IR Control",
            model=device_type.replace("_", " ").title(),
            suggested_area=device.location if device.location else None,
            via_device=(DOMAIN, device.board_id),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "command": self._command,
            "protocol": self._protocol,
            "device_id": self._device.device_id,
            "board_id": self._device.board_id,
            "output_port": self._device.output_port,
        }

    async def async_press(self) -> None:
        """Handle button press - send IR command."""
        _LOGGER.debug(
            "Sending %s command to %s via GPIO %d",
            self._command,
            self._device.device_id,
            self._device.output_port,
        )

        success = await self.coordinator.send_ir_code(
            self._device.output_port,
            self._code,
            self._protocol,
        )

        if not success:
            _LOGGER.error(
                "Failed to send %s command to %s",
                self._command,
                self._device.device_id,
            )
