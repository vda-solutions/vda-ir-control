"""Switch platform for VDA IR Control."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import VDAIRBoardCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform from a config entry."""
    coordinator: VDAIRBoardCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create switches for each IR output
    switches = []
    for output_id, output_info in coordinator.ir_outputs.items():
        switches.append(
            VDAIROutputSwitch(
                coordinator=coordinator,
                output_id=output_id,
                output_name=output_info.get("name", f"Output {output_id}"),
            )
        )

    if switches:
        async_add_entities(switches)


class VDAIROutputSwitch(SwitchEntity):
    """Switch entity for an IR output."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(
        self,
        coordinator: VDAIRBoardCoordinator,
        output_id: int,
        output_name: str,
    ) -> None:
        """Initialize the switch."""
        self.coordinator = coordinator
        self.output_id = output_id
        self._attr_name = output_name
        self._attr_unique_id = f"{coordinator.board_id}_output_{output_id}"
        self._attr_is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.board_id)},
            name=self.coordinator.board_info.get("board_name", self.coordinator.board_id),
            manufacturer="VDA IR Control",
            model="Olamex PoE ISO",
            sw_version=self.coordinator.board_info.get("firmware_version", "Unknown"),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch (test output)."""
        success = await self.coordinator.test_output(self.output_id, duration_ms=100)
        if success:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        # For IR outputs, "off" just means stop transmitting
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update entity state."""
        # IR outputs don't have persistent state
        # State is updated when we send commands
        pass
