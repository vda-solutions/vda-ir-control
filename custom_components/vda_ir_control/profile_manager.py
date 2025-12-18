"""Profile manager for hybrid IR profile system.

Manages IR profiles from multiple sources:
1. Built-in profiles (fallback defaults)
2. Community profiles (synced from GitHub)
3. User profiles (learned/created locally)

Priority order: User > Community > Built-in
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .ir_profiles import BUILTIN_PROFILES, get_profile_by_id as get_builtin_profile

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_COMMUNITY_PROFILES = f"{DOMAIN}_community_profiles"
STORAGE_KEY_COMMUNITY_META = f"{DOMAIN}_community_meta"

# GitHub repository URLs
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/vda-solutions/vda-ir-profiles/main"
GITHUB_API_BASE = "https://api.github.com/repos/vda-solutions/vda-ir-profiles"
GITHUB_REPO_URL = "https://github.com/vda-solutions/vda-ir-profiles"


class ProfileManager:
    """Manages IR profiles from multiple sources with priority."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the profile manager.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self._community_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_COMMUNITY_PROFILES)
        self._meta_store = Store(hass, STORAGE_VERSION, STORAGE_KEY_COMMUNITY_META)

        # Cached data
        self._community_profiles: Dict[str, Dict[str, Any]] = {}
        self._meta: Dict[str, Any] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load cached community profiles from storage."""
        if self._loaded:
            return

        # Load community profiles cache
        profiles_data = await self._community_store.async_load()
        if profiles_data:
            self._community_profiles = profiles_data
            _LOGGER.debug("Loaded %d community profiles from cache", len(self._community_profiles))

        # Load metadata (last sync time, etag, etc.)
        meta_data = await self._meta_store.async_load()
        if meta_data:
            self._meta = meta_data

        self._loaded = True
        _LOGGER.info(
            "ProfileManager loaded: %d community profiles, last sync: %s",
            len(self._community_profiles),
            self._meta.get("last_sync", "never")
        )

    async def async_sync_community_profiles(self) -> Dict[str, Any]:
        """Sync profiles from GitHub.

        Fetches the manifest from the community repository, then downloads
        each profile listed. Uses ETag for conditional requests to respect
        GitHub API rate limits.

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
            "profiles_added": 0,
            "profiles_updated": 0,
            "profiles_failed": 0,
            "total_profiles": 0,
            "message": "",
            "last_sync": None,
        }

        try:
            # Fetch manifest from GitHub
            manifest_url = f"{GITHUB_RAW_BASE}/manifest.json"
            _LOGGER.debug("Fetching manifest from %s", manifest_url)

            async with session.get(
                manifest_url,
                headers=headers,
                timeout=30
            ) as resp:
                if resp.status == 304:
                    # Not modified
                    result["success"] = True
                    result["message"] = "Profiles are up to date"
                    result["total_profiles"] = len(self._community_profiles)
                    result["last_sync"] = self._meta.get("last_sync")
                    _LOGGER.info("Community profiles are up to date (304 Not Modified)")
                    return result

                if resp.status == 404:
                    result["message"] = "Community profile repository not found"
                    _LOGGER.error("Manifest not found at %s", manifest_url)
                    return result

                if resp.status != 200:
                    result["message"] = f"GitHub error: HTTP {resp.status}"
                    _LOGGER.error("Failed to fetch manifest: HTTP %d", resp.status)
                    return result

                manifest = await resp.json()
                new_etag = resp.headers.get("ETag")

            # Validate manifest
            profiles_to_fetch = manifest.get("profiles", [])
            if not profiles_to_fetch:
                result["message"] = "Manifest contains no profiles"
                _LOGGER.warning("Manifest is empty")
                return result

            _LOGGER.info("Found %d profiles in manifest", len(profiles_to_fetch))

            # Fetch each profile listed in manifest
            added = 0
            updated = 0
            failed = 0

            for profile_path in profiles_to_fetch:
                try:
                    profile_url = f"{GITHUB_RAW_BASE}/{profile_path}"
                    async with session.get(profile_url, timeout=10) as profile_resp:
                        if profile_resp.status == 200:
                            profile_data = await profile_resp.json()
                            profile_id = profile_data.get("profile_id")

                            if profile_id:
                                if profile_id in self._community_profiles:
                                    updated += 1
                                else:
                                    added += 1
                                self._community_profiles[profile_id] = profile_data
                                _LOGGER.debug("Fetched profile: %s", profile_id)
                            else:
                                _LOGGER.warning("Profile missing profile_id: %s", profile_path)
                                failed += 1
                        else:
                            _LOGGER.warning(
                                "Failed to fetch profile %s: HTTP %d",
                                profile_path, profile_resp.status
                            )
                            failed += 1
                except Exception as err:
                    _LOGGER.warning("Error fetching profile %s: %s", profile_path, err)
                    failed += 1

            # Save to storage
            await self._community_store.async_save(self._community_profiles)

            # Update metadata
            self._meta = {
                "etag": new_etag,
                "last_sync": datetime.now().isoformat(),
                "manifest_version": manifest.get("version", "unknown"),
                "manifest_updated": manifest.get("updated", "unknown"),
            }
            await self._meta_store.async_save(self._meta)

            result["success"] = True
            result["profiles_added"] = added
            result["profiles_updated"] = updated
            result["profiles_failed"] = failed
            result["total_profiles"] = len(self._community_profiles)
            result["last_sync"] = self._meta["last_sync"]
            result["message"] = f"Synced {added} new, {updated} updated profiles"
            if failed > 0:
                result["message"] += f" ({failed} failed)"

            _LOGGER.info(
                "Community profile sync complete: %d added, %d updated, %d failed",
                added, updated, failed
            )

        except Exception as err:
            _LOGGER.error("Failed to sync community profiles: %s", err)
            result["message"] = f"Sync failed: {str(err)}"

        return result

    def get_builtin_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get a built-in profile by ID.

        Args:
            profile_id: The profile ID to look up

        Returns:
            Profile dict with _source field, or None if not found
        """
        profile = get_builtin_profile(profile_id)
        if profile:
            return {**profile, "_source": "builtin"}
        return None

    def get_community_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get a community profile by ID.

        Args:
            profile_id: The profile ID to look up

        Returns:
            Profile dict with _source field, or None if not found
        """
        profile = self._community_profiles.get(profile_id)
        if profile:
            return {**profile, "_source": "community"}
        return None

    def get_profile(self, profile_id: str, source: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a profile by ID with optional source filter.

        If source is not specified, checks community first (higher priority),
        then falls back to built-in.

        Args:
            profile_id: The profile ID to look up
            source: Optional source filter ('builtin' or 'community')

        Returns:
            Profile dict with _source field, or None if not found
        """
        if source == "builtin":
            return self.get_builtin_profile(profile_id)

        if source == "community":
            return self.get_community_profile(profile_id)

        # No source specified - check community first (higher priority)
        community = self.get_community_profile(profile_id)
        if community:
            return community

        # Fall back to built-in
        return self.get_builtin_profile(profile_id)

    def get_all_community_profiles(self) -> List[Dict[str, Any]]:
        """Get all cached community profiles.

        Returns:
            List of profile dicts with _source field
        """
        return [
            {**profile, "_source": "community"}
            for profile in self._community_profiles.values()
        ]

    def get_all_builtin_profiles(self) -> List[Dict[str, Any]]:
        """Get all built-in profiles.

        Returns:
            List of profile dicts with _source field
        """
        return [
            {**profile, "_source": "builtin"}
            for profile in BUILTIN_PROFILES
        ]

    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status information.

        Returns:
            Dict with sync status including last sync time, profile counts, etc.
        """
        return {
            "last_sync": self._meta.get("last_sync"),
            "manifest_version": self._meta.get("manifest_version"),
            "manifest_updated": self._meta.get("manifest_updated"),
            "community_profile_count": len(self._community_profiles),
            "builtin_profile_count": len(BUILTIN_PROFILES),
            "repository_url": GITHUB_REPO_URL,
        }

    def export_profile_for_contribution(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Export a user profile in a format suitable for PR submission.

        Formats the profile according to the community repository schema
        and provides contribution information.

        Args:
            profile: The profile dict to export

        Returns:
            Dict with export_data, export_json, and contribution_url
        """
        # Build export data according to schema
        export_data = {
            "profile_id": profile.get("profile_id", ""),
            "name": profile.get("name", ""),
            "manufacturer": profile.get("manufacturer", "Unknown"),
            "device_type": profile.get("device_type", "tv"),
            "protocol": profile.get("protocol", "NEC"),
            "bits": profile.get("bits", 32),
            "codes": {},
        }

        # Extract codes - handle both dict and IRCode formats
        codes = profile.get("codes", {})
        for command, code_data in codes.items():
            if isinstance(code_data, dict):
                # IRCode format from user profiles
                export_data["codes"][command] = code_data.get("raw_code", "")
            else:
                # Simple string format
                export_data["codes"][command] = code_data

        export_json = json.dumps(export_data, indent=2)

        # Determine the directory path for contribution
        device_type = export_data["device_type"]
        manufacturer = export_data["manufacturer"].lower().replace(" ", "_")
        profile_id = export_data["profile_id"]

        suggested_path = f"{device_type}/{manufacturer}/{profile_id}.json"

        return {
            "export_data": export_data,
            "export_json": export_json,
            "suggested_path": suggested_path,
            "contribution_url": f"{GITHUB_REPO_URL}/issues/new?title=New+Profile:+{profile.get('name', 'Unknown')}&body=Please+add+this+profile",
            "repository_url": GITHUB_REPO_URL,
        }


def get_profile_manager(hass: HomeAssistant) -> ProfileManager:
    """Get or create ProfileManager instance.

    Args:
        hass: Home Assistant instance

    Returns:
        ProfileManager instance (singleton per HA instance)
    """
    if "profile_manager" not in hass.data.get(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["profile_manager"] = ProfileManager(hass)
    return hass.data[DOMAIN]["profile_manager"]
