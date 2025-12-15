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
            port=data.get("port", 80),
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
    # Matrix linking (optional) - links this device to an HDMI matrix output
    matrix_device_id: Optional[str] = None  # Network/Serial device ID of the matrix
    matrix_device_type: Optional[str] = None  # "network" or "serial"
    matrix_output: Optional[str] = None  # Which output on the matrix this device is connected to

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
            "matrix_output": self.matrix_output,
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
            matrix_device_id=data.get("matrix_device_id"),
            matrix_device_type=data.get("matrix_device_type"),
            matrix_output=data.get("matrix_output"),
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
class NetworkConfig:
    """Configuration for network communication."""
    host: str = ""
    port: int = 8000              # Default TCP port (your HDMI matrix uses 8000)
    protocol: str = "tcp"         # tcp or udp
    timeout: float = 5.0
    persistent_connection: bool = True  # Keep TCP connection open
    reconnect_interval: float = 30.0    # Seconds between reconnect attempts

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "timeout": self.timeout,
            "persistent_connection": self.persistent_connection,
            "reconnect_interval": self.reconnect_interval,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NetworkConfig":
        return cls(
            host=data.get("host", ""),
            port=data.get("port", 8000),
            protocol=data.get("protocol", "tcp"),
            timeout=data.get("timeout", 5.0),
            persistent_connection=data.get("persistent_connection", True),
            reconnect_interval=data.get("reconnect_interval", 30.0),
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

    def to_dict(self) -> dict:
        return {"index": self.index, "name": self.name, "device_id": self.device_id}

    @classmethod
    def from_dict(cls, data: dict) -> "MatrixInput":
        return cls(
            index=data.get("index", 1),
            name=data.get("name", ""),
            device_id=data.get("device_id"),
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
class NetworkDevice:
    """A network-controlled device (TCP/UDP)."""
    device_id: str
    name: str
    device_type: DeviceType = DeviceType.CUSTOM
    transport_type: TransportType = TransportType.NETWORK_TCP
    location: str = ""
    network_config: NetworkConfig = field(default_factory=NetworkConfig)
    commands: Dict[str, DeviceCommand] = field(default_factory=dict)
    # Global response patterns (apply to all responses)
    global_response_patterns: List[ResponsePattern] = field(default_factory=list)
    # Matrix I/O configuration (for hdmi_matrix type)
    matrix_inputs: List[MatrixInput] = field(default_factory=list)
    matrix_outputs: List[MatrixOutput] = field(default_factory=list)

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
            "network_config": self.network_config.to_dict(),
            "commands": {k: v.to_dict() for k, v in self.commands.items()},
            "global_response_patterns": [p.to_dict() for p in self.global_response_patterns],
            "matrix_inputs": [i.to_dict() for i in self.matrix_inputs],
            "matrix_outputs": [o.to_dict() for o in self.matrix_outputs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NetworkDevice":
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
            transport_type=TransportType(data.get("transport_type", "network_tcp")),
            location=data.get("location", ""),
            network_config=NetworkConfig.from_dict(data.get("network_config", {})),
            commands=commands,
            global_response_patterns=patterns,
            matrix_inputs=matrix_inputs,
            matrix_outputs=matrix_outputs,
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
        )
