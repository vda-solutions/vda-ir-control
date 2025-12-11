"""Pre-loaded IR code profiles for common devices.

These profiles contain IR codes for popular TV brands and cable boxes.
Codes are in hex format with their protocol specified.

Sources:
- Tasmota IR Codes: https://tasmota.github.io/docs/Codes-for-IR-Remotes/
- IRremoteESP8266: https://github.com/crankyoldgit/IRremoteESP8266
- Remote Central: https://www.remotecentral.com/cgi-bin/codes/
- IRDB: https://github.com/probonopd/irdb
"""

from typing import Dict, List, Any

# IR Profile structure:
# {
#     "profile_id": "unique_id",
#     "name": "Display Name",
#     "manufacturer": "Brand",
#     "device_type": "tv" | "cable_box" | "soundbar" | "streaming",
#     "protocol": "SAMSUNG" | "NEC" | "SONY" | etc,
#     "bits": 32,  # Protocol bit length
#     "codes": {
#         "command_name": "hex_code",
#         ...
#     }
# }

BUILTIN_PROFILES: List[Dict[str, Any]] = [
    # ==================== SAMSUNG TVs ====================
    {
        "profile_id": "samsung_tv_generic",
        "name": "Samsung TV (Generic)",
        "manufacturer": "Samsung",
        "device_type": "tv",
        "protocol": "SAMSUNG",
        "bits": 32,
        "codes": {
            "power": "E0E040BF",
            "power_on": "E0E09966",
            "power_off": "E0E019E6",
            "volume_up": "E0E0E01F",
            "volume_down": "E0E0D02F",
            "mute": "E0E0F00F",
            "channel_up": "E0E048B7",
            "channel_down": "E0E008F7",
            "source": "E0E0807F",
            "hdmi": "E0E0D12E",
            "menu": "E0E058A7",
            "enter": "E0E016E9",
            "exit": "E0E0B44B",
            "up": "E0E006F9",
            "down": "E0E08679",
            "left": "E0E0A659",
            "right": "E0E046B9",
            "back": "E0E01AE5",
            "home": "E0E09E61",
            "guide": "E0E0F20D",
            "info": "E0E0F807",
            "0": "E0E08877",
            "1": "E0E020DF",
            "2": "E0E0A05F",
            "3": "E0E0609F",
            "4": "E0E010EF",
            "5": "E0E0906F",
            "6": "E0E050AF",
            "7": "E0E030CF",
            "8": "E0E0B04F",
            "9": "E0E0708F",
        }
    },

    # ==================== LG TVs ====================
    {
        "profile_id": "lg_tv_generic",
        "name": "LG TV (Generic)",
        "manufacturer": "LG",
        "device_type": "tv",
        "protocol": "NEC",
        "bits": 32,
        "codes": {
            "power": "20DF10EF",
            "volume_up": "20DF40BF",
            "volume_down": "20DFC03F",
            "mute": "20DF906F",
            "channel_up": "20DF00FF",
            "channel_down": "20DF807F",
            "source": "20DFD02F",
            "menu": "20DFC23D",
            "enter": "20DF22DD",
            "exit": "20DFDA25",
            "up": "20DF02FD",
            "down": "20DF827D",
            "left": "20DFE01F",
            "right": "20DF609F",
            "back": "20DF14EB",
            "home": "20DF3EC1",
            "guide": "20DFD52A",
            "info": "20DF55AA",
            "0": "20DF08F7",
            "1": "20DF8877",
            "2": "20DF48B7",
            "3": "20DFC837",
            "4": "20DF28D7",
            "5": "20DFA857",
            "6": "20DF6897",
            "7": "20DFE817",
            "8": "20DF18E7",
            "9": "20DF9867",
            # Discrete inputs
            "hdmi1": "20DF738C",
            "hdmi2": "20DF33CC",
            "hdmi3": "20DF9768",
            "hdmi4": "20DF5DA2",
            "av1": "20DF5AA5",
            "component1": "20DFFD02",
        }
    },

    # ==================== SONY TVs ====================
    {
        "profile_id": "sony_tv_generic",
        "name": "Sony TV (Generic)",
        "manufacturer": "Sony",
        "device_type": "tv",
        "protocol": "SONY",
        "bits": 12,
        "codes": {
            "power": "A90",
            "power_on": "750",
            "power_off": "F50",
            "volume_up": "490",
            "volume_down": "C90",
            "mute": "290",
            "channel_up": "090",
            "channel_down": "890",
            "source": "A50",
            "menu": "070",
            "enter": "A70",
            "exit": "C70",
            "up": "2F0",
            "down": "AF0",
            "left": "2D0",
            "right": "CD0",
            "guide": "6D0",
            "info": "5D0",
            "0": "910",
            "1": "010",
            "2": "810",
            "3": "410",
            "4": "C10",
            "5": "210",
            "6": "A10",
            "7": "610",
            "8": "E10",
            "9": "110",
        }
    },

    # ==================== VIZIO TVs ====================
    {
        "profile_id": "vizio_tv_generic",
        "name": "Vizio TV (Generic)",
        "manufacturer": "Vizio",
        "device_type": "tv",
        "protocol": "NEC",
        "bits": 32,
        "codes": {
            "power": "20DF10EF",
            "power_on": "20DF23DC",
            "power_off": "20DFA35C",
            "volume_up": "20DF40BF",
            "volume_down": "20DFC03F",
            "mute": "20DF906F",
            "channel_up": "20DF00FF",
            "channel_down": "20DF807F",
            "source": "20DFD02F",
            "menu": "20DFC23D",
            "enter": "20DF22DD",
            "exit": "20DFDA25",
            "up": "20DF02FD",
            "down": "20DF827D",
            "left": "20DFE01F",
            "right": "20DF609F",
            "back": "20DF14EB",
            "info": "20DF55AA",
            "0": "20DF08F7",
            "1": "20DF8877",
            "2": "20DF48B7",
            "3": "20DFC837",
            "4": "20DF28D7",
            "5": "20DFA857",
            "6": "20DF6897",
            "7": "20DFE817",
            "8": "20DF18E7",
            "9": "20DF9867",
            # Discrete inputs
            "hdmi1": "20DF738C",
            "hdmi2": "20DF33CC",
            "component": "20DFFD02",
            "av": "20DF5AA5",
        }
    },

    # ==================== TCL/Roku TVs ====================
    {
        "profile_id": "tcl_roku_tv",
        "name": "TCL Roku TV",
        "manufacturer": "TCL",
        "device_type": "tv",
        "protocol": "NEC",
        "bits": 32,
        "codes": {
            "power": "57E3E817",
            "volume_up": "57E3F807",
            "volume_down": "57E37887",
            "mute": "57E3B847",
            "home": "57E3C03F",
            "back": "57E36699",
            "up": "57E39867",
            "down": "57E3CC33",
            "left": "57E37C83",
            "right": "57E3BC43",
            "enter": "57E354AB",
            "replay": "57E31CE3",
            "options": "57E36C93",
            "rewind": "57E32CD3",
            "play_pause": "57E3AC53",
            "fast_forward": "57E3EC13",
        }
    },

    # ==================== HISENSE TVs ====================
    {
        "profile_id": "hisense_tv_generic",
        "name": "Hisense TV (Generic)",
        "manufacturer": "Hisense",
        "device_type": "tv",
        "protocol": "NEC",
        "bits": 32,
        "codes": {
            "power": "20DF10EF",
            "volume_up": "20DF40BF",
            "volume_down": "20DFC03F",
            "mute": "20DF906F",
            "channel_up": "20DF00FF",
            "channel_down": "20DF807F",
            "source": "20DFD02F",
            "menu": "20DFC23D",
            "enter": "20DF22DD",
            "exit": "20DFDA25",
            "up": "20DF02FD",
            "down": "20DF827D",
            "left": "20DFE01F",
            "right": "20DF609F",
            "back": "20DF14EB",
            "home": "20DF3EC1",
            "0": "20DF08F7",
            "1": "20DF8877",
            "2": "20DF48B7",
            "3": "20DFC837",
            "4": "20DF28D7",
            "5": "20DFA857",
            "6": "20DF6897",
            "7": "20DFE817",
            "8": "20DF18E7",
            "9": "20DF9867",
        }
    },

    # ==================== CABLE BOXES ====================

    # DirecTV (RC66 style remotes)
    {
        "profile_id": "directv_receiver",
        "name": "DirecTV Receiver",
        "manufacturer": "DirecTV",
        "device_type": "cable_box",
        "protocol": "DIRECTV",
        "bits": 0,  # Uses raw timing
        "codes": {
            # Note: DirecTV uses a proprietary protocol
            # These are simplified command identifiers
            "power": "POWER",
            "guide": "GUIDE",
            "menu": "MENU",
            "list": "LIST",
            "exit": "EXIT",
            "info": "INFO",
            "up": "UP",
            "down": "DOWN",
            "left": "LEFT",
            "right": "RIGHT",
            "select": "SELECT",
            "channel_up": "CHANUP",
            "channel_down": "CHANDN",
            "prev": "PREV",
            "play": "PLAY",
            "pause": "PAUSE",
            "rewind": "REW",
            "fast_forward": "FFWD",
            "stop": "STOP",
            "record": "REC",
            "0": "0",
            "1": "1",
            "2": "2",
            "3": "3",
            "4": "4",
            "5": "5",
            "6": "6",
            "7": "7",
            "8": "8",
            "9": "9",
        }
    },

    # ==================== STREAMING DEVICES ====================

    # Apple TV
    {
        "profile_id": "apple_tv",
        "name": "Apple TV",
        "manufacturer": "Apple",
        "device_type": "streaming",
        "protocol": "NEC",
        "bits": 32,
        "codes": {
            "menu": "77E15080",
            "up": "77E15020",
            "down": "77E130D0",
            "left": "77E11090",
            "right": "77E1E010",
            "select": "77E1BA45",
            "play_pause": "77E17A85",
        }
    },

    # Amazon Fire TV
    {
        "profile_id": "amazon_firetv",
        "name": "Amazon Fire TV",
        "manufacturer": "Amazon",
        "device_type": "streaming",
        "protocol": "NEC",
        "bits": 32,
        "codes": {
            "power": "00FF00FF",
            "home": "00FF50AF",
            "back": "00FF40BF",
            "menu": "00FF906F",
            "up": "00FF20DF",
            "down": "00FF10EF",
            "left": "00FF807F",
            "right": "00FFC03F",
            "select": "00FFA05F",
            "play_pause": "00FF609F",
            "rewind": "00FFC837",
            "fast_forward": "00FF28D7",
        }
    },

    # Roku
    {
        "profile_id": "roku_streaming",
        "name": "Roku Streaming Device",
        "manufacturer": "Roku",
        "device_type": "streaming",
        "protocol": "NEC",
        "bits": 32,
        "codes": {
            "power": "57E3E817",
            "home": "57E3C03F",
            "back": "57E36699",
            "up": "57E39867",
            "down": "57E3CC33",
            "left": "57E37C83",
            "right": "57E3BC43",
            "select": "57E354AB",
            "replay": "57E31CE3",
            "options": "57E36C93",
            "rewind": "57E32CD3",
            "play_pause": "57E3AC53",
            "fast_forward": "57E3EC13",
        }
    },

    # ==================== SOUNDBARS ====================

    # Samsung Soundbar
    {
        "profile_id": "samsung_soundbar",
        "name": "Samsung Soundbar",
        "manufacturer": "Samsung",
        "device_type": "soundbar",
        "protocol": "SAMSUNG",
        "bits": 32,
        "codes": {
            "power": "E0E040BF",
            "volume_up": "E0E0E01F",
            "volume_down": "E0E0D02F",
            "mute": "E0E0F00F",
            "source": "E0E0807F",
        }
    },

    # Vizio Soundbar
    {
        "profile_id": "vizio_soundbar",
        "name": "Vizio Soundbar",
        "manufacturer": "Vizio",
        "device_type": "soundbar",
        "protocol": "NEC",
        "bits": 32,
        "codes": {
            "power": "D7280DF2",
            "volume_up": "D728ED12",
            "volume_down": "D7286D92",
            "mute": "D7287D82",
            "input": "D728FD02",
            "bluetooth": "D7285DA2",
        }
    },

    # Sony Soundbar
    {
        "profile_id": "sony_soundbar",
        "name": "Sony Soundbar",
        "manufacturer": "Sony",
        "device_type": "soundbar",
        "protocol": "SONY",
        "bits": 15,
        "codes": {
            "power": "540C",
            "volume_up": "240C",
            "volume_down": "640C",
            "mute": "140C",
            "input": "220C",
        }
    },
]


def get_all_profiles() -> List[Dict[str, Any]]:
    """Return all built-in IR profiles."""
    return BUILTIN_PROFILES


def get_profiles_by_type(device_type: str) -> List[Dict[str, Any]]:
    """Return profiles filtered by device type."""
    return [p for p in BUILTIN_PROFILES if p["device_type"] == device_type]


def get_profiles_by_manufacturer(manufacturer: str) -> List[Dict[str, Any]]:
    """Return profiles filtered by manufacturer."""
    return [p for p in BUILTIN_PROFILES if p["manufacturer"].lower() == manufacturer.lower()]


def get_profile_by_id(profile_id: str) -> Dict[str, Any] | None:
    """Return a specific profile by ID."""
    for profile in BUILTIN_PROFILES:
        if profile["profile_id"] == profile_id:
            return profile
    return None


def get_available_manufacturers() -> List[str]:
    """Return list of unique manufacturers."""
    return list(set(p["manufacturer"] for p in BUILTIN_PROFILES))


def get_available_device_types() -> List[str]:
    """Return list of unique device types."""
    return list(set(p["device_type"] for p in BUILTIN_PROFILES))
