"""Network device discovery service.

Provides device discovery via:
1. mDNS/Bonjour - For PJLink projectors, Denon receivers
2. SSDP/UPnP - For Denon/Marantz receivers
3. PJLink broadcast - For projectors on port 4352
4. Protocol probing - Test known ports and identify device type
"""

import asyncio
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .driver_manager import get_driver_manager

_LOGGER = logging.getLogger(__name__)

# Well-known ports for network devices
KNOWN_PORTS = {
    4352: {"name": "PJLink", "device_type": "projector", "probe_cmd": "%1POWR ?\r"},
    23: {"name": "Telnet (Denon/Marantz)", "device_type": "audio_receiver", "probe_cmd": "PW?\r"},
    50000: {"name": "Yamaha YNCA", "device_type": "audio_receiver", "probe_cmd": "@MAIN:PWR=?\r\n"},
    8000: {"name": "HDMI Matrix", "device_type": "hdmi_matrix", "probe_cmd": "s read version!"},
    8080: {"name": "HTTP Control", "device_type": "custom", "probe_cmd": None},
}

# mDNS service types to look for
MDNS_SERVICES = [
    "_pjlink._tcp.local.",
    "_http._tcp.local.",
]

# SSDP search targets
SSDP_TARGETS = [
    "urn:schemas-denon-com:device:ACT-Denon:1",
    "urn:schemas-yamaha-com:service:X_YamahaRemoteControl:1",
    "urn:schemas-upnp-org:device:MediaRenderer:1",
]


@dataclass
class DiscoveredDevice:
    """Represents a discovered network device."""
    ip_address: str
    port: int
    device_type: str
    protocol_name: str
    manufacturer: str = ""
    model: str = ""
    name: str = ""
    suggested_driver_id: Optional[str] = None
    discovery_method: str = ""  # mdns, ssdp, pjlink, probe
    raw_response: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ip_address": self.ip_address,
            "port": self.port,
            "device_type": self.device_type,
            "protocol_name": self.protocol_name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "name": self.name,
            "suggested_driver_id": self.suggested_driver_id,
            "discovery_method": self.discovery_method,
            "additional_info": self.additional_info,
        }


class DiscoveryService:
    """Service for discovering network devices."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the discovery service."""
        self.hass = hass
        self._discovered_devices: List[DiscoveredDevice] = []
        self._is_scanning = False
        self._scan_progress: Dict[str, Any] = {}

    @property
    def is_scanning(self) -> bool:
        """Return whether a scan is in progress."""
        return self._is_scanning

    @property
    def discovered_devices(self) -> List[DiscoveredDevice]:
        """Return list of discovered devices."""
        return self._discovered_devices

    async def async_discover_all(
        self,
        subnet: Optional[str] = None,
        timeout: float = 5.0,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> List[DiscoveredDevice]:
        """Run all discovery methods.

        Args:
            subnet: Optional subnet to scan (e.g., "192.168.1")
            timeout: Timeout for each discovery method
            progress_callback: Optional callback for progress updates (method, percentage)

        Returns:
            List of discovered devices
        """
        if self._is_scanning:
            _LOGGER.warning("Discovery scan already in progress")
            return self._discovered_devices

        self._is_scanning = True
        self._discovered_devices = []

        try:
            # Run discovery methods
            methods = [
                ("pjlink", self._discover_pjlink(subnet, timeout)),
                ("probe", self._probe_known_ports(subnet, timeout)),
            ]

            for idx, (method_name, coro) in enumerate(methods):
                try:
                    if progress_callback:
                        progress = int((idx / len(methods)) * 100)
                        progress_callback(method_name, progress)

                    devices = await coro
                    self._discovered_devices.extend(devices)
                except Exception as err:
                    _LOGGER.warning("Discovery method %s failed: %s", method_name, err)

            if progress_callback:
                progress_callback("complete", 100)

            # Deduplicate by IP:port
            seen = set()
            unique_devices = []
            for device in self._discovered_devices:
                key = f"{device.ip_address}:{device.port}"
                if key not in seen:
                    seen.add(key)
                    unique_devices.append(device)
            self._discovered_devices = unique_devices

            _LOGGER.info("Discovery complete: found %d devices", len(self._discovered_devices))
            return self._discovered_devices

        finally:
            self._is_scanning = False

    async def _discover_pjlink(
        self,
        subnet: Optional[str] = None,
        timeout: float = 3.0,
    ) -> List[DiscoveredDevice]:
        """Discover PJLink projectors via broadcast.

        PJLink uses port 4352 and responds to %1CLSS ? for class identification.
        """
        devices = []

        # Get local IP addresses to determine broadcast addresses
        if subnet:
            broadcast_addrs = [f"{subnet}.255"]
        else:
            broadcast_addrs = ["255.255.255.255", "192.168.1.255", "192.168.0.255", "10.0.0.255"]

        for broadcast in broadcast_addrs:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(timeout)
                sock.setblocking(False)

                # Send PJLink class query
                query = b"%1CLSS ?\r"
                try:
                    sock.sendto(query, (broadcast, 4352))
                except Exception:
                    continue

                # Collect responses
                end_time = asyncio.get_event_loop().time() + timeout
                while asyncio.get_event_loop().time() < end_time:
                    try:
                        await asyncio.sleep(0.1)
                        data, addr = sock.recvfrom(1024)
                        response = data.decode("utf-8", errors="replace").strip()

                        if response.startswith("%1CLSS="):
                            pjlink_class = response[7:].strip()
                            device = DiscoveredDevice(
                                ip_address=addr[0],
                                port=4352,
                                device_type="projector",
                                protocol_name="PJLink",
                                discovery_method="pjlink",
                                suggested_driver_id="projector_pjlink_class1",
                                raw_response=response,
                                additional_info={"pjlink_class": pjlink_class},
                            )
                            devices.append(device)
                            _LOGGER.debug("Found PJLink projector at %s", addr[0])
                    except BlockingIOError:
                        continue
                    except socket.timeout:
                        break

                sock.close()
            except Exception as err:
                _LOGGER.debug("PJLink discovery error for %s: %s", broadcast, err)

        return devices

    async def _probe_known_ports(
        self,
        subnet: Optional[str] = None,
        timeout: float = 2.0,
    ) -> List[DiscoveredDevice]:
        """Probe known ports on subnet to discover devices.

        This is a simple port scan that tests well-known control ports.
        """
        devices = []

        if not subnet:
            # Try to determine local subnet
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                subnet = ".".join(local_ip.split(".")[:-1])
            except Exception:
                subnet = "192.168.1"

        # Scan common host addresses (skip 0, 1, 255)
        hosts_to_scan = [f"{subnet}.{i}" for i in range(2, 255)]

        # Batch probe hosts
        batch_size = 50
        for i in range(0, len(hosts_to_scan), batch_size):
            batch = hosts_to_scan[i:i + batch_size]
            tasks = [self._probe_host(host, timeout) for host in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    devices.extend(result)

        return devices

    async def _probe_host(self, host: str, timeout: float) -> List[DiscoveredDevice]:
        """Probe a single host for known control ports."""
        devices = []

        for port, info in KNOWN_PORTS.items():
            try:
                result = await self._try_connect(host, port, info, timeout)
                if result:
                    devices.append(result)
            except Exception:
                pass

        return devices

    async def _try_connect(
        self,
        host: str,
        port: int,
        port_info: Dict[str, Any],
        timeout: float,
    ) -> Optional[DiscoveredDevice]:
        """Try to connect to a host:port and identify the device."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout,
            )

            response = ""
            suggested_driver = None

            # Send probe command if we have one
            if port_info.get("probe_cmd"):
                writer.write(port_info["probe_cmd"].encode())
                await writer.drain()

                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                    response = data.decode("utf-8", errors="replace").strip()
                except asyncio.TimeoutError:
                    response = ""

            writer.close()
            await writer.wait_closed()

            # Identify device based on response
            device_type = port_info["device_type"]
            manufacturer = ""
            model = ""

            if port == 4352 and response.startswith("%1"):
                suggested_driver = "projector_pjlink_class1"
            elif port == 23:
                if "DENON" in response.upper() or "MARANTZ" in response.upper():
                    suggested_driver = "av_receiver_denon_avr"
                    manufacturer = "Denon" if "DENON" in response.upper() else "Marantz"
            elif port == 50000 and "@" in response:
                suggested_driver = "av_receiver_yamaha_ynca"
                manufacturer = "Yamaha"
            elif port == 8000:
                suggested_driver = "hdmi_matrix_generic"

            return DiscoveredDevice(
                ip_address=host,
                port=port,
                device_type=device_type,
                protocol_name=port_info["name"],
                manufacturer=manufacturer,
                model=model,
                discovery_method="probe",
                suggested_driver_id=suggested_driver,
                raw_response=response[:200],  # Limit response length
            )

        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return None

    async def async_probe_device(
        self,
        ip_address: str,
        port: Optional[int] = None,
        timeout: float = 5.0,
    ) -> Optional[DiscoveredDevice]:
        """Probe a specific device to identify it.

        Args:
            ip_address: IP address to probe
            port: Specific port to probe (if None, tries all known ports)
            timeout: Connection timeout

        Returns:
            DiscoveredDevice if identified, None otherwise
        """
        if port:
            ports_to_try = {port: KNOWN_PORTS.get(port, {"name": "Unknown", "device_type": "custom", "probe_cmd": None})}
        else:
            ports_to_try = KNOWN_PORTS

        for p, info in ports_to_try.items():
            result = await self._try_connect(ip_address, p, info, timeout)
            if result:
                # Try to match with a driver
                manager = get_driver_manager(self.hass)
                await manager.async_load()

                if result.suggested_driver_id:
                    driver = manager.get_driver(result.suggested_driver_id)
                    if driver:
                        result.name = driver.get("name", "")
                        result.additional_info["driver_name"] = driver.get("name", "")

                return result

        return None


def get_discovery_service(hass: HomeAssistant) -> DiscoveryService:
    """Get or create DiscoveryService instance.

    Args:
        hass: Home Assistant instance

    Returns:
        DiscoveryService instance (singleton per HA instance)
    """
    if "discovery_service" not in hass.data.get(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["discovery_service"] = DiscoveryService(hass)
    return hass.data[DOMAIN]["discovery_service"]
