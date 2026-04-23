"""Data models for VDA IR Control."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

from .device_types import (
    DeviceType,
    PortMode,
    TransportType,
    CommandFormat,
    LineEnding,
)


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
    port: int = 80
    total_ports: int = 8  # Default, can be configured
    board_type: str = "poe_iso"  # "poe_iso" for ESP32-POE-ISO, "devkit" for ESP32 DevKit
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
            "board_type": self.board_type,
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
            port=data.get("port", 80),
            total_ports=data.get("total_ports", 8),
            board_type=data.get("board_type", "poe_iso"),
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
class ChannelPreset:
    """A channel preset for quick tuning."""
    name: str  # e.g., "ESPN"
    number: str  # Channel number as string, e.g., "206"
    logo: str = ""  # Logo shorthand or URL, e.g., "espn" or "/local/logo.png"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "number": str(self.number),
            "logo": self.logo,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChannelPreset":
        return cls(
            name=data.get("name", ""),
            number=str(data.get("number", "")),
            logo=data.get("logo", ""),
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
    # Matrix linking (optional) - links this device to an HDMI matrix port
    matrix_device_id: Optional[str] = None  # Network/Serial device ID of the matrix
    matrix_device_type: Optional[str] = None  # "network" or "serial"
    matrix_port_type: Optional[str] = None  # "input" (source devices) or "output" (displays)
    matrix_port: Optional[str] = None  # Which port on the matrix this device is connected to
    # Screen linking (optional) - for projectors to control a motorized screen
    linked_screen_id: Optional[str] = None  # Device ID of the linked projector screen
    screen_down_delay: Optional[float] = None  # Seconds to wait before sending stop (e.g., 3.75)
    # Channel presets for quick tuning (for cable boxes, satellite receivers, etc.)
    channels: List["ChannelPreset"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "location": self.location,
            "device_profile_id": self.device_profile_id,
            "board_id": self.board_id,
            "output_port": self.output_port,
            "matrix_device_id": self.matrix_device_id,
            "matrix_device_type": self.matrix_device_type,
            "matrix_port_type": self.matrix_port_type,
            "matrix_port": self.matrix_port,
            "linked_screen_id": self.linked_screen_id,
            "screen_down_delay": self.screen_down_delay,
            "channels": [ch.to_dict() for ch in self.channels],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ControlledDevice":
        # Handle backward compatibility: matrix_output -> matrix_port
        matrix_port = data.get("matrix_port") or data.get("matrix_output")
        matrix_port_type = data.get("matrix_port_type")
        # If old data had matrix_output, assume it was an output device
        if not matrix_port_type and data.get("matrix_output"):
            matrix_port_type = "output"

        # Parse channel presets
        channels = [
            ChannelPreset.from_dict(ch) for ch in data.get("channels", [])
        ]

        return cls(
            device_id=data["device_id"],
            name=data["name"],
            location=data.get("location", ""),
            device_profile_id=data.get("device_profile_id", ""),
            board_id=data.get("board_id", ""),
            output_port=data.get("output_port", 0),
            matrix_device_id=data.get("matrix_device_id"),
            matrix_device_type=data.get("matrix_device_type"),
            matrix_port_type=matrix_port_type,
            matrix_port=matrix_port,
            linked_screen_id=data.get("linked_screen_id"),
            screen_down_delay=data.get("screen_down_delay"),
            channels=channels,
        )


# ============================================================================
# NEW MODELS FOR SERIAL/NETWORK DEVICE SUPPORT
# ============================================================================


@dataclass
class SerialConfig:
    """Configuration for serial communication."""
    port: str = ""                # /dev/ttyUSB0 for direct, board_id for bridge
    baud_rate: int = 115200
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = "N"             # N, E, O
    flow_control: str = "none"    # none, rtscts, xonxoff
    timeout: float = 5.0
    # For ESP32 serial bridge mode
    uart_number: int = 1          # UART1 or UART2 on ESP32
    rx_pin: int = 9               # GPIO for RX (Olimex: 9, DevKit: 16)
    tx_pin: int = 10              # GPIO for TX (Olimex: 10, DevKit: 17)

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "baud_rate": self.baud_rate,
            "data_bits": self.data_bits,
            "stop_bits": self.stop_bits,
            "parity": self.parity,
            "flow_control": self.flow_control,
            "timeout": self.timeout,
            "uart_number": self.uart_number,
            "rx_pin": self.rx_pin,
            "tx_pin": self.tx_pin,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SerialConfig":
        return cls(
            port=data.get("port", ""),
            baud_rate=data.get("baud_rate", 115200),
            data_bits=data.get("data_bits", 8),
            stop_bits=data.get("stop_bits", 1),
            parity=data.get("parity", "N"),
            flow_control=data.get("flow_control", "none"),
            timeout=data.get("timeout", 5.0),
            uart_number=data.get("uart_number", 1),
            rx_pin=data.get("rx_pin", 9),
            tx_pin=data.get("tx_pin", 10),
        )


@dataclass
class ResponsePattern:
    """Pattern to parse device responses for state updates."""
    pattern: str = ""             # Regex pattern to match (e.g., "input (\\d+) -> output (\\d+)")
    state_key: str = ""           # Which state this updates (e.g., "current_input", "power")
    value_group: int = 1          # Which regex group contains the value
    value_map: Dict[str, str] = field(default_factory=dict)  # Map raw values to friendly names

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "state_key": self.state_key,
            "value_group": self.value_group,
            "value_map": self.value_map,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResponsePattern":
        return cls(
            pattern=data.get("pattern", ""),
            state_key=data.get("state_key", ""),
            value_group=data.get("value_group", 1),
            value_map=data.get("value_map", {}),
        )


@dataclass
class DeviceCommand:
    """A single command for a serial/network device."""
    command_id: str               # e.g., "power_on", "input_1"
    name: str                     # Display name
    format: CommandFormat = CommandFormat.TEXT
    payload: str = ""             # The actual command (e.g., "s power 1!" or "A5 01 02")
    line_ending: LineEnding = LineEnding.NONE
    # For IR (backward compat)
    protocol: str = ""            # IR protocol (nec, samsung, etc.)
    frequency: int = 38000
    # For input selection (creates select entity options)
    is_input_option: bool = False
    input_value: str = ""         # e.g., "1", "HDMI1" - the value this represents
    # For state queries
    is_query: bool = False        # Is this a status query command?
    response_patterns: List[ResponsePattern] = field(default_factory=list)
    # For polling queries (auto-query at interval)
    poll_interval: float = 0.0    # If > 0, auto-query at this interval (seconds)

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "name": self.name,
            "format": self.format.value,
            "payload": self.payload,
            "line_ending": self.line_ending.value,
            "protocol": self.protocol,
            "frequency": self.frequency,
            "is_input_option": self.is_input_option,
            "input_value": self.input_value,
            "is_query": self.is_query,
            "response_patterns": [p.to_dict() for p in self.response_patterns],
            "poll_interval": self.poll_interval,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceCommand":
        patterns = [
            ResponsePattern.from_dict(p)
            for p in data.get("response_patterns", [])
        ]
        return cls(
            command_id=data["command_id"],
            name=data["name"],
            format=CommandFormat(data.get("format", "text")),
            payload=data.get("payload", ""),
            line_ending=LineEnding(data.get("line_ending", "none")),
            protocol=data.get("protocol", ""),
            frequency=data.get("frequency", 38000),
            is_input_option=data.get("is_input_option", False),
            input_value=data.get("input_value", ""),
            is_query=data.get("is_query", False),
            response_patterns=patterns,
            poll_interval=data.get("poll_interval", 0.0),
        )


@dataclass
class DeviceState:
    """Current state of a bidirectional device."""
    power: str = "unknown"        # on, off, unknown
    current_input: str = ""       # Current input selection
    current_output: str = ""      # For matrices: which output is selected
    volume: int = -1              # -1 means unknown
    mute: bool = False
    connected: bool = False       # Connection status
    last_response: str = ""       # Last response from device
    custom_states: Dict[str, str] = field(default_factory=dict)  # Arbitrary state key/values
    last_updated: Optional[datetime] = None

    def update(self, key: str, value: Any) -> None:
        """Update a state value."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.custom_states[key] = str(value)
        self.last_updated = datetime.now()

    def to_dict(self) -> dict:
        return {
            "power": self.power,
            "current_input": self.current_input,
            "current_output": self.current_output,
            "volume": self.volume,
            "mute": self.mute,
            "connected": self.connected,
            "last_response": self.last_response,
            "custom_states": self.custom_states,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceState":
        last_updated = None
        if data.get("last_updated"):
            last_updated = datetime.fromisoformat(data["last_updated"])
        return cls(
            power=data.get("power", "unknown"),
            current_input=data.get("current_input", ""),
            current_output=data.get("current_output", ""),
            volume=data.get("volume", -1),
            mute=data.get("mute", False),
            connected=data.get("connected", False),
            last_response=data.get("last_response", ""),
            custom_states=data.get("custom_states", {}),
            last_updated=last_updated,
        )


@dataclass
class MatrixInput:
    """Configuration for a matrix input."""
    index: int
    name: str = ""
    device_id: Optional[str] = None  # Linked source device (Apple TV, Roku, etc.)
    enabled: bool = True  # Whether this input is shown in TV source selection

    def to_dict(self) -> dict:
        return {"index": self.index, "name": self.name, "device_id": self.device_id, "enabled": self.enabled}

    @classmethod
    def from_dict(cls, data: dict) -> "MatrixInput":
        return cls(
            index=data.get("index", 1),
            name=data.get("name", ""),
            device_id=data.get("device_id"),
            enabled=data.get("enabled", True),
        )


@dataclass
class MatrixOutput:
    """Configuration for a matrix output."""
    index: int
    name: str = ""
    device_id: Optional[str] = None  # Linked display device (TV, Projector, etc.)

    def to_dict(self) -> dict:
        return {"index": self.index, "name": self.name, "device_id": self.device_id}

    @classmethod
    def from_dict(cls, data: dict) -> "MatrixOutput":
        return cls(
            index=data.get("index", 1),
            name=data.get("name", ""),
            device_id=data.get("device_id"),
        )


@dataclass
class SerialDevice:
    """A serial-controlled device (direct or via ESP32 bridge)."""
    device_id: str
    name: str
    device_type: DeviceType = DeviceType.CUSTOM
    transport_type: TransportType = TransportType.SERIAL_DIRECT
    location: str = ""
    serial_config: SerialConfig = field(default_factory=SerialConfig)
    # For serial bridge mode - which ESP32 board
    bridge_board_id: str = ""
    commands: Dict[str, DeviceCommand] = field(default_factory=dict)
    global_response_patterns: List[ResponsePattern] = field(default_factory=list)
    # For HDMI matrices - input/output configuration
    matrix_inputs: List[MatrixInput] = field(default_factory=list)
    matrix_outputs: List[MatrixOutput] = field(default_factory=list)
    # Routing command template with {input} and {output} placeholders
    # Example: "s in {input} av out {output}!" for OREI matrices
    routing_template: str = ""
    # Query template with {output} placeholder to query current input for an output
    # Example: "r av out {output}!" for OREI matrices
    query_template: str = ""

    def add_command(self, command: DeviceCommand) -> None:
        """Add a command to this device."""
        self.commands[command.command_id] = command

    def get_command(self, command_id: str) -> Optional[DeviceCommand]:
        """Get a command by ID."""
        return self.commands.get(command_id)

    def get_input_options(self) -> List[DeviceCommand]:
        """Get commands that are input options (for select entity)."""
        return [cmd for cmd in self.commands.values() if cmd.is_input_option]

    def get_query_commands(self) -> List[DeviceCommand]:
        """Get commands that are status queries."""
        return [cmd for cmd in self.commands.values() if cmd.is_query]

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "transport_type": self.transport_type.value,
            "location": self.location,
            "serial_config": self.serial_config.to_dict(),
            "bridge_board_id": self.bridge_board_id,
            "commands": {k: v.to_dict() for k, v in self.commands.items()},
            "global_response_patterns": [p.to_dict() for p in self.global_response_patterns],
            "matrix_inputs": [i.to_dict() for i in self.matrix_inputs],
            "matrix_outputs": [o.to_dict() for o in self.matrix_outputs],
            "routing_template": self.routing_template,
            "query_template": self.query_template,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SerialDevice":
        commands = {}
        for k, v in data.get("commands", {}).items():
            commands[k] = DeviceCommand.from_dict(v)

        patterns = [
            ResponsePattern.from_dict(p)
            for p in data.get("global_response_patterns", [])
        ]

        matrix_inputs = [
            MatrixInput.from_dict(i)
            for i in data.get("matrix_inputs", [])
        ]

        matrix_outputs = [
            MatrixOutput.from_dict(o)
            for o in data.get("matrix_outputs", [])
        ]

        return cls(
            device_id=data["device_id"],
            name=data["name"],
            device_type=DeviceType(data.get("device_type", "custom")),
            transport_type=TransportType(data.get("transport_type", "serial_direct")),
            location=data.get("location", ""),
            serial_config=SerialConfig.from_dict(data.get("serial_config", {})),
            bridge_board_id=data.get("bridge_board_id", ""),
            commands=commands,
            global_response_patterns=patterns,
            matrix_inputs=matrix_inputs,
            matrix_outputs=matrix_outputs,
            routing_template=data.get("routing_template", ""),
            query_template=data.get("query_template", ""),
        )


# ============================================================================
# HOME ASSISTANT REMOTE DEVICE SUPPORT (Apple TV, Roku, Android TV, etc.)
# ============================================================================


class HADeviceFamily(Enum):
    """Supported Home Assistant device families."""
    APPLE_TV = "apple_tv"
    ROKU = "roku"
    ANDROID_TV = "android_tv"
    CHROMECAST = "chromecast"
    NVIDIA_SHIELD = "nvidia_shield"
    FIRE_TV = "fire_tv"
    DIRECTV = "directv"
    CUSTOM = "custom"


# Predefined commands for each device family
HA_DEVICE_COMMANDS = {
    HADeviceFamily.APPLE_TV: [
        "up", "down", "left", "right", "select", "menu", "home", "top_menu",
        "play_pause", "pause", "play", "stop", "skip_forward", "skip_backward",
        "volume_up", "volume_down", "power"
    ],
    HADeviceFamily.ROKU: [
        "up", "down", "left", "right", "select", "back", "home", "play",
        "pause", "forward", "reverse", "volume_up", "volume_down", "volume_mute",
        "channel_up", "channel_down", "info", "replay", "search", "power"
    ],
    HADeviceFamily.ANDROID_TV: [
        "UP", "DOWN", "LEFT", "RIGHT", "CENTER", "BACK", "HOME", "MENU",
        "PLAY", "PAUSE", "STOP", "NEXT", "PREVIOUS", "VOLUME_UP", "VOLUME_DOWN",
        "MUTE", "POWER"
    ],
    HADeviceFamily.FIRE_TV: [
        "UP", "DOWN", "LEFT", "RIGHT", "CENTER", "BACK", "HOME", "MENU",
        "PLAY", "PAUSE", "STOP", "NEXT", "PREVIOUS", "VOLUME_UP", "VOLUME_DOWN",
        "MUTE", "POWER"
    ],
    HADeviceFamily.CHROMECAST: [
        "up", "down", "left", "right", "select", "back", "home",
        "play", "pause", "stop", "volume_up", "volume_down", "mute"
    ],
    HADeviceFamily.NVIDIA_SHIELD: [
        "UP", "DOWN", "LEFT", "RIGHT", "CENTER", "BACK", "HOME", "MENU",
        "PLAY", "PAUSE", "STOP", "NEXT", "PREVIOUS", "VOLUME_UP", "VOLUME_DOWN",
        "MUTE", "POWER"
    ],
    HADeviceFamily.DIRECTV: [
        "up", "down", "left", "right", "select", "menu", "guide", "info",
        "exit", "back", "play", "pause", "stop", "record", "ffwd", "rew",
        "advance", "replay", "power", "poweron", "poweroff", "chanup", "chandown",
        "prev", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "dash", "enter",
        "active", "list", "format", "red", "green", "yellow", "blue"
    ],
    HADeviceFamily.CUSTOM: [],
}


@dataclass
class HARemoteDevice:
    """A Home Assistant-controlled remote device (Apple TV, Roku, etc.)."""
    device_id: str                  # Unique ID, e.g., "living_room_apple_tv"
    name: str                       # Display name, e.g., "Living Room Apple TV"
    entity_id: str                  # HA entity ID, e.g., "remote.apple_tv" or "media_player.roku_xxx"
    device_family: HADeviceFamily = HADeviceFamily.CUSTOM
    location: str = ""              # e.g., "Living Room", "Bedroom"
    # Matrix linking (optional) - links this device to an HDMI matrix port
    matrix_device_id: Optional[str] = None  # Network/Serial device ID of the matrix
    matrix_device_type: Optional[str] = None  # "network" or "serial"
    matrix_port: Optional[str] = None  # Which input port on the matrix this device is connected to
    # Custom commands (if device_family is CUSTOM or to override defaults)
    custom_commands: List[str] = field(default_factory=list)
    # Optional media_player entity for now playing info (e.g., media_player.directv_xxx)
    media_player_entity_id: Optional[str] = None
    # Channel presets for quick tuning (for cable boxes, satellite receivers, etc.)
    channels: List["ChannelPreset"] = field(default_factory=list)

    def get_commands(self) -> List[str]:
        """Get the list of available commands for this device."""
        if self.custom_commands:
            return self.custom_commands
        return HA_DEVICE_COMMANDS.get(self.device_family, [])

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "entity_id": self.entity_id,
            "device_family": self.device_family.value,
            "location": self.location,
            "matrix_device_id": self.matrix_device_id,
            "matrix_device_type": self.matrix_device_type,
            "matrix_port": self.matrix_port,
            "custom_commands": self.custom_commands,
            "media_player_entity_id": self.media_player_entity_id,
            "channels": [ch.to_dict() for ch in self.channels],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HARemoteDevice":
        # Parse channel presets
        channels = [
            ChannelPreset.from_dict(ch) for ch in data.get("channels", [])
        ]
        return cls(
            device_id=data["device_id"],
            name=data["name"],
            entity_id=data["entity_id"],
            device_family=HADeviceFamily(data.get("device_family", "custom")),
            location=data.get("location", ""),
            matrix_device_id=data.get("matrix_device_id"),
            matrix_device_type=data.get("matrix_device_type"),
            matrix_port=data.get("matrix_port"),
            custom_commands=data.get("custom_commands", []),
            media_player_entity_id=data.get("media_player_entity_id"),
            channels=channels,
        )


# ============================================================================
# SERIAL DEVICE PROFILE SUPPORT (Community Serial Profiles)
# ============================================================================


@dataclass
class SerialDeviceProfile:
    """A serial device profile containing pre-configured commands for a device model.

    Similar to DeviceProfile for IR devices, this allows sharing working configurations
    for serial-controlled devices like HDMI matrices, projectors, displays, etc.
    """
    profile_id: str               # Unique ID, e.g., "epson_home_cinema_projector"
    name: str                     # e.g., "Epson Home Cinema Projector (RS232)"
    manufacturer: str = ""        # e.g., "Epson"
    model: str = ""               # e.g., "Home Cinema 2350"
    device_type: DeviceType = DeviceType.CUSTOM

    # Serial configuration defaults
    baud_rate: int = 9600
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = "N"

    # Commands for this device
    commands: Dict[str, DeviceCommand] = field(default_factory=dict)

    # Global response patterns that apply to all commands
    global_response_patterns: List[ResponsePattern] = field(default_factory=list)

    # For HDMI matrices
    routing_template: str = ""    # e.g., "s in {input} av out {output}!"
    query_template: str = ""      # e.g., "r av out {output}!"
    default_inputs: int = 0       # Default number of matrix inputs
    default_outputs: int = 0      # Default number of matrix outputs

    def add_command(self, command: DeviceCommand) -> None:
        """Add a command to this profile."""
        self.commands[command.command_id] = command

    def get_command(self, command_id: str) -> Optional[DeviceCommand]:
        """Get a command by ID."""
        return self.commands.get(command_id)

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "device_type": self.device_type.value,
            "baud_rate": self.baud_rate,
            "data_bits": self.data_bits,
            "stop_bits": self.stop_bits,
            "parity": self.parity,
            "commands": {k: v.to_dict() for k, v in self.commands.items()},
            "global_response_patterns": [p.to_dict() for p in self.global_response_patterns],
            "routing_template": self.routing_template,
            "query_template": self.query_template,
            "default_inputs": self.default_inputs,
            "default_outputs": self.default_outputs,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SerialDeviceProfile":
        commands = {}
        for k, v in data.get("commands", {}).items():
            commands[k] = DeviceCommand.from_dict(v)

        patterns = [
            ResponsePattern.from_dict(p)
            for p in data.get("global_response_patterns", [])
        ]

        return cls(
            profile_id=data["profile_id"],
            name=data["name"],
            manufacturer=data.get("manufacturer", ""),
            model=data.get("model", ""),
            device_type=DeviceType(data.get("device_type", "custom")),
            baud_rate=data.get("baud_rate", 9600),
            data_bits=data.get("data_bits", 8),
            stop_bits=data.get("stop_bits", 1),
            parity=data.get("parity", "N"),
            commands=commands,
            global_response_patterns=patterns,
            routing_template=data.get("routing_template", ""),
            query_template=data.get("query_template", ""),
            default_inputs=data.get("default_inputs", 0),
            default_outputs=data.get("default_outputs", 0),
        )


@dataclass
class DeviceGroupMember:
    """A member device in a group."""
    device_id: str
    device_type: str  # 'controlled' for IR devices, 'serial' for serial devices

    def to_dict(self) -> dict:
        return {"device_id": self.device_id, "device_type": self.device_type}

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceGroupMember":
        return cls(
            device_id=data["device_id"],
            device_type=data.get("device_type", "controlled"),
        )


@dataclass
class DeviceGroup:
    """A group of devices that can be controlled together."""
    group_id: str
    name: str
    members: List[DeviceGroupMember] = field(default_factory=list)
    sequence_delay_ms: int = 20  # Delay between commands in milliseconds
    location: str = ""
    power_on_repeat: int = 3  # Number of times to send discrete power_on commands
    power_off_repeat: int = 1  # Number of times to send discrete power_off commands
    channels: List[ChannelPreset] = field(default_factory=list)  # Shared channel presets

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "name": self.name,
            "members": [m.to_dict() for m in self.members],
            "sequence_delay_ms": self.sequence_delay_ms,
            "location": self.location,
            "power_on_repeat": self.power_on_repeat,
            "power_off_repeat": self.power_off_repeat,
            "channels": [ch.to_dict() for ch in self.channels],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceGroup":
        members = [
            DeviceGroupMember.from_dict(m)
            for m in data.get("members", [])
        ]
        channels = [
            ChannelPreset.from_dict(ch)
            for ch in data.get("channels", [])
        ]
        return cls(
            group_id=data["group_id"],
            name=data["name"],
            members=members,
            sequence_delay_ms=data.get("sequence_delay_ms", 20),
            location=data.get("location", ""),
            power_on_repeat=data.get("power_on_repeat", 3),
            power_off_repeat=data.get("power_off_repeat", 1),
            channels=channels,
        )
