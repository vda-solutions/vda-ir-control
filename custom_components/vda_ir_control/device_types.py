"""Device types and predefined command sets for IR devices."""

from enum import Enum
from typing import Dict, List, NamedTuple, Optional


# Port modes
class PortMode(str, Enum):
    """Port mode configuration."""
    IR_OUTPUT = "ir_output"
    IR_INPUT = "ir_input"
    DISABLED = "disabled"


# Transport types for device communication
class TransportType(str, Enum):
    """Transport type for device communication."""
    IR = "ir"                        # IR via ESP32 board (existing)
    SERIAL_BRIDGE = "serial_bridge"  # Serial via ESP32 as bridge
    SERIAL_DIRECT = "serial_direct"  # Serial directly from HA server
    NETWORK_TCP = "network_tcp"      # TCP socket connection
    NETWORK_UDP = "network_udp"      # UDP datagram


# Command format types
class CommandFormat(str, Enum):
    """Command format type."""
    IR_CODE = "ir_code"    # IR protocol code (existing)
    TEXT = "text"          # Text string (ASCII)
    HEX = "hex"            # Hex/binary data (e.g., "A5 01 02 FF")


# Line endings for text commands
class LineEnding(str, Enum):
    """Line ending for text commands."""
    NONE = "none"
    CR = "cr"
    LF = "lf"
    CRLF = "crlf"
    EXCLAMATION = "!"  # For devices like HDMI matrices that use ! as delimiter

    def get_bytes(self) -> bytes:
        """Get the actual bytes for this line ending."""
        endings = {
            "none": b"",
            "cr": b"\r",
            "lf": b"\n",
            "crlf": b"\r\n",
            "!": b"!",
        }
        return endings.get(self.value, b"")


class GPIOPin(NamedTuple):
    """GPIO pin definition for ESP32-POE-ISO board."""
    gpio: int
    name: str
    can_input: bool
    can_output: bool
    notes: str
    ir_capable: bool  # Whether suitable for IR (PWM capable for output)


# ESP32-POE-ISO GPIO Pin Definitions
# Based on official Olimex ESP32-POE-ISO pinout diagram
# Pins reserved for Ethernet: GPIO17, GPIO18, GPIO19, GPIO21, GPIO22, GPIO23, GPIO25, GPIO26, GPIO27
# Pins shared with SD card (usable if no SD): GPIO2, GPIO14, GPIO15
# Input-only pins: GPIO34, GPIO35, GPIO36, GPIO39
ESP32_POE_ISO_PINS: Dict[int, GPIOPin] = {
    # FREE pins - output capable
    0: GPIOPin(0, "GPIO0", True, True, "FREE - Boot strapping, free after boot (WROOM only)", True),
    1: GPIOPin(1, "GPIO1", True, True, "FREE - USB programming, free after boot", True),
    2: GPIOPin(2, "GPIO2", True, True, "MUX SD CARD - Shared with SD card, 2.2k pull-up", True),
    3: GPIOPin(3, "GPIO3", True, True, "FREE - USB programming, free after boot", True),
    4: GPIOPin(4, "GPIO4", True, True, "FREE - UEXT connector", True),
    5: GPIOPin(5, "GPIO5", True, True, "FREE - 10k pull-up", True),
    13: GPIOPin(13, "GPIO13", True, True, "FREE - UEXT connector, 2.2k pull-up", True),
    14: GPIOPin(14, "GPIO14", True, True, "MUX SD CARD - Shared with SD card", True),
    15: GPIOPin(15, "GPIO15", True, True, "MUX SD CARD - Shared with SD card, 10k pull-up", True),
    16: GPIOPin(16, "GPIO16", True, True, "FREE - UEXT connector, 2.2k pull-up (NOT on WROVER)", True),
    32: GPIOPin(32, "GPIO32", True, True, "FREE", True),
    33: GPIOPin(33, "GPIO33", True, True, "FREE", True),

    # Input-only pins (good for IR receiver)
    34: GPIOPin(34, "GPIO34", True, False, "BUT1 - Input only, user button, 10k pull-up", True),
    35: GPIOPin(35, "GPIO35", True, False, "BAT M - Input only, battery voltage measurement", True),
    36: GPIOPin(36, "GPIO36", True, False, "FREE - Input only, UEXT connector, 2.2k pull-up", True),
    39: GPIOPin(39, "GPIO39", True, False, "PWR SENSE - Input only, external power detection", True),
}

# Reserved pins (Ethernet) - NOT available for IR use
ESP32_POE_ISO_RESERVED: Dict[int, str] = {
    17: "EMAC_CLK - Ethernet clock (RMII)",
    18: "MDIO - Ethernet management data",
    19: "EMAC_TXD0 - Ethernet TX data 0",
    21: "EMAC_TX_EN - Ethernet TX enable",
    22: "EMAC_TXD1 - Ethernet TX data 1",
    23: "MDC - Ethernet management clock",
    25: "EMAC_RXD0 - Ethernet RX data 0",
    26: "EMAC_RXD1 - Ethernet RX data 1",
    27: "EMAC_RX_DV - Ethernet RX data valid",
}


def get_available_ir_pins(for_input: bool = False, for_output: bool = False) -> List[GPIOPin]:
    """Get list of GPIO pins available for IR use.

    Args:
        for_input: Filter for pins that can be used as IR input (receivers)
        for_output: Filter for pins that can be used as IR output (transmitters)

    Returns:
        List of GPIOPin objects that match the criteria
    """
    pins = []
    for gpio, pin in ESP32_POE_ISO_PINS.items():
        if not pin.ir_capable:
            continue
        if for_input and not pin.can_input:
            continue
        if for_output and not pin.can_output:
            continue
        pins.append(pin)
    return sorted(pins, key=lambda p: p.gpio)


def get_gpio_info(gpio: int) -> Optional[GPIOPin]:
    """Get information about a specific GPIO pin."""
    return ESP32_POE_ISO_PINS.get(gpio)


def is_gpio_reserved(gpio: int) -> bool:
    """Check if a GPIO pin is reserved (e.g., for Ethernet)."""
    return gpio in ESP32_POE_ISO_RESERVED


def get_reserved_reason(gpio: int) -> Optional[str]:
    """Get the reason a GPIO pin is reserved."""
    return ESP32_POE_ISO_RESERVED.get(gpio)


# Device types with their associated commands
class DeviceType(str, Enum):
    """Supported device types."""
    CABLE_BOX = "cable_box"
    TV = "tv"
    AUDIO_RECEIVER = "audio_receiver"
    STREAMING_DEVICE = "streaming_device"
    DVD_BLURAY = "dvd_bluray"
    PROJECTOR = "projector"
    # New serial/network device types
    HDMI_MATRIX = "hdmi_matrix"
    HDMI_SWITCH = "hdmi_switch"
    AV_PROCESSOR = "av_processor"
    SERIAL_RELAY = "serial_relay"
    CUSTOM = "custom"


# Predefined command sets by device type
# These are the standard command names that ensure consistency
DEVICE_COMMANDS: Dict[DeviceType, List[str]] = {
    DeviceType.CABLE_BOX: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Digits
        "digit_0",
        "digit_1",
        "digit_2",
        "digit_3",
        "digit_4",
        "digit_5",
        "digit_6",
        "digit_7",
        "digit_8",
        "digit_9",
        # Channel
        "channel_up",
        "channel_down",
        "channel_enter",
        "channel_prev",
        # Volume (if box controls TV volume)
        "volume_up",
        "volume_down",
        "mute",
        # Navigation
        "guide",
        "menu",
        "info",
        "exit",
        "back",
        "arrow_up",
        "arrow_down",
        "arrow_left",
        "arrow_right",
        "select",
        # DVR
        "play",
        "pause",
        "stop",
        "rewind",
        "fast_forward",
        "record",
        # Favorites
        "favorite",
        "last",
        # Page
        "page_up",
        "page_down",
    ],

    DeviceType.TV: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Volume
        "volume_up",
        "volume_down",
        "mute",
        # Input selection
        "input_hdmi1",
        "input_hdmi2",
        "input_hdmi3",
        "input_hdmi4",
        "input_component",
        "input_composite",
        "input_antenna",
        "input_cycle",
        # Navigation (for smart TVs)
        "menu",
        "exit",
        "arrow_up",
        "arrow_down",
        "arrow_left",
        "arrow_right",
        "select",
        "back",
        "home",
        # Picture
        "picture_mode",
        "aspect_ratio",
    ],

    DeviceType.AUDIO_RECEIVER: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Volume
        "volume_up",
        "volume_down",
        "mute",
        # Input selection
        "input_hdmi1",
        "input_hdmi2",
        "input_hdmi3",
        "input_optical",
        "input_coax",
        "input_aux",
        "input_bluetooth",
        "input_cycle",
        # Sound modes
        "sound_mode",
        "bass_up",
        "bass_down",
        "treble_up",
        "treble_down",
    ],

    DeviceType.STREAMING_DEVICE: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Navigation
        "home",
        "menu",
        "back",
        "arrow_up",
        "arrow_down",
        "arrow_left",
        "arrow_right",
        "select",
        # Playback
        "play",
        "pause",
        "play_pause",
        "rewind",
        "fast_forward",
        # Volume (if supported)
        "volume_up",
        "volume_down",
        "mute",
        # Voice
        "voice",
    ],

    DeviceType.DVD_BLURAY: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Tray
        "eject",
        # Playback
        "play",
        "pause",
        "stop",
        "rewind",
        "fast_forward",
        "skip_prev",
        "skip_next",
        # Navigation
        "menu",
        "title_menu",
        "popup_menu",
        "arrow_up",
        "arrow_down",
        "arrow_left",
        "arrow_right",
        "select",
        "back",
        # Audio/Subtitle
        "audio_track",
        "subtitle",
    ],

    DeviceType.PROJECTOR: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Input
        "input_hdmi1",
        "input_hdmi2",
        "input_vga",
        "input_component",
        "input_cycle",
        # Picture
        "picture_mode",
        "brightness_up",
        "brightness_down",
        "contrast_up",
        "contrast_down",
        "keystone_up",
        "keystone_down",
        "zoom_in",
        "zoom_out",
        "focus_near",
        "focus_far",
        # Other
        "menu",
        "exit",
        "freeze",
        "blank",
    ],

    DeviceType.CUSTOM: [
        # Empty - user defines all commands
    ],

    DeviceType.HDMI_MATRIX: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Input routing (x to y)
        "input_1",
        "input_2",
        "input_3",
        "input_4",
        "input_5",
        "input_6",
        "input_7",
        "input_8",
        # All outputs to input x
        "all_to_input_1",
        "all_to_input_2",
        "all_to_input_3",
        "all_to_input_4",
        "all_to_input_5",
        "all_to_input_6",
        "all_to_input_7",
        "all_to_input_8",
        # Query commands
        "query_status",
        "query_routing",
        "query_power",
        # System
        "reboot",
        "beep_on",
        "beep_off",
        "lock_panel",
        "unlock_panel",
        # Presets
        "save_preset_1",
        "save_preset_2",
        "save_preset_3",
        "save_preset_4",
        "recall_preset_1",
        "recall_preset_2",
        "recall_preset_3",
        "recall_preset_4",
        # CEC control (pass-through to connected devices)
        "cec_power_on",
        "cec_power_off",
        "cec_volume_up",
        "cec_volume_down",
        "cec_mute",
    ],

    DeviceType.HDMI_SWITCH: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Input selection
        "input_1",
        "input_2",
        "input_3",
        "input_4",
        "input_5",
        # Query
        "query_status",
        "query_input",
    ],

    DeviceType.AV_PROCESSOR: [
        # Power
        "power_on",
        "power_off",
        "power_toggle",
        # Volume
        "volume_up",
        "volume_down",
        "mute",
        "set_volume",
        # Input selection
        "input_1",
        "input_2",
        "input_3",
        "input_4",
        "input_5",
        "input_6",
        # Query
        "query_status",
        "query_volume",
        "query_input",
    ],

    DeviceType.SERIAL_RELAY: [
        # Relay control
        "relay_1_on",
        "relay_1_off",
        "relay_2_on",
        "relay_2_off",
        "relay_3_on",
        "relay_3_off",
        "relay_4_on",
        "relay_4_off",
        "all_on",
        "all_off",
        # Query
        "query_status",
    ],
}


# Human-readable labels for commands
COMMAND_LABELS: Dict[str, str] = {
    # Power
    "power_on": "Power On",
    "power_off": "Power Off",
    "power_toggle": "Power Toggle",
    # Digits
    "digit_0": "0",
    "digit_1": "1",
    "digit_2": "2",
    "digit_3": "3",
    "digit_4": "4",
    "digit_5": "5",
    "digit_6": "6",
    "digit_7": "7",
    "digit_8": "8",
    "digit_9": "9",
    # Channel
    "channel_up": "Channel Up",
    "channel_down": "Channel Down",
    "channel_enter": "Channel Enter",
    "channel_prev": "Previous Channel",
    # Volume
    "volume_up": "Volume Up",
    "volume_down": "Volume Down",
    "mute": "Mute",
    # Navigation
    "guide": "Guide",
    "menu": "Menu",
    "info": "Info",
    "exit": "Exit",
    "back": "Back",
    "home": "Home",
    "arrow_up": "Up",
    "arrow_down": "Down",
    "arrow_left": "Left",
    "arrow_right": "Right",
    "select": "Select/OK",
    # Playback
    "play": "Play",
    "pause": "Pause",
    "play_pause": "Play/Pause",
    "stop": "Stop",
    "rewind": "Rewind",
    "fast_forward": "Fast Forward",
    "skip_prev": "Previous",
    "skip_next": "Next",
    "record": "Record",
    # Input
    "input_hdmi1": "HDMI 1",
    "input_hdmi2": "HDMI 2",
    "input_hdmi3": "HDMI 3",
    "input_hdmi4": "HDMI 4",
    "input_component": "Component",
    "input_composite": "Composite",
    "input_antenna": "Antenna/TV",
    "input_optical": "Optical",
    "input_coax": "Coaxial",
    "input_aux": "AUX",
    "input_bluetooth": "Bluetooth",
    "input_vga": "VGA",
    "input_cycle": "Input Cycle",
    # DVD/Bluray
    "eject": "Eject",
    "title_menu": "Title Menu",
    "popup_menu": "Popup Menu",
    "audio_track": "Audio Track",
    "subtitle": "Subtitle",
    # Other
    "favorite": "Favorites",
    "last": "Last",
    "page_up": "Page Up",
    "page_down": "Page Down",
    "picture_mode": "Picture Mode",
    "aspect_ratio": "Aspect Ratio",
    "sound_mode": "Sound Mode",
    "bass_up": "Bass Up",
    "bass_down": "Bass Down",
    "treble_up": "Treble Up",
    "treble_down": "Treble Down",
    "voice": "Voice",
    "brightness_up": "Brightness Up",
    "brightness_down": "Brightness Down",
    "contrast_up": "Contrast Up",
    "contrast_down": "Contrast Down",
    "keystone_up": "Keystone Up",
    "keystone_down": "Keystone Down",
    "zoom_in": "Zoom In",
    "zoom_out": "Zoom Out",
    "focus_near": "Focus Near",
    "focus_far": "Focus Far",
    "freeze": "Freeze",
    "blank": "Blank Screen",
    # HDMI Matrix/Switch commands
    "input_1": "Input 1",
    "input_2": "Input 2",
    "input_3": "Input 3",
    "input_4": "Input 4",
    "input_5": "Input 5",
    "input_6": "Input 6",
    "input_7": "Input 7",
    "input_8": "Input 8",
    "all_to_input_1": "All Outputs → Input 1",
    "all_to_input_2": "All Outputs → Input 2",
    "all_to_input_3": "All Outputs → Input 3",
    "all_to_input_4": "All Outputs → Input 4",
    "all_to_input_5": "All Outputs → Input 5",
    "all_to_input_6": "All Outputs → Input 6",
    "all_to_input_7": "All Outputs → Input 7",
    "all_to_input_8": "All Outputs → Input 8",
    "query_status": "Query Status",
    "query_routing": "Query Routing",
    "query_power": "Query Power",
    "query_input": "Query Input",
    "query_volume": "Query Volume",
    "beep_on": "Beep On",
    "beep_off": "Beep Off",
    "lock_panel": "Lock Front Panel",
    "unlock_panel": "Unlock Front Panel",
    "save_preset_1": "Save Preset 1",
    "save_preset_2": "Save Preset 2",
    "save_preset_3": "Save Preset 3",
    "save_preset_4": "Save Preset 4",
    "recall_preset_1": "Recall Preset 1",
    "recall_preset_2": "Recall Preset 2",
    "recall_preset_3": "Recall Preset 3",
    "recall_preset_4": "Recall Preset 4",
    "cec_power_on": "CEC Power On",
    "cec_power_off": "CEC Power Off",
    "cec_volume_up": "CEC Volume Up",
    "cec_volume_down": "CEC Volume Down",
    "cec_mute": "CEC Mute",
    # Relay commands
    "relay_1_on": "Relay 1 On",
    "relay_1_off": "Relay 1 Off",
    "relay_2_on": "Relay 2 On",
    "relay_2_off": "Relay 2 Off",
    "relay_3_on": "Relay 3 On",
    "relay_3_off": "Relay 3 Off",
    "relay_4_on": "Relay 4 On",
    "relay_4_off": "Relay 4 Off",
    "all_on": "All On",
    "all_off": "All Off",
    "set_volume": "Set Volume",
}


# Device type labels
DEVICE_TYPE_LABELS: Dict[DeviceType, str] = {
    DeviceType.CABLE_BOX: "Cable/Satellite Box",
    DeviceType.TV: "Television",
    DeviceType.AUDIO_RECEIVER: "Audio Receiver/Soundbar",
    DeviceType.STREAMING_DEVICE: "Streaming Device (Roku, Fire TV, etc.)",
    DeviceType.DVD_BLURAY: "DVD/Blu-ray Player",
    DeviceType.PROJECTOR: "Projector",
    DeviceType.HDMI_MATRIX: "HDMI Matrix",
    DeviceType.HDMI_SWITCH: "HDMI Switch",
    DeviceType.AV_PROCESSOR: "AV Processor",
    DeviceType.SERIAL_RELAY: "Serial Relay Controller",
    DeviceType.CUSTOM: "Custom Device",
}


def get_commands_for_device_type(device_type: DeviceType) -> List[str]:
    """Get the list of commands available for a device type."""
    return DEVICE_COMMANDS.get(device_type, [])


def get_command_label(command: str) -> str:
    """Get the human-readable label for a command."""
    return COMMAND_LABELS.get(command, command.replace("_", " ").title())


def get_device_type_label(device_type: DeviceType) -> str:
    """Get the human-readable label for a device type."""
    return DEVICE_TYPE_LABELS.get(device_type, device_type.value)
