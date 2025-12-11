"""Data coordinator for VDA IR Control."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, ATTR_BOARD_ID, ATTR_IP_ADDRESS, ATTR_MAC_ADDRESS

_LOGGER = logging.getLogger(__name__)


class VDAIRBoardCoordinator(DataUpdateCoordinator):
    """Coordinator for managing a single VDA IR board."""

    def __init__(
        self,
        hass: HomeAssistant,
        board_id: str,
        ip_address: str,
        mac_address: str,
        port: int = 80,
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"VDA IR Board {board_id}",
            update_interval=None,  # MQTT updates instead
        )
        self.board_id = board_id
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.port = port
        self.base_url = f"http://{ip_address}:{port}"
        self.session = None
        self.board_info: Dict[str, Any] = {}
        self.ir_outputs: Dict[int, Dict[str, Any]] = {}

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch board information."""
        try:
            if self.session is None:
                self.session = async_get_clientsession(self.hass)

            async with self.session.get(
                f"{self.base_url}/info",
                timeout=5,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.board_info = data
                    self._parse_board_info(data)
                    return data
                else:
                    raise UpdateFailed(f"Failed to get board info: {resp.status}")
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Board {self.board_id} is unreachable") from err
        except Exception as err:
            raise UpdateFailed(f"Error updating board {self.board_id}: {err}") from err

    def _parse_board_info(self, data: Dict[str, Any]) -> None:
        """Parse board info and extract IR outputs."""
        # Build IR output information
        output_count = data.get("output_count", 0)
        for i in range(1, output_count + 1):
            self.ir_outputs[i] = {
                "output_id": i,
                "name": f"Output {i}",
                "unique_id": f"{self.board_id}_output_{i}",
            }

    async def send_ir_code(self, output: int, code: str, protocol: str = None) -> bool:
        """Send IR code to a specific output."""
        try:
            if self.session is None:
                self.session = async_get_clientsession(self.hass)

            payload = {
                "output": output,
                "code": code,
            }
            if protocol:
                payload["protocol"] = protocol.lower()

            async with self.session.post(
                f"{self.base_url}/send_ir",
                json=payload,
                timeout=5,
            ) as resp:
                if resp.status == 200:
                    _LOGGER.debug(
                        "Successfully sent IR code to %s output %d",
                        self.board_id,
                        output,
                    )
                    return True
                else:
                    _LOGGER.error(
                        "Failed to send IR code to %s: %s",
                        self.board_id,
                        await resp.text(),
                    )
                    return False
        except Exception as err:
            _LOGGER.error("Error sending IR code: %s", err)
            return False

    async def test_output(self, output: int, duration_ms: int = 500) -> bool:
        """Test an IR output by sending a test signal."""
        try:
            if self.session is None:
                self.session = async_get_clientsession(self.hass)

            payload = {
                "output": output,
                "duration_ms": duration_ms,
            }

            async with self.session.post(
                f"{self.base_url}/test_output",
                json=payload,
                timeout=5,
            ) as resp:
                if resp.status == 200:
                    _LOGGER.debug(
                        "Tested output %d on board %s",
                        output,
                        self.board_id,
                    )
                    return True
                else:
                    _LOGGER.error("Failed to test output: %s", await resp.text())
                    return False
        except Exception as err:
            _LOGGER.error("Error testing output: %s", err)
            return False

    async def get_board_status(self) -> Optional[Dict[str, Any]]:
        """Get current board status."""
        try:
            if self.session is None:
                self.session = async_get_clientsession(self.hass)

            async with self.session.get(
                f"{self.base_url}/status",
                timeout=5,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("Failed to get board status: %s", resp.status)
                    return None
        except Exception as err:
            _LOGGER.error("Error getting board status: %s", err)
            return None


class VDAIRDiscoveryCoordinator:
    """Coordinator for discovering IR boards on the network."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the discovery coordinator."""
        self.hass = hass
        self.session = None
        self.discovered_boards: Dict[str, Dict[str, Any]] = {}

    async def discover_boards(self, subnet: str = "192.168.4") -> Dict[str, Dict[str, Any]]:
        """Discover boards by scanning subnet."""
        boards = {}

        if self.session is None:
            self.session = async_get_clientsession(self.hass)

        # Scan common IP addresses in the subnet
        tasks = []

        # Add specific test IPs first (for development/testing)
        test_ips = ["192.168.4.87", "127.0.0.1"]
        for ip in test_ips:
            tasks.append(self._check_board(ip))

        # Scan a limited range for faster discovery
        for i in range(1, 30):
            ip = f"{subnet}.{i}"
            if ip not in test_ips:  # Don't duplicate
                tasks.append(self._check_board(ip))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, dict) and "mac_address" in result:
                mac = result["mac_address"]
                boards[mac] = result

        self.discovered_boards = boards
        _LOGGER.info("Discovered %d IR boards on network", len(boards))
        return boards

    async def _check_board(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Check if a device at IP is an IR board."""
        try:
            if self.session is None:
                self.session = async_get_clientsession(self.hass)

            async with self.session.get(
                f"http://{ip_address}/info",
                timeout=2,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Verify it's an IR controller board
                    if "board_id" in data and "mac_address" in data:
                        data["ip_address"] = ip_address
                        _LOGGER.debug(f"Found IR board at {ip_address}: {data.get('board_id')}")
                        return data
        except asyncio.TimeoutError:
            _LOGGER.debug(f"Timeout checking {ip_address}")
        except Exception as err:
            _LOGGER.debug(f"Error checking {ip_address}: {err}")

        return None
