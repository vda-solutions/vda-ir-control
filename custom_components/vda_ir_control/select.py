"""Select platform for VDA IR Control - Input selection entities."""

import logging
from typing import Any, List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .network_coordinator import NetworkDeviceCoordinator, get_network_coordinator
from .storage import get_storage
from .models import NetworkDevice, DeviceCommand

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VDA IR Control select entities from config entry."""
    # Load network devices and create select entities for those with input options
    storage = get_storage(hass)
    network_devices = await storage.async_get_all_network_devices()

    entities = []
    for device in network_devices:
        # Get input option commands
        input_commands = device.get_input_options()
        if input_commands:
            # Get or create coordinator
            coordinator = get_network_coordinator(hass, device.device_id)
            if coordinator:
                entities.append(
                    VDAInputSelect(
                        coordinator=coordinator,
                        device=device,
                        input_commands=input_commands,
                    )
                )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d input select entities for network devices", len(entities))


class VDAInputSelect(CoordinatorEntity[NetworkDeviceCoordinator], SelectEntity):
    """Select entity for device input selection with state feedback."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetworkDeviceCoordinator,
        device: NetworkDevice,
        input_commands: List[DeviceCommand],
    ) -> None:
        """Initialize the input select entity."""
        super().__init__(coordinator)

        self._device = device
        self._input_commands = {cmd.input_value: cmd for cmd in input_commands}
        self._option_to_value = {cmd.name: cmd.input_value for cmd in input_commands}
        self._value_to_option = {cmd.input_value: cmd.name for cmd in input_commands}

        # Entity attributes
        self._attr_unique_id = f"{device.device_id}_input_select"
        self._attr_name = "Input"
        self._attr_options = [cmd.name for cmd in input_commands]

        # Register for state updates
        self._remove_listener = coordinator.add_state_listener(self._on_state_change)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for linking to device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            name=self._device.name,
            manufacturer="VDA IR Control",
            model=self._device.device_type.value,
        )

    @property
    def current_option(self) -> Optional[str]:
        """Return current input from device state."""
        state = self.coordinator.device_state
        if state and state.current_input:
            # Map device value back to option name
            return self._value_to_option.get(state.current_input, state.current_input)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_connected

    async def async_select_option(self, option: str) -> None:
        """Send input change command."""
        input_value = self._option_to_value.get(option)
        if not input_value:
            _LOGGER.warning("Unknown input option: %s", option)
            return

        command = self._input_commands.get(input_value)
        if command:
            try:
                await self.coordinator.async_send_command(command)
                _LOGGER.debug("Sent input change command: %s", command.command_id)
                # State will update via listener when device confirms
            except Exception as err:
                _LOGGER.error("Failed to send input command: %s", err)

    @callback
    def _on_state_change(self, key: str, value: Any) -> None:
        """Handle state update from device."""
        if key == "current_input":
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal."""
        if self._remove_listener:
            self._remove_listener()
        await super().async_will_remove_from_hass()


class VDAOutputSelect(CoordinatorEntity[NetworkDeviceCoordinator], SelectEntity):
    """Select entity for matrix output selection (for HDMI matrices with per-output control)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetworkDeviceCoordinator,
        device: NetworkDevice,
        output_number: int,
        input_commands: List[DeviceCommand],
    ) -> None:
        """Initialize the output select entity."""
        super().__init__(coordinator)

        self._device = device
        self._output_number = output_number
        self._input_commands = input_commands

        # Build option mappings
        self._option_to_value = {cmd.name: cmd.input_value for cmd in input_commands}
        self._value_to_option = {cmd.input_value: cmd.name for cmd in input_commands}

        # Entity attributes
        self._attr_unique_id = f"{device.device_id}_output_{output_number}_input"
        self._attr_name = f"Output {output_number} Input"
        self._attr_options = [cmd.name for cmd in input_commands]

        # Register for state updates
        self._state_key = f"output_{output_number}_input"
        self._remove_listener = coordinator.add_state_listener(self._on_state_change)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for linking to device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            name=self._device.name,
            manufacturer="VDA IR Control",
            model=self._device.device_type.value,
        )

    @property
    def current_option(self) -> Optional[str]:
        """Return current input for this output from device state."""
        state = self.coordinator.device_state
        if state:
            value = state.custom_states.get(self._state_key)
            if value:
                return self._value_to_option.get(value, value)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.is_connected

    async def async_select_option(self, option: str) -> None:
        """Send input routing command for this output."""
        input_value = self._option_to_value.get(option)
        if not input_value:
            _LOGGER.warning("Unknown input option: %s", option)
            return

        # For matrices, we need to send a routing command
        # The command should route input_value to self._output_number
        # This will be device-specific - look for a routing command
        for cmd in self._input_commands:
            if cmd.input_value == input_value:
                try:
                    await self.coordinator.async_send_command(cmd)
                    _LOGGER.debug(
                        "Sent routing command: input %s to output %d",
                        input_value,
                        self._output_number,
                    )
                except Exception as err:
                    _LOGGER.error("Failed to send routing command: %s", err)
                break

    @callback
    def _on_state_change(self, key: str, value: Any) -> None:
        """Handle state update from device."""
        if key == self._state_key:
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal."""
        if self._remove_listener:
            self._remove_listener()
        await super().async_will_remove_from_hass()
