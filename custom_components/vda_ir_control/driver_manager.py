"""Driver manager for network device drivers.

Manages network device drivers from multiple sources:
1. Built-in drivers (fallback defaults)
2. Community drivers (synced from GitHub)

Priority order: Community > Built-in
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .device_types import CommandFormat, DeviceType, LineEnding, TransportType
from .models import (
    DeviceCommand,
    NetworkConfig,
    NetworkDevice,
    ResponsePattern,
    MatrixInput,
    MatrixOutput,
)
from .builtin_drivers import (
    get_builtin_driver,
    get_builtin_drivers_by_type,
    get_all_builtin_drivers,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_COMMUNITY_DRIVERS = f"{DOMAIN}_community_drivers"
STORAGE_KEY_DRIVER_META = f"{DOMAIN}_driver_meta"

# GitHub repository URLs
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/vda-solutions/vda-network-drivers/main"
GITHUB_API_BASE = "https://api.github.com/repos/vda-solutions/vda-network-drivers"
GITHUB_REPO_URL = "https://github.com/vda-solutions/vda-network-drivers"


class DriverManager:
    """Manages network device drivers from multiple sources with priority."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the driver manager.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self._community_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_COMMUNITY_DRIVERS)
        self._meta_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_DRIVER_META)

        # Cached data
        self._community_drivers: Dict[str, Dict[str, Any]] = {}
        self._meta: Dict[str, Any] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load cached community drivers from storage."""
        if self._loaded:
            return

        # Load community drivers cache
        drivers_data = await self._community_store.async_load()
        if drivers_data:
            self._community_drivers = drivers_data
            _LOGGER.debug("Loaded %d community drivers from cache", len(self._community_drivers))

        # Load metadata (last sync time, etag, etc.)
        meta_data = await self._meta_store.async_load()
        if meta_data:
            self._meta = meta_data

        self._loaded = True
        _LOGGER.info(
            "DriverManager loaded: %d community drivers, last sync: %s",
            len(self._community_drivers),
            self._meta.get("last_sync", "never")
        )

    async def async_sync_community_drivers(self) -> Dict[str, Any]:
        """Sync drivers from GitHub.

        Fetches the manifest from the community repository, then downloads
        each driver listed. Uses ETag for conditional requests.

        Returns:
            Dict with sync results including success status, counts, and messages
        """
        await self.async_load()
        session = async_get_clientsession(self.hass)

        headers = {
            "Accept": "application/json",
            "User-Agent": "VDA-IR-Control-HomeAssistant/1.0"
        }

        # Use ETag for conditional request if available
        if self._meta.get("etag"):
            headers["If-None-Match"] = self._meta["etag"]

        result = {
            "success": False,
            "drivers_added": 0,
            "drivers_updated": 0,
            "drivers_failed": 0,
            "total_drivers": 0,
            "message": "",
            "last_sync": None,
        }

        try:
            # Fetch manifest from GitHub
            manifest_url = f"{GITHUB_RAW_BASE}/manifest.json"
            _LOGGER.debug("Fetching driver manifest from %s", manifest_url)

            async with session.get(
                manifest_url,
                headers=headers,
                timeout=30
            ) as resp:
                if resp.status == 304:
                    # Not modified
                    result["success"] = True
                    result["message"] = "Drivers are up to date"
                    result["total_drivers"] = len(self._community_drivers)
                    result["last_sync"] = self._meta.get("last_sync")
                    _LOGGER.info("Community drivers are up to date (304 Not Modified)")
                    return result

                if resp.status == 404:
                    result["message"] = "Community driver repository not found"
                    _LOGGER.error("Manifest not found at %s", manifest_url)
                    return result

                if resp.status != 200:
                    result["message"] = f"GitHub error: HTTP {resp.status}"
                    _LOGGER.error("Failed to fetch manifest: HTTP %d", resp.status)
                    return result

                manifest = await resp.json(content_type=None)
                new_etag = resp.headers.get("ETag")

            # Validate manifest
            drivers_to_fetch = manifest.get("drivers", [])
            if not drivers_to_fetch:
                result["message"] = "Manifest contains no drivers"
                _LOGGER.warning("Manifest is empty")
                return result

            _LOGGER.info("Found %d drivers in manifest", len(drivers_to_fetch))

            # Fetch each driver listed in manifest
            added = 0
            updated = 0
            failed = 0

            for driver_path in drivers_to_fetch:
                try:
                    driver_url = f"{GITHUB_RAW_BASE}/{driver_path}"
                    async with session.get(driver_url, timeout=10) as driver_resp:
                        if driver_resp.status == 200:
                            driver_data = await driver_resp.json(content_type=None)
                            driver_id = driver_data.get("driver_id")

                            if driver_id:
                                if driver_id in self._community_drivers:
                                    updated += 1
                                else:
                                    added += 1
                                self._community_drivers[driver_id] = driver_data
                                _LOGGER.debug("Fetched driver: %s", driver_id)
                            else:
                                _LOGGER.warning("Driver missing driver_id: %s", driver_path)
                                failed += 1
                        else:
                            _LOGGER.warning(
                                "Failed to fetch driver %s: HTTP %d",
                                driver_path, driver_resp.status
                            )
                            failed += 1
                except Exception as err:
                    _LOGGER.warning("Error fetching driver %s: %s", driver_path, err)
                    failed += 1

            # Save to storage
            await self._community_store.async_save(self._community_drivers)

            # Update metadata
            self._meta = {
                "etag": new_etag,
                "last_sync": datetime.now().isoformat(),
                "manifest_version": manifest.get("version", "unknown"),
                "manifest_updated": manifest.get("updated", "unknown"),
            }
            await self._meta_store.async_save(self._meta)

            result["success"] = True
            result["drivers_added"] = added
            result["drivers_updated"] = updated
            result["drivers_failed"] = failed
            result["total_drivers"] = len(self._community_drivers)
            result["last_sync"] = self._meta["last_sync"]
            result["message"] = f"Synced {added} new, {updated} updated drivers"
            if failed > 0:
                result["message"] += f" ({failed} failed)"

            _LOGGER.info(
                "Community driver sync complete: %d added, %d updated, %d failed",
                added, updated, failed
            )

        except Exception as err:
            _LOGGER.error("Failed to sync community drivers: %s", err)
            result["message"] = f"Sync failed: {str(err)}"

        return result

    def get_builtin_driver(self, driver_id: str) -> Optional[Dict[str, Any]]:
        """Get a built-in driver by ID.

        Args:
            driver_id: The driver ID to look up

        Returns:
            Driver dict with _source field, or None if not found
        """
        driver = get_builtin_driver(driver_id)
        if driver:
            return {**driver, "_source": "builtin"}
        return None

    def get_community_driver(self, driver_id: str) -> Optional[Dict[str, Any]]:
        """Get a community driver by ID.

        Args:
            driver_id: The driver ID to look up

        Returns:
            Driver dict with _source field, or None if not found
        """
        driver = self._community_drivers.get(driver_id)
        if driver:
            return {**driver, "_source": "community"}
        return None

    def get_driver(self, driver_id: str, source: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a driver by ID with optional source filter.

        If source is not specified, checks community first (higher priority),
        then falls back to built-in.

        Args:
            driver_id: The driver ID to look up
            source: Optional source filter ('builtin' or 'community')

        Returns:
            Driver dict with _source field, or None if not found
        """
        if source == "builtin":
            return self.get_builtin_driver(driver_id)

        if source == "community":
            return self.get_community_driver(driver_id)

        # No source specified - check community first (higher priority)
        community = self.get_community_driver(driver_id)
        if community:
            return community

        # Fall back to built-in
        return self.get_builtin_driver(driver_id)

    def get_drivers_by_type(self, device_type: str) -> List[Dict[str, Any]]:
        """Get all drivers for a device type.

        Args:
            device_type: The device type to filter by

        Returns:
            List of driver dicts with _source field
        """
        drivers = []

        # Community drivers first (higher priority)
        for driver in self._community_drivers.values():
            if driver.get("device_type") == device_type:
                drivers.append({**driver, "_source": "community"})

        # Built-in drivers
        for driver in get_builtin_drivers_by_type(device_type):
            # Skip if we already have a community driver with same ID
            if not any(d["driver_id"] == driver["driver_id"] for d in drivers):
                drivers.append({**driver, "_source": "builtin"})

        return drivers

    def get_all_drivers(self) -> List[Dict[str, Any]]:
        """Get all drivers from all sources.

        Returns:
            List of all driver dicts with _source field
        """
        drivers = []
        seen_ids = set()

        # Community drivers first (higher priority)
        for driver in self._community_drivers.values():
            drivers.append({**driver, "_source": "community"})
            seen_ids.add(driver["driver_id"])

        # Built-in drivers
        for driver in get_all_builtin_drivers():
            if driver["driver_id"] not in seen_ids:
                drivers.append({**driver, "_source": "builtin"})

        return drivers

    def get_all_community_drivers(self) -> List[Dict[str, Any]]:
        """Get all cached community drivers.

        Returns:
            List of driver dicts with _source field
        """
        return [
            {**driver, "_source": "community"}
            for driver in self._community_drivers.values()
        ]

    def get_all_builtin_drivers(self) -> List[Dict[str, Any]]:
        """Get all built-in drivers.

        Returns:
            List of driver dicts with _source field
        """
        return [
            {**driver, "_source": "builtin"}
            for driver in get_all_builtin_drivers()
        ]

    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status information.

        Returns:
            Dict with sync status including last sync time, driver counts, etc.
        """
        return {
            "last_sync": self._meta.get("last_sync"),
            "manifest_version": self._meta.get("manifest_version"),
            "manifest_updated": self._meta.get("manifest_updated"),
            "community_driver_count": len(self._community_drivers),
            "builtin_driver_count": len(get_all_builtin_drivers()),
            "repository_url": GITHUB_REPO_URL,
        }

    def create_network_device_from_driver(
        self,
        driver_id: str,
        device_id: str,
        name: str,
        ip_address: str,
        port: Optional[int] = None,
        location: str = "",
        matrix_inputs: Optional[List[Dict[str, Any]]] = None,
        matrix_outputs: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[NetworkDevice]:
        """Create a NetworkDevice from a driver template.

        Args:
            driver_id: The driver ID to use as template
            device_id: Unique ID for the new device
            name: Display name for the device
            ip_address: IP address of the device
            port: Optional port override (uses driver default if not specified)
            location: Optional location string
            matrix_inputs: Optional list of input configurations
            matrix_outputs: Optional list of output configurations

        Returns:
            NetworkDevice instance or None if driver not found
        """
        driver = self.get_driver(driver_id)
        if not driver:
            _LOGGER.error("Driver not found: %s", driver_id)
            return None

        # Get connection config
        conn = driver.get("connection", {})
        protocol = conn.get("protocol", "tcp")

        # Create network config
        network_config = NetworkConfig(
            host=ip_address,
            port=port if port is not None else conn.get("default_port", 8000),
            protocol=protocol,
            timeout=conn.get("timeout", 5.0),
            persistent_connection=conn.get("persistent_connection", True),
            reconnect_interval=conn.get("reconnect_interval", 30.0),
        )

        # Determine device type
        device_type_str = driver.get("device_type", "custom")
        try:
            device_type = DeviceType(device_type_str)
        except ValueError:
            device_type = DeviceType.CUSTOM

        # Determine transport type
        transport_type = TransportType.NETWORK_TCP if protocol == "tcp" else TransportType.NETWORK_UDP

        # Build commands from driver
        commands: Dict[str, DeviceCommand] = {}
        driver_commands = driver.get("commands", {})

        for cmd_id, cmd_data in driver_commands.items():
            # Parse line ending
            line_ending_str = cmd_data.get("line_ending", "none")
            try:
                line_ending = LineEnding(line_ending_str)
            except ValueError:
                line_ending = LineEnding.NONE

            # Parse response patterns
            response_patterns = []
            for pattern_data in cmd_data.get("response_patterns", []):
                response_patterns.append(ResponsePattern(
                    pattern=pattern_data.get("pattern", ""),
                    state_key=pattern_data.get("state_key", ""),
                    value_group=pattern_data.get("value_group", 1),
                    value_map=pattern_data.get("value_map", {}),
                ))

            command = DeviceCommand(
                command_id=cmd_data.get("command_id", cmd_id),
                name=cmd_data.get("name", cmd_id),
                format=CommandFormat.TEXT,
                payload=cmd_data.get("payload", ""),
                line_ending=line_ending,
                is_input_option=cmd_data.get("is_input_option", False),
                input_value=cmd_data.get("input_value", ""),
                is_query=cmd_data.get("is_query", False),
                response_patterns=response_patterns,
                poll_interval=cmd_data.get("poll_interval", 0.0),
            )
            commands[cmd_id] = command

        # Build matrix I/O config if applicable
        matrix_input_list = []
        matrix_output_list = []

        if device_type == DeviceType.HDMI_MATRIX:
            matrix_cfg = driver.get("matrix_config", {})
            input_count = matrix_cfg.get("input_count", 8)
            output_count = matrix_cfg.get("output_count", 8)

            # Use provided inputs or generate defaults
            if matrix_inputs:
                for inp in matrix_inputs:
                    matrix_input_list.append(MatrixInput(
                        index=inp.get("index", 1),
                        name=inp.get("name", f"Input {inp.get('index', 1)}"),
                        device_id=inp.get("device_id"),
                    ))
            else:
                for i in range(1, input_count + 1):
                    matrix_input_list.append(MatrixInput(
                        index=i,
                        name=f"Input {i}",
                    ))

            # Use provided outputs or generate defaults
            if matrix_outputs:
                for out in matrix_outputs:
                    matrix_output_list.append(MatrixOutput(
                        index=out.get("index", 1),
                        name=out.get("name", f"Output {out.get('index', 1)}"),
                        device_id=out.get("device_id"),
                    ))
            else:
                for i in range(1, output_count + 1):
                    matrix_output_list.append(MatrixOutput(
                        index=i,
                        name=f"Output {i}",
                    ))

        # Create the NetworkDevice
        device = NetworkDevice(
            device_id=device_id,
            name=name,
            device_type=device_type,
            transport_type=transport_type,
            location=location,
            network_config=network_config,
            commands=commands,
            matrix_inputs=matrix_input_list,
            matrix_outputs=matrix_output_list,
        )

        _LOGGER.info(
            "Created network device '%s' from driver '%s' with %d commands",
            name, driver_id, len(commands)
        )

        return device

    def get_routing_command(
        self,
        driver_id: str,
        input_num: int,
        output_num: int,
    ) -> Optional[str]:
        """Get the routing command for a matrix driver.

        Args:
            driver_id: The driver ID
            input_num: Input number (1-based)
            output_num: Output number (1-based, 0 for all outputs)

        Returns:
            Command string or None if not a matrix driver
        """
        driver = self.get_driver(driver_id)
        if not driver:
            return None

        matrix_cfg = driver.get("matrix_config", {})
        template = matrix_cfg.get("routing_command_template")

        if not template:
            return None

        # If output is 0, use all-outputs template if available
        if output_num == 0:
            all_template = matrix_cfg.get("all_outputs_template")
            if all_template:
                return all_template.format(input=input_num)

        return template.format(input=input_num, output=output_num)


def get_driver_manager(hass: HomeAssistant) -> DriverManager:
    """Get or create DriverManager instance.

    Args:
        hass: Home Assistant instance

    Returns:
        DriverManager instance (singleton per HA instance)
    """
    if "driver_manager" not in hass.data.get(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["driver_manager"] = DriverManager(hass)
    return hass.data[DOMAIN]["driver_manager"]
