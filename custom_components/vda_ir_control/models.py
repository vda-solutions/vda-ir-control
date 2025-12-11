"""Data models for VDA IR Control."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from .device_types import DeviceType, PortMode


@dataclass
class PortConfig:
    """Configuration for a single port on a board."""
    port_number: int
    mode: PortMode = PortMode.DISABLED
    name: str = ""  # e.g., "Bar TV 1"
    device_profile_id: Optional[str] = None  # Links to a DeviceProfile

    def to_dict(self) -> dict:
        return {
            "port_number": self.port_number,
            "mode": self.mode.value,
            "name": self.name,
            "device_profile_id": self.device_profile_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PortConfig":
        return cls(
            port_number=data["port_number"],
            mode=PortMode(data.get("mode", "disabled")),
            name=data.get("name", ""),
            device_profile_id=data.get("device_profile_id"),
        )


@dataclass
class BoardConfig:
    """Configuration for a board including all port mappings."""
    board_id: str
    board_name: str
    ip_address: str
    mac_address: str
    port: int = 8080
    total_ports: int = 8  # Default, can be configured
    ports: Dict[int, PortConfig] = field(default_factory=dict)

    def __post_init__(self):
        # Initialize all ports if not provided
        if not self.ports:
            for i in range(1, self.total_ports + 1):
                self.ports[i] = PortConfig(port_number=i)

    def get_ir_inputs(self) -> List[PortConfig]:
        """Get all ports configured as IR inputs."""
        return [p for p in self.ports.values() if p.mode == PortMode.IR_INPUT]

    def get_ir_outputs(self) -> List[PortConfig]:
        """Get all ports configured as IR outputs."""
        return [p for p in self.ports.values() if p.mode == PortMode.IR_OUTPUT]

    def to_dict(self) -> dict:
        return {
            "board_id": self.board_id,
            "board_name": self.board_name,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "port": self.port,
            "total_ports": self.total_ports,
            "ports": {k: v.to_dict() for k, v in self.ports.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BoardConfig":
        ports = {}
        if "ports" in data:
            for k, v in data["ports"].items():
                ports[int(k)] = PortConfig.from_dict(v)

        return cls(
            board_id=data["board_id"],
            board_name=data["board_name"],
            ip_address=data["ip_address"],
            mac_address=data["mac_address"],
            port=data.get("port", 8080),
            total_ports=data.get("total_ports", 8),
            ports=ports,
        )


@dataclass
class IRCode:
    """A single IR code for a command."""
    command: str  # e.g., "power_on", "channel_1"
    raw_code: str  # The raw IR code data (protocol-specific format)
    protocol: str = "raw"  # e.g., "nec", "rc5", "raw"
    frequency: int = 38000  # IR carrier frequency in Hz

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "raw_code": self.raw_code,
            "protocol": self.protocol,
            "frequency": self.frequency,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IRCode":
        return cls(
            command=data["command"],
            raw_code=data["raw_code"],
            protocol=data.get("protocol", "raw"),
            frequency=data.get("frequency", 38000),
        )


@dataclass
class DeviceProfile:
    """A device profile containing learned IR codes for a specific device model."""
    profile_id: str  # Unique ID, e.g., "xfinity_xr15_living_room"
    name: str  # e.g., "Xfinity XR15 Remote"
    device_type: DeviceType
    manufacturer: str = ""  # e.g., "Comcast", "Samsung"
    model: str = ""  # e.g., "XR15", "UN55TU8000"
    codes: Dict[str, IRCode] = field(default_factory=dict)  # command -> IRCode

    def add_code(self, command: str, raw_code: str, protocol: str = "raw", frequency: int = 38000):
        """Add or update an IR code for a command."""
        self.codes[command] = IRCode(
            command=command,
            raw_code=raw_code,
            protocol=protocol,
            frequency=frequency,
        )

    def get_code(self, command: str) -> Optional[IRCode]:
        """Get the IR code for a command."""
        return self.codes.get(command)

    def get_learned_commands(self) -> List[str]:
        """Get list of commands that have been learned."""
        return list(self.codes.keys())

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "codes": {k: v.to_dict() for k, v in self.codes.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceProfile":
        codes = {}
        if "codes" in data:
            for k, v in data["codes"].items():
                codes[k] = IRCode.from_dict(v)

        return cls(
            profile_id=data["profile_id"],
            name=data["name"],
            device_type=DeviceType(data["device_type"]),
            manufacturer=data.get("manufacturer", ""),
            model=data.get("model", ""),
            codes=codes,
        )


@dataclass
class ControlledDevice:
    """A device that is controlled via IR (e.g., a specific TV in a location)."""
    device_id: str  # Unique ID, e.g., "bar_tv_1"
    name: str  # e.g., "Bar TV 1"
    location: str = ""  # e.g., "Bar Area", "Patio"
    device_profile_id: str = ""  # Links to DeviceProfile
    board_id: str = ""  # Which board controls this device
    output_port: int = 0  # Which port on the board

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "location": self.location,
            "device_profile_id": self.device_profile_id,
            "board_id": self.board_id,
            "output_port": self.output_port,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ControlledDevice":
        return cls(
            device_id=data["device_id"],
            name=data["name"],
            location=data.get("location", ""),
            device_profile_id=data.get("device_profile_id", ""),
            board_id=data.get("board_id", ""),
            output_port=data.get("output_port", 0),
        )
