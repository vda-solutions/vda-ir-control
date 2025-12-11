"""VDA IR Control integration for Home Assistant."""

import logging
from pathlib import Path
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN
from .coordinator import VDAIRBoardCoordinator
from .services import async_setup_services
from .api import async_setup_api

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: Final = [Platform.SWITCH]

# Frontend paths
FRONTEND_DIR = Path(__file__).parent / "frontend"
CARD_URL = f"/{DOMAIN}/vda-ir-control-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the VDA IR Control component."""
    hass.data.setdefault(DOMAIN, {})

    # Register services
    await async_setup_services(hass)

    # Register REST API
    await async_setup_api(hass)

    # Register frontend resources
    await _async_register_frontend(hass)

    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Register frontend resources."""
    # Register static path for frontend files
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            f"/{DOMAIN}",
            str(FRONTEND_DIR),
            cache_headers=False,
        )
    ])

    # Register the card as a Lovelace resource
    # Users need to add this to their Lovelace resources manually or via UI
    _LOGGER.info(
        "VDA IR Control frontend registered. Add this resource to Lovelace: %s",
        CARD_URL,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VDA IR Control from a config entry."""
    _LOGGER.debug("Setting up VDA IR Control entry: %s", entry.title)

    hass.data.setdefault(DOMAIN, {})

    # Create board coordinator
    board_id = entry.data["board_id"]
    ip_address = entry.data["ip_address"]
    mac_address = entry.data["mac_address"]
    port = entry.data.get("port", 8080)

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
