"""Built-in network device drivers.

Provides pre-configured drivers for common network devices:
1. Generic HDMI Matrix (common protocol)
2. PJLink Projector (Class 1)
3. Denon/Marantz AVR (telnet protocol)

These serve as fallbacks when community drivers are not available.
"""

from typing import Any, Dict, List

from .device_types import DeviceType


# Generic HDMI Matrix Driver
# Common protocol used by many budget HDMI matrices (OREI, J-Tech, Monoprice, etc.)
# Format: "s cir {input} {output}!" for routing
HDMI_MATRIX_GENERIC = {
    "driver_id": "hdmi_matrix_generic",
    "name": "Generic HDMI Matrix",
    "manufacturer": "Generic",
    "device_type": "hdmi_matrix",
    "description": "Generic HDMI matrix with common command protocol. Works with many budget matrices.",

    "connection": {
        "protocol": "tcp",
        "default_port": 8000,
        "persistent_connection": True,
        "timeout": 5.0,
        "reconnect_interval": 30.0,
    },

    "discovery": {
        "method": "none",
        "identification_command": "s read version!",
        "identification_pattern": r"version[:\s]+(.+)",
    },

    "communication": {
        "command_format": "text",
        "default_line_ending": "none",  # Commands end with !
    },

    "matrix_config": {
        "input_count": 8,
        "output_count": 8,
        "routing_command_template": "s cir {input} {output}!",
        "all_outputs_template": "s cir {input} 0!",  # 0 = all outputs
    },

    "commands": {
        "power_on": {
            "command_id": "power_on",
            "name": "Power On",
            "payload": "s power 1!",
            "line_ending": "none",
        },
        "power_off": {
            "command_id": "power_off",
            "name": "Power Off",
            "payload": "s power 0!",
            "line_ending": "none",
        },
        "query_power": {
            "command_id": "query_power",
            "name": "Query Power",
            "payload": "s read power!",
            "line_ending": "none",
            "is_query": True,
            "response_patterns": [
                {"pattern": r"power[:\s]+(on|off|1|0)", "state_key": "power", "value_group": 1}
            ],
        },
        "query_routing": {
            "command_id": "query_routing",
            "name": "Query Routing",
            "payload": "s read cirall!",
            "line_ending": "none",
            "is_query": True,
            "response_patterns": [
                {"pattern": r"cir\s*(\d+)\s*(\d+)", "state_key": "routing", "value_group": 0}
            ],
        },
        "beep_on": {
            "command_id": "beep_on",
            "name": "Beep On",
            "payload": "s buzzer 1!",
            "line_ending": "none",
        },
        "beep_off": {
            "command_id": "beep_off",
            "name": "Beep Off",
            "payload": "s buzzer 0!",
            "line_ending": "none",
        },
        "lock_panel": {
            "command_id": "lock_panel",
            "name": "Lock Front Panel",
            "payload": "s lock 1!",
            "line_ending": "none",
        },
        "unlock_panel": {
            "command_id": "unlock_panel",
            "name": "Unlock Front Panel",
            "payload": "s lock 0!",
            "line_ending": "none",
        },
    },

    "input_options": [
        {"input_value": "1", "name": "Input 1", "command_template": "s cir 1 {output}!"},
        {"input_value": "2", "name": "Input 2", "command_template": "s cir 2 {output}!"},
        {"input_value": "3", "name": "Input 3", "command_template": "s cir 3 {output}!"},
        {"input_value": "4", "name": "Input 4", "command_template": "s cir 4 {output}!"},
        {"input_value": "5", "name": "Input 5", "command_template": "s cir 5 {output}!"},
        {"input_value": "6", "name": "Input 6", "command_template": "s cir 6 {output}!"},
        {"input_value": "7", "name": "Input 7", "command_template": "s cir 7 {output}!"},
        {"input_value": "8", "name": "Input 8", "command_template": "s cir 8 {output}!"},
    ],
}


# PJLink Projector Driver (Class 1)
# Industry-standard protocol for projector control
# See: https://pjlink.jbmia.or.jp/english/data_cl1/PJLink_5-1.pdf
PJLINK_PROJECTOR = {
    "driver_id": "projector_pjlink_class1",
    "name": "PJLink Projector (Class 1)",
    "manufacturer": "Generic",
    "device_type": "projector",
    "description": "PJLink Class 1 compatible projector. Supports Epson, NEC, Sony, Panasonic, and more.",

    "connection": {
        "protocol": "tcp",
        "default_port": 4352,
        "persistent_connection": False,
        "timeout": 5.0,
        "reconnect_interval": 30.0,
    },

    "discovery": {
        "method": "pjlink",
        "identification_command": "%1NAME ?\r",
        "identification_pattern": r"%1NAME=(.+)",
        "broadcast_port": 4352,
    },

    "communication": {
        "command_format": "text",
        "default_line_ending": "cr",
        "authentication": {
            "supported": True,
            "type": "pjlink",  # Uses PJLink challenge-response
        },
    },

    "commands": {
        "power_on": {
            "command_id": "power_on",
            "name": "Power On",
            "payload": "%1POWR 1",
            "line_ending": "cr",
        },
        "power_off": {
            "command_id": "power_off",
            "name": "Power Off",
            "payload": "%1POWR 0",
            "line_ending": "cr",
        },
        "query_power": {
            "command_id": "query_power",
            "name": "Query Power",
            "payload": "%1POWR ?",
            "line_ending": "cr",
            "is_query": True,
            "response_patterns": [
                {
                    "pattern": r"%1POWR=(\d)",
                    "state_key": "power",
                    "value_group": 1,
                    "value_map": {"0": "off", "1": "on", "2": "cooling", "3": "warming"},
                }
            ],
        },
        "input_rgb1": {
            "command_id": "input_rgb1",
            "name": "RGB 1",
            "payload": "%1INPT 11",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "RGB1",
        },
        "input_rgb2": {
            "command_id": "input_rgb2",
            "name": "RGB 2",
            "payload": "%1INPT 12",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "RGB2",
        },
        "input_video": {
            "command_id": "input_video",
            "name": "Video",
            "payload": "%1INPT 21",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "VIDEO",
        },
        "input_hdmi1": {
            "command_id": "input_hdmi1",
            "name": "HDMI 1",
            "payload": "%1INPT 31",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "HDMI1",
        },
        "input_hdmi2": {
            "command_id": "input_hdmi2",
            "name": "HDMI 2",
            "payload": "%1INPT 32",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "HDMI2",
        },
        "query_input": {
            "command_id": "query_input",
            "name": "Query Input",
            "payload": "%1INPT ?",
            "line_ending": "cr",
            "is_query": True,
            "response_patterns": [
                {
                    "pattern": r"%1INPT=(\d+)",
                    "state_key": "current_input",
                    "value_group": 1,
                    "value_map": {"11": "RGB1", "12": "RGB2", "21": "VIDEO", "31": "HDMI1", "32": "HDMI2"},
                }
            ],
        },
        "mute_on": {
            "command_id": "mute_on",
            "name": "AV Mute On",
            "payload": "%1AVMT 31",
            "line_ending": "cr",
        },
        "mute_off": {
            "command_id": "mute_off",
            "name": "AV Mute Off",
            "payload": "%1AVMT 30",
            "line_ending": "cr",
        },
        "query_lamp": {
            "command_id": "query_lamp",
            "name": "Query Lamp Hours",
            "payload": "%1LAMP ?",
            "line_ending": "cr",
            "is_query": True,
            "response_patterns": [
                {
                    "pattern": r"%1LAMP=(\d+)",
                    "state_key": "lamp_hours",
                    "value_group": 1,
                }
            ],
        },
        "query_name": {
            "command_id": "query_name",
            "name": "Query Name",
            "payload": "%1NAME ?",
            "line_ending": "cr",
            "is_query": True,
            "response_patterns": [
                {
                    "pattern": r"%1NAME=(.+)",
                    "state_key": "device_name",
                    "value_group": 1,
                }
            ],
        },
        "query_errors": {
            "command_id": "query_errors",
            "name": "Query Errors",
            "payload": "%1ERST ?",
            "line_ending": "cr",
            "is_query": True,
            "response_patterns": [
                {
                    "pattern": r"%1ERST=(.+)",
                    "state_key": "error_status",
                    "value_group": 1,
                }
            ],
        },
    },
}


# Denon/Marantz AVR Driver
# Telnet protocol for AV receivers
# See: https://assets.denon.com/DocumentMaster/US/AVR-X6400H_X4400H_X3400H_X2400H_X1400H_S930H_S730H_X6300W_PROTOCOL(1006)_V04.pdf
DENON_AVR = {
    "driver_id": "av_receiver_denon_avr",
    "name": "Denon/Marantz AVR",
    "manufacturer": "Denon",
    "device_type": "audio_receiver",
    "description": "Denon and Marantz AV receivers with network control. Works with most models from 2010+.",

    "connection": {
        "protocol": "tcp",
        "default_port": 23,
        "persistent_connection": True,
        "timeout": 5.0,
        "reconnect_interval": 30.0,
    },

    "discovery": {
        "method": "ssdp",
        "ssdp_search_target": "urn:schemas-denon-com:device:ACT-Denon:1",
        "identification_command": "PW?\r",
        "identification_pattern": r"PW(ON|STANDBY)",
    },

    "communication": {
        "command_format": "text",
        "default_line_ending": "cr",
    },

    "commands": {
        "power_on": {
            "command_id": "power_on",
            "name": "Power On",
            "payload": "PWON",
            "line_ending": "cr",
        },
        "power_off": {
            "command_id": "power_off",
            "name": "Power Off",
            "payload": "PWSTANDBY",
            "line_ending": "cr",
        },
        "query_power": {
            "command_id": "query_power",
            "name": "Query Power",
            "payload": "PW?",
            "line_ending": "cr",
            "is_query": True,
            "poll_interval": 30.0,
            "response_patterns": [
                {
                    "pattern": r"PW(ON|STANDBY)",
                    "state_key": "power",
                    "value_group": 1,
                    "value_map": {"ON": "on", "STANDBY": "off"},
                }
            ],
        },
        "volume_up": {
            "command_id": "volume_up",
            "name": "Volume Up",
            "payload": "MVUP",
            "line_ending": "cr",
        },
        "volume_down": {
            "command_id": "volume_down",
            "name": "Volume Down",
            "payload": "MVDOWN",
            "line_ending": "cr",
        },
        "mute_on": {
            "command_id": "mute_on",
            "name": "Mute On",
            "payload": "MUON",
            "line_ending": "cr",
        },
        "mute_off": {
            "command_id": "mute_off",
            "name": "Mute Off",
            "payload": "MUOFF",
            "line_ending": "cr",
        },
        "mute_toggle": {
            "command_id": "mute_toggle",
            "name": "Mute Toggle",
            "payload": "MU?",
            "line_ending": "cr",
        },
        "query_volume": {
            "command_id": "query_volume",
            "name": "Query Volume",
            "payload": "MV?",
            "line_ending": "cr",
            "is_query": True,
            "poll_interval": 30.0,
            "response_patterns": [
                {
                    "pattern": r"MV(\d+)",
                    "state_key": "volume",
                    "value_group": 1,
                }
            ],
        },
        "input_cbl_sat": {
            "command_id": "input_cbl_sat",
            "name": "CBL/SAT",
            "payload": "SISAT/CBL",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "CBL/SAT",
        },
        "input_dvd": {
            "command_id": "input_dvd",
            "name": "DVD",
            "payload": "SIDVD",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "DVD",
        },
        "input_bluray": {
            "command_id": "input_bluray",
            "name": "Blu-ray",
            "payload": "SIBD",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "BD",
        },
        "input_game": {
            "command_id": "input_game",
            "name": "Game",
            "payload": "SIGAME",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "GAME",
        },
        "input_media_player": {
            "command_id": "input_media_player",
            "name": "Media Player",
            "payload": "SIMPLAY",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "MPLAY",
        },
        "input_tv": {
            "command_id": "input_tv",
            "name": "TV Audio",
            "payload": "SITV",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "TV",
        },
        "input_aux1": {
            "command_id": "input_aux1",
            "name": "AUX 1",
            "payload": "SIAUX1",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "AUX1",
        },
        "input_aux2": {
            "command_id": "input_aux2",
            "name": "AUX 2",
            "payload": "SIAUX2",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "AUX2",
        },
        "input_tuner": {
            "command_id": "input_tuner",
            "name": "Tuner",
            "payload": "SITUNER",
            "line_ending": "cr",
            "is_input_option": True,
            "input_value": "TUNER",
        },
        "query_input": {
            "command_id": "query_input",
            "name": "Query Input",
            "payload": "SI?",
            "line_ending": "cr",
            "is_query": True,
            "poll_interval": 30.0,
            "response_patterns": [
                {
                    "pattern": r"SI(.+)",
                    "state_key": "current_input",
                    "value_group": 1,
                }
            ],
        },
        "surround_auto": {
            "command_id": "surround_auto",
            "name": "Auto Surround",
            "payload": "MSAUTO",
            "line_ending": "cr",
        },
        "surround_stereo": {
            "command_id": "surround_stereo",
            "name": "Stereo",
            "payload": "MSSTEREO",
            "line_ending": "cr",
        },
        "surround_movie": {
            "command_id": "surround_movie",
            "name": "Movie",
            "payload": "MSMOVIE",
            "line_ending": "cr",
        },
        "surround_music": {
            "command_id": "surround_music",
            "name": "Music",
            "payload": "MSMUSIC",
            "line_ending": "cr",
        },
        "surround_game": {
            "command_id": "surround_game",
            "name": "Game",
            "payload": "MSGAME",
            "line_ending": "cr",
        },
        "query_surround": {
            "command_id": "query_surround",
            "name": "Query Surround Mode",
            "payload": "MS?",
            "line_ending": "cr",
            "is_query": True,
            "response_patterns": [
                {
                    "pattern": r"MS(.+)",
                    "state_key": "surround_mode",
                    "value_group": 1,
                }
            ],
        },
    },
}


# Yamaha AVR Driver (YNCA protocol)
# Alternative protocol for Yamaha receivers
YAMAHA_AVR = {
    "driver_id": "av_receiver_yamaha_ynca",
    "name": "Yamaha AVR (YNCA)",
    "manufacturer": "Yamaha",
    "device_type": "audio_receiver",
    "description": "Yamaha AV receivers with YNCA network control. RX-A and RX-V series.",

    "connection": {
        "protocol": "tcp",
        "default_port": 50000,
        "persistent_connection": True,
        "timeout": 5.0,
        "reconnect_interval": 30.0,
    },

    "discovery": {
        "method": "ssdp",
        "ssdp_search_target": "urn:schemas-yamaha-com:service:X_YamahaRemoteControl:1",
        "identification_command": "@MAIN:PWR=?\r\n",
        "identification_pattern": r"@MAIN:PWR=(On|Standby)",
    },

    "communication": {
        "command_format": "text",
        "default_line_ending": "crlf",
    },

    "commands": {
        "power_on": {
            "command_id": "power_on",
            "name": "Power On",
            "payload": "@MAIN:PWR=On",
            "line_ending": "crlf",
        },
        "power_off": {
            "command_id": "power_off",
            "name": "Power Off",
            "payload": "@MAIN:PWR=Standby",
            "line_ending": "crlf",
        },
        "query_power": {
            "command_id": "query_power",
            "name": "Query Power",
            "payload": "@MAIN:PWR=?",
            "line_ending": "crlf",
            "is_query": True,
            "poll_interval": 30.0,
            "response_patterns": [
                {
                    "pattern": r"@MAIN:PWR=(On|Standby)",
                    "state_key": "power",
                    "value_group": 1,
                    "value_map": {"On": "on", "Standby": "off"},
                }
            ],
        },
        "volume_up": {
            "command_id": "volume_up",
            "name": "Volume Up",
            "payload": "@MAIN:VOL=Up",
            "line_ending": "crlf",
        },
        "volume_down": {
            "command_id": "volume_down",
            "name": "Volume Down",
            "payload": "@MAIN:VOL=Down",
            "line_ending": "crlf",
        },
        "mute_on": {
            "command_id": "mute_on",
            "name": "Mute On",
            "payload": "@MAIN:MUTE=On",
            "line_ending": "crlf",
        },
        "mute_off": {
            "command_id": "mute_off",
            "name": "Mute Off",
            "payload": "@MAIN:MUTE=Off",
            "line_ending": "crlf",
        },
        "query_volume": {
            "command_id": "query_volume",
            "name": "Query Volume",
            "payload": "@MAIN:VOL=?",
            "line_ending": "crlf",
            "is_query": True,
            "response_patterns": [
                {
                    "pattern": r"@MAIN:VOL=(-?\d+\.?\d*)",
                    "state_key": "volume",
                    "value_group": 1,
                }
            ],
        },
        "input_hdmi1": {
            "command_id": "input_hdmi1",
            "name": "HDMI 1",
            "payload": "@MAIN:INP=HDMI1",
            "line_ending": "crlf",
            "is_input_option": True,
            "input_value": "HDMI1",
        },
        "input_hdmi2": {
            "command_id": "input_hdmi2",
            "name": "HDMI 2",
            "payload": "@MAIN:INP=HDMI2",
            "line_ending": "crlf",
            "is_input_option": True,
            "input_value": "HDMI2",
        },
        "input_hdmi3": {
            "command_id": "input_hdmi3",
            "name": "HDMI 3",
            "payload": "@MAIN:INP=HDMI3",
            "line_ending": "crlf",
            "is_input_option": True,
            "input_value": "HDMI3",
        },
        "input_hdmi4": {
            "command_id": "input_hdmi4",
            "name": "HDMI 4",
            "payload": "@MAIN:INP=HDMI4",
            "line_ending": "crlf",
            "is_input_option": True,
            "input_value": "HDMI4",
        },
        "input_av1": {
            "command_id": "input_av1",
            "name": "AV 1",
            "payload": "@MAIN:INP=AV1",
            "line_ending": "crlf",
            "is_input_option": True,
            "input_value": "AV1",
        },
        "input_tuner": {
            "command_id": "input_tuner",
            "name": "Tuner",
            "payload": "@MAIN:INP=TUNER",
            "line_ending": "crlf",
            "is_input_option": True,
            "input_value": "TUNER",
        },
        "query_input": {
            "command_id": "query_input",
            "name": "Query Input",
            "payload": "@MAIN:INP=?",
            "line_ending": "crlf",
            "is_query": True,
            "response_patterns": [
                {
                    "pattern": r"@MAIN:INP=(.+)",
                    "state_key": "current_input",
                    "value_group": 1,
                }
            ],
        },
    },
}


# All built-in drivers
BUILTIN_DRIVERS: List[Dict[str, Any]] = [
    HDMI_MATRIX_GENERIC,
    PJLINK_PROJECTOR,
    DENON_AVR,
    YAMAHA_AVR,
]


def get_builtin_driver(driver_id: str) -> Dict[str, Any] | None:
    """Get a built-in driver by ID.

    Args:
        driver_id: The driver ID to look up

    Returns:
        Driver dict or None if not found
    """
    for driver in BUILTIN_DRIVERS:
        if driver["driver_id"] == driver_id:
            return driver
    return None


def get_builtin_drivers_by_type(device_type: str) -> List[Dict[str, Any]]:
    """Get all built-in drivers for a device type.

    Args:
        device_type: The device type to filter by

    Returns:
        List of driver dicts matching the device type
    """
    return [d for d in BUILTIN_DRIVERS if d["device_type"] == device_type]


def get_all_builtin_drivers() -> List[Dict[str, Any]]:
    """Get all built-in drivers.

    Returns:
        List of all built-in driver dicts
    """
    return BUILTIN_DRIVERS.copy()
