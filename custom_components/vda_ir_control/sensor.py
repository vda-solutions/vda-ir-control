"""Sensor platform for VDA IR Control - Matrix routing state."""

import asyncio
import logging
import re
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .storage import get_storage
from .serial_coordinator import get_serial_coordinator, async_setup_serial_coordinator

_LOGGER = logging.getLogger(__name__)

# Signal for matrix routing updates
SIGNAL_MATRIX_ROUTING_UPDATED = f"{DOMAIN}_matrix_routing_updated"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up matrix routing sensors."""
    # We don't create sensors per config entry - they're created globally for matrices
    pass


async def async_setup_matrix_sensors(hass: HomeAssistant) -> None:
    """Set up sensors for all matrix outputs."""
    storage = get_storage(hass)
    all_serial_devices = await storage.async_get_all_serial_devices()
    serial_devices = {d.device_id: d for d in all_serial_devices}

    sensors = []

    for device in serial_devices.values():
        # Only create sensors for HDMI matrices
        if device.device_type.value != "hdmi_matrix":
            continue

        matrix_id = device.device_id

        # Create a sensor for each output
        for output in device.matrix_outputs:
            sensor = MatrixOutputSensor(
                hass=hass,
                matrix_id=matrix_id,
                matrix_name=device.name,
                output_index=output.index,
                output_name=output.name,
                output_device_id=output.device_id,
                matrix_inputs=device.matrix_inputs,
            )
            sensors.append(sensor)

    if sensors:
        # Register sensors with HA
        # We need to use the entity component directly since this isn't per-config-entry
        from homeassistant.helpers.entity_component import EntityComponent

        component = hass.data.get(f"{DOMAIN}_sensor_component")
        if component is None:
            component = EntityComponent(_LOGGER, "sensor", hass)
            hass.data[f"{DOMAIN}_sensor_component"] = component

        await component.async_add_entities(sensors)
        _LOGGER.info("Created %d matrix routing sensors", len(sensors))

        # Query initial routing state for all matrices (run in background)
        hass.async_create_task(_async_sync_initial_routing(hass, serial_devices))


async def _async_sync_initial_routing(hass: HomeAssistant, serial_devices: dict) -> None:
    """Query all matrix outputs to sync initial routing state."""
    # Wait for HA to fully start
    await asyncio.sleep(5)

    _LOGGER.info("Starting initial matrix routing sync...")

    for device in serial_devices.values():
        if device.device_type.value != "hdmi_matrix":
            continue

        matrix_id = device.device_id
        query_template = device.query_template

        if not query_template:
            _LOGGER.debug("No query_template for matrix %s, skipping sync", matrix_id)
            continue

        # Get or create coordinator
        coordinator = get_serial_coordinator(hass, matrix_id)
        if coordinator is None:
            _LOGGER.debug("Creating coordinator for matrix %s", matrix_id)
            coordinator = await async_setup_serial_coordinator(hass, device)

        if coordinator is None:
            _LOGGER.warning("Could not create coordinator for matrix %s", matrix_id)
            continue

        # Query each output sequentially
        for output in device.matrix_outputs:
            output_index = output.index
            query_cmd = query_template.replace("{output}", str(output_index))

            try:
                _LOGGER.debug("Querying matrix %s output %d: %s", matrix_id, output_index, query_cmd)

                response = await coordinator.async_send_raw(
                    payload=query_cmd,
                    format_type="text",
                    line_ending="cr",
                    wait_for_response=True,
                    response_timeout=2.0,
                )

                if response:
                    response_str = str(response).strip()
                    _LOGGER.debug("Matrix %s output %d response: %s", matrix_id, output_index, response_str)

                    # Parse response - OREI format: "av out7 in3"
                    input_match = re.search(r"in\s*(\d+)", response_str, re.IGNORECASE)
                    if not input_match:
                        input_match = re.search(r"input\s*(\d+)", response_str, re.IGNORECASE)
                    if not input_match:
                        input_match = re.search(r"(\d+)\s*$", response_str)

                    if input_match:
                        input_index = int(input_match.group(1))
                        async_update_matrix_routing(hass, matrix_id, output_index, input_index)
                        _LOGGER.info(
                            "Initial sync: Matrix %s output %d -> input %d",
                            matrix_id, output_index, input_index
                        )

                # Small delay between queries to not overwhelm serial port
                await asyncio.sleep(0.5)

            except Exception as e:
                _LOGGER.warning("Failed to query matrix %s output %d: %s", matrix_id, output_index, e)

    _LOGGER.info("Initial matrix routing sync complete")


class MatrixOutputSensor(SensorEntity):
    """Sensor representing the current input for a matrix output."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        matrix_id: str,
        matrix_name: str,
        output_index: int,
        output_name: str,
        output_device_id: Optional[str],
        matrix_inputs: list,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._matrix_id = matrix_id
        self._matrix_name = matrix_name
        self._output_index = output_index
        self._output_name = output_name or f"Output {output_index}"
        self._output_device_id = output_device_id
        self._matrix_inputs = {inp.index: inp for inp in matrix_inputs}

        # Current routing state
        self._current_input: Optional[int] = None
        self._current_input_name: Optional[str] = None
        self._current_source_device: Optional[str] = None

        # Entity attributes
        self._attr_unique_id = f"vda_ir_matrix_{matrix_id}_output_{output_index}"
        self._attr_name = f"{matrix_name} {self._output_name}"
        self._attr_icon = "mdi:video-input-hdmi"

    @property
    def native_value(self) -> Optional[str]:
        """Return the current input number as state."""
        if self._current_input is None:
            return "unknown"
        return str(self._current_input)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attrs = {
            "matrix_id": self._matrix_id,
            "output_index": self._output_index,
            "output_name": self._output_name,
            "output_device_id": self._output_device_id,
            "current_input": self._current_input,
            "current_input_name": self._current_input_name,
            "current_source_device": self._current_source_device,
        }
        return attrs

    async def async_added_to_hass(self) -> None:
        """Register for routing update signals."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_MATRIX_ROUTING_UPDATED}_{self._matrix_id}_{self._output_index}",
                self._handle_routing_update,
            )
        )

    @callback
    def _handle_routing_update(self, input_index: int) -> None:
        """Handle routing update signal."""
        self._current_input = input_index

        # Look up input details
        if input_index in self._matrix_inputs:
            inp = self._matrix_inputs[input_index]
            self._current_input_name = inp.name
            self._current_source_device = inp.device_id
        else:
            self._current_input_name = f"Input {input_index}"
            self._current_source_device = None

        self.async_write_ha_state()
        _LOGGER.debug(
            "Matrix %s output %d updated to input %d (%s)",
            self._matrix_id, self._output_index, input_index, self._current_input_name
        )

    def update_routing(self, input_index: int) -> None:
        """Update the routing state (called directly, not via signal)."""
        self._handle_routing_update(input_index)


def async_update_matrix_routing(
    hass: HomeAssistant,
    matrix_id: str,
    output_index: int,
    input_index: int,
) -> None:
    """Update matrix routing state and notify all listeners.

    Call this from the API/service when routing changes.
    """
    from homeassistant.helpers.dispatcher import async_dispatcher_send

    # Send signal to update the sensor
    async_dispatcher_send(
        hass,
        f"{SIGNAL_MATRIX_ROUTING_UPDATED}_{matrix_id}_{output_index}",
        input_index,
    )

    # Also store in hass.data for quick access
    routing_key = f"{DOMAIN}_matrix_routing"
    if routing_key not in hass.data:
        hass.data[routing_key] = {}

    if matrix_id not in hass.data[routing_key]:
        hass.data[routing_key][matrix_id] = {}

    hass.data[routing_key][matrix_id][output_index] = input_index

    _LOGGER.debug(
        "Matrix routing updated: %s output %d -> input %d",
        matrix_id, output_index, input_index
    )


def get_matrix_routing(
    hass: HomeAssistant,
    matrix_id: str,
    output_index: int,
) -> Optional[int]:
    """Get current matrix routing for an output."""
    routing_key = f"{DOMAIN}_matrix_routing"
    routing_data = hass.data.get(routing_key, {})
    matrix_data = routing_data.get(matrix_id, {})
    return matrix_data.get(output_index)
