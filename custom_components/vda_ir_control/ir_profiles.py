"""Pre-loaded IR code profiles for common devices.

All profiles are now sourced from the community repository on GitHub.
Use the sync feature to download profiles from:
https://github.com/vda-solutions/vda-ir-profiles
"""

from typing import Dict, List, Any

# IR Profile structure:
# {
#     "profile_id": "unique_id",
#     "name": "Display Name",
#     "manufacturer": "Brand",
#     "device_type": "tv" | "cable_box" | "soundbar" | "streaming" | "av_receiver" | "projector" | "blu_ray" | "gaming" | "fan" | "ac" | "lighting",
#     "protocol": "SAMSUNG" | "NEC" | "SONY" | etc,
#     "bits": 32,  # Protocol bit length
#     "codes": {
#         "command_name": "hex_code",
#         ...
#     }
# }

# No builtin profiles - all profiles come from the community repository
BUILTIN_PROFILES: List[Dict[str, Any]] = []


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
