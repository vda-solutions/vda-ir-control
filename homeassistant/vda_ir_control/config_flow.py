"""Config flow for VDA IR Control integration."""

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Discovery timeout per IP
DISCOVERY_TIMEOUT = 2


class VdaIrControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for VDA IR Control."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_boards: dict[str, dict[str, Any]] = {}
        self.selected_board: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose discovery or manual entry."""
        if user_input is not None:
            if user_input.get("setup_method") == "manual":
                return await self.async_step_manual()
            # Default to discovery
            return await self.async_step_discover()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("setup_method", default="discover"): vol.In(
                        {
                            "discover": "Discover boards on network",
                            "manual": "Enter IP address manually",
                        }
                    ),
                }
            ),
            description_placeholders={},
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle board discovery step."""
        errors = {}

        if user_input is not None:
            # User selected a board
            selected_mac = user_input.get("board")
            if selected_mac and selected_mac in self.discovered_boards:
                self.selected_board = self.discovered_boards[selected_mac]
                return await self.async_step_adopt()
            errors["base"] = "no_board_selected"

        # Perform discovery
        self.discovered_boards = await self._discover_boards()

        if not self.discovered_boards:
            return self.async_abort(reason="no_boards_found")

        # Build selection options
        board_options = {
            mac: f"{info.get('board_name', 'Unknown')} ({info.get('ip_address', 'Unknown IP')})"
            for mac, info in self.discovered_boards.items()
        }

        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required("board"): vol.In(board_options),
                }
            ),
            description_placeholders={"boards_found": str(len(self.discovered_boards))},
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual IP entry step."""
        errors = {}

        if user_input is not None:
            ip_address = user_input.get("ip_address", "").strip()
            if ip_address:
                # Try to connect to the board
                board_info = await self._check_board(ip_address)
                if board_info:
                    self.selected_board = board_info
                    return await self.async_step_adopt()
                errors["base"] = "cannot_connect"
            else:
                errors["ip_address"] = "invalid_ip"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required("ip_address"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_adopt(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle board adoption/configuration step."""
        errors = {}

        if self.selected_board is None:
            return self.async_abort(reason="no_board_selected")

        mac_address = self.selected_board.get("mac_address", "")
        ip_address = self.selected_board.get("ip_address", "")
        current_name = self.selected_board.get("board_name", "IR Board")
        current_id = self.selected_board.get("board_id", "")

        # Check if already configured
        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            board_id = user_input.get("board_id", "").strip()
            board_name = user_input.get("board_name", "").strip()

            if not board_id:
                errors["board_id"] = "invalid_board_id"
            elif not board_name:
                errors["board_name"] = "invalid_board_name"
            else:
                # Try to adopt the board
                success = await self._adopt_board(ip_address, board_id, board_name)
                if success:
                    return self.async_create_entry(
                        title=board_name,
                        data={
                            "board_id": board_id,
                            "board_name": board_name,
                            "ip_address": ip_address,
                            "mac_address": mac_address,
                            "port": 8080,
                            "output_count": self.selected_board.get("output_count", 5),
                        },
                    )
                errors["base"] = "adoption_failed"

        # Generate a default board_id from MAC if not set
        if not current_id or current_id.startswith("ir-"):
            # Create a friendly default ID from MAC last 6 chars
            mac_suffix = mac_address.replace(":", "")[-6:].lower()
            default_id = f"ir_board_{mac_suffix}"
        else:
            default_id = current_id

        return self.async_show_form(
            step_id="adopt",
            data_schema=vol.Schema(
                {
                    vol.Required("board_id", default=default_id): str,
                    vol.Required("board_name", default=current_name): str,
                }
            ),
            description_placeholders={
                "ip_address": ip_address,
                "mac_address": mac_address,
            },
            errors=errors,
        )

    async def _discover_boards(self) -> dict[str, dict[str, Any]]:
        """Discover IR boards on the network."""
        boards = {}
        session = async_get_clientsession(self.hass)

        # IPs to scan - include localhost for testing
        ips_to_scan = ["127.0.0.1"]

        # Add common subnet ranges
        for subnet in ["192.168.1", "192.168.4", "192.168.0", "10.0.0"]:
            for i in range(1, 255):
                ips_to_scan.append(f"{subnet}.{i}")

        # Limit concurrent connections
        semaphore = asyncio.Semaphore(50)

        async def check_with_semaphore(ip: str) -> dict[str, Any] | None:
            async with semaphore:
                return await self._check_board(ip)

        # Run discovery with limited concurrency
        tasks = [check_with_semaphore(ip) for ip in ips_to_scan[:300]]  # Limit total IPs
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, dict) and "mac_address" in result:
                mac = result["mac_address"]
                boards[mac] = result
                _LOGGER.info("Discovered board: %s at %s", mac, result.get("ip_address"))

        return boards

    async def _check_board(self, ip_address: str) -> dict[str, Any] | None:
        """Check if a device at IP is an IR board."""
        try:
            session = async_get_clientsession(self.hass)
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                async with session.get(f"http://{ip_address}:8080/info") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "board_id" in data and "mac_address" in data:
                            data["ip_address"] = ip_address
                            return data
        except asyncio.TimeoutError:
            pass
        except Exception as err:
            _LOGGER.debug("Error checking %s: %s", ip_address, err)
        return None

    async def _adopt_board(
        self, ip_address: str, board_id: str, board_name: str
    ) -> bool:
        """Send adoption request to board."""
        try:
            session = async_get_clientsession(self.hass)
            async with asyncio.timeout(5):
                async with session.post(
                    f"http://{ip_address}:8080/adopt",
                    json={"board_id": board_id, "board_name": board_name},
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("success", False)
        except Exception as err:
            _LOGGER.error("Failed to adopt board at %s: %s", ip_address, err)
        return False
