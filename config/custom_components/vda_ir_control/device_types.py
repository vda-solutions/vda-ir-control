"""Device types and predefined command sets for IR devices."""

from enum import Enum
from typing import Dict, List, NamedTuple, Optional


# Port modes
class PortMode(str, Enum):
    """Port mode configuration."""
    IR_OUTPUT = "ir_output"
    IR_INPUT = "ir_input"
    DISABLED = "disabled"


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
}


# Device type labels
DEVICE_TYPE_LABELS: Dict[DeviceType, str] = {
    DeviceType.CABLE_BOX: "Cable/Satellite Box",
    DeviceType.TV: "Television",
    DeviceType.AUDIO_RECEIVER: "Audio Receiver/Soundbar",
    DeviceType.STREAMING_DEVICE: "Streaming Device (Roku, Fire TV, etc.)",
    DeviceType.DVD_BLURAY: "DVD/Blu-ray Player",
    DeviceType.PROJECTOR: "Projector",
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
