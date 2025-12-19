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
from .network_coordinator import async_setup_network_coordinator
from .profile_manager import get_profile_manager
from .driver_manager import get_driver_manager

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: Final = [Platform.SWITCH, Platform.BUTTON, Platform.SELECT]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the VDA IR Control component."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize profile manager and load cached community profiles
    profile_manager = get_profile_manager(hass)
    await profile_manager.async_load()
    _LOGGER.info(
        "Profile manager initialized: %d community profiles cached",
        len(profile_manager.get_all_community_profiles())
    )

    # Initialize driver manager and load cached community drivers
    driver_manager = get_driver_manager(hass)
    await driver_manager.async_load()
    _LOGGER.info(
        "Driver manager initialized: %d community drivers cached",
        len(driver_manager.get_all_community_drivers())
    )

    # Register services
    await async_setup_services(hass)

    # Register REST API
    await async_setup_api(hass)

    # Initialize network device coordinators
    await _async_setup_network_devices(hass)

    return True


async def _async_setup_network_devices(hass: HomeAssistant) -> None:
    """Set up coordinators for all saved network devices."""
    storage = get_storage(hass)
    network_devices = await storage.async_get_all_network_devices()

    for device in network_devices:
        try:
            await async_setup_network_coordinator(hass, device)
            _LOGGER.info("Set up network device coordinator: %s", device.name)
        except Exception as err:
            _LOGGER.warning(
                "Failed to connect to network device %s: %s",
                device.name,
                err,
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VDA IR Control from a config entry."""
    _LOGGER.debug("Setting up VDA IR Control entry: %s", entry.title)

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

    # Forward setup to switch platform
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
