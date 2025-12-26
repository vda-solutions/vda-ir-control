"""VDA IR Control integration for Home Assistant."""

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import VDAIRBoardCoordinator
from .services import async_setup_services
from .api import async_setup_api
from .storage import get_storage
from .profile_manager import get_profile_manager

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: Final = [Platform.SWITCH, Platform.BUTTON, Platform.SELECT]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the VDA IR Control component."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize profile manager and load cached community profiles
    profile_manager = get_profile_manager(hass)
    await profile_manager.async_load()
    _LOGGER.debug(
        "Profile manager initialized: %d community profiles cached",
        len(profile_manager.get_all_community_profiles())
    )

    # Register services
    await async_setup_services(hass)

    # Register REST API
    await async_setup_api(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VDA IR Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create board coordinator
    board_id = entry.data["board_id"]
    ip_address = entry.data["ip_address"]
    mac_address = entry.data["mac_address"]
    port = entry.data.get("port", 80)

    coordinator = VDAIRBoardCoordinator(
        hass,
        board_id=board_id,
        ip_address=ip_address,
        mac_address=mac_address,
        port=port,
    )

    # Fetch initial board info
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to fetch board info for %s: %s", board_id, err)
        raise ConfigEntryNotReady(f"Unable to connect to board {board_id}") from err

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for config entry updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.debug("Unloaded VDA IR Control entry: %s", entry.title)

    return unload_ok
