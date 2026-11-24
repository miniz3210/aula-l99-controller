"""Icon cache with per-device, per-profile isolation and duplicate suppression."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class CacheEntry:
    """Single cached icon entry."""
    processed_image: 'ProcessedImage'
    device_id: str
    profile_id: str
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    def touch(self) -> None:
        """Update access time and count."""
        self.last_accessed = time.time()
        self.access_count += 1


class IconCache:
    """Per-device, per-profile icon cache with LRU eviction and duplicate suppression."""

    def __init__(self, max_entries_per_device: int = 64, max_total_entries: int = 256) -> None:
        # device_id -> profile_id -> position -> CacheEntry
        self._cache: Dict[str, Dict[str, Dict[int, CacheEntry]]] = {}
        self._max_entries_per_device = max_entries_per_device
        self._max_total_entries = max_total_entries
        self._total_entries = 0

    def _get_device_cache(self, device_id: str) -> Dict[str, Dict[int, CacheEntry]]:
        if device_id not in self._cache:
            self._cache[device_id] = {}
        return self._cache[device_id]

    def _get_profile_cache(self, device_id: str, profile_id: str) -> Dict[int, CacheEntry]:
        device_cache = self._get_device_cache(device_id)
        if profile_id not in device_cache:
            device_cache[profile_id] = {}
        return device_cache[profile_id]

    def _count_device_entries(self, device_id: str) -> int:
        device_cache = self._cache.get(device_id)
        if not device_cache:
            return 0
        total = 0
        for profile_cache in device_cache.values():
            if isinstance(profile_cache, dict):
                total += len(profile_cache)
        return total

    def _evict_lru_if_needed(self, device_id: str) -> None:
        """Evict LRU entries if device cache exceeds limit."""
        device_cache = self._cache.get(device_id)
        if not device_cache:
            return
        total = self._count_device_entries(device_id)

        while total >= self._max_entries_per_device:
            # Find LRU entry across all profiles
            lru_entry = None
            lru_profile = None
            lru_position = None
            lru_time = float('inf')

            for profile_id, profile_cache in device_cache.items():
                if not isinstance(profile_cache, dict):
                    continue
                for position, entry in profile_cache.items():
                    if entry.last_accessed < lru_time:
                        lru_time = entry.last_accessed
                        lru_entry = entry
                        lru_profile = profile_id
                        lru_position = position

            if lru_entry and lru_profile and lru_position is not None:
                profile_cache = device_cache.get(lru_profile)
                if isinstance(profile_cache, dict) and lru_position in profile_cache:
                    del profile_cache[lru_position]
                    if not profile_cache:
                        del device_cache[lru_profile]
                    self._total_entries -= 1
                    total -= 1
            else:
                break

        # Also check global limit
        while self._total_entries >= self._max_total_entries:
            # Find global LRU
            lru_entry = None
            lru_device = None
            lru_profile = None
            lru_position = None
            lru_time = float('inf')

            for dev_id, dev_cache in self._cache.items():
                if not isinstance(dev_cache, dict):
                    continue
                for prof_id, prof_cache in dev_cache.items():
                    if not isinstance(prof_cache, dict):
                        continue
                    for pos, entry in prof_cache.items():
                        if entry.last_accessed < lru_time:
                            lru_time = entry.last_accessed
                            lru_entry = entry
                            lru_device = dev_id
                            lru_profile = prof_id
                            lru_position = pos

            if lru_entry and lru_device and lru_profile and lru_position is not None:
                dev_cache = self._cache.get(lru_device)
                if isinstance(dev_cache, dict):
                    prof_cache = dev_cache.get(lru_profile)
                    if isinstance(prof_cache, dict) and lru_position in prof_cache:
                        del prof_cache[lru_position]
                        if not prof_cache:
                            del dev_cache[lru_profile]
                        if not dev_cache:
                            del self._cache[lru_device]
                        self._total_entries -= 1
            else:
                break

    def get(
        self,
        device_id: str,
        profile_id: str,
        position: int
    ) -> Optional['ProcessedImage']:
        """Get cached image if exists and SHA-256 matches (duplicate suppression)."""
        profile_cache = self._get_profile_cache(device_id, profile_id)
        entry = profile_cache.get(position)
        if entry:
            entry.touch()
            return entry.processed_image
        return None

    def put(
        self,
        device_id: str,
        profile_id: str,
        processed_image: 'ProcessedImage'
    ) -> bool:
        """Store processed image in cache.
        
        Returns True if stored (new or updated), False if duplicate (same SHA-256).
        """
        profile_cache = self._get_profile_cache(device_id, profile_id)
        existing = profile_cache.get(processed_image.position)

        # Duplicate suppression: same SHA-256 means identical image
        if existing and existing.processed_image.sha256 == processed_image.sha256:
            existing.touch()
            return False  # Duplicate, not stored

        # Evict if needed before adding
        self._evict_lru_if_needed(device_id)

        entry = CacheEntry(
            processed_image=processed_image,
            device_id=device_id,
            profile_id=profile_id
        )
        profile_cache[processed_image.position] = entry
        self._total_entries += 1
        return True

    def clear_position(self, device_id: str, profile_id: str, position: int) -> bool:
        """Clear a specific position from cache."""
        device_cache = self._cache.get(device_id)
        if not device_cache:
            return False
        profile_cache = device_cache.get(profile_id)
        if not profile_cache:
            return False
        if not isinstance(profile_cache, dict):
            return False
        if position in profile_cache:
            del profile_cache[position]
            self._total_entries -= 1
            if not profile_cache:
                del device_cache[profile_id]
            if not device_cache:
                del self._cache[device_id]
            return True
        return False

    def clear_profile(self, device_id: str, profile_id: str) -> int:
        """Clear all positions for a profile. Returns count cleared."""
        device_cache = self._cache.get(device_id)
        if not device_cache:
            return 0
        profile_cache = device_cache.get(profile_id)
        if not profile_cache:
            return 0
        if not isinstance(profile_cache, dict):
            return 0
        count = len(profile_cache)
        del device_cache[profile_id]
        self._total_entries -= count
        if not device_cache:
            del self._cache[device_id]
        return count

    def clear_device(self, device_id: str) -> int:
        """Clear all profiles for a device. Returns count cleared."""
        device_cache = self._cache.get(device_id)
        if not device_cache:
            return 0
        if not isinstance(device_cache, dict):
            return 0
        count = 0
        for profile_cache in device_cache.values():
            if isinstance(profile_cache, dict):
                count += len(profile_cache)
        del self._cache[device_id]
        self._total_entries -= count
        return count

    def get_all_for_device(self, device_id: str) -> Dict[str, Dict[int, 'ProcessedImage']]:
        """Get all cached images for a device (for reconnect restoration)."""
        device_cache = self._cache.get(device_id, {})
        result = {}
        for profile_id, profile_cache in device_cache.items():
            if not isinstance(profile_cache, dict):
                continue
            result[profile_id] = {}
            for position, entry in profile_cache.items():
                entry.touch()
                result[profile_id][position] = entry.processed_image
        return result

    def get_all_for_profile(self, device_id: str, profile_id: str) -> Dict[int, 'ProcessedImage']:
        """Get all cached images for a profile."""
        profile_cache = self._get_profile_cache(device_id, profile_id)
        result = {}
        for position, entry in profile_cache.items():
            entry.touch()
            result[position] = entry.processed_image
        return result

    def get_stats(self) -> Dict[str, any]:
        """Get cache statistics."""
        stats = {
            "total_entries": self._total_entries,
            "devices": {}
        }
        for device_id, device_cache in self._cache.items():
            if not isinstance(device_cache, dict):
                continue
            device_stats = {
                "profiles": {},
                "total_entries": 0
            }
            for profile_id, profile_cache in device_cache.items():
                if not isinstance(profile_cache, dict):
                    continue
                device_stats["profiles"][profile_id] = {
                    "entries": len(profile_cache),
                    "positions": list(profile_cache.keys())
                }
                device_stats["total_entries"] += len(profile_cache)
            stats["devices"][device_id] = device_stats
        return stats

    def has_image(self, device_id: str, profile_id: str, position: int, sha256: str) -> bool:
        """Check if an image with given SHA-256 is already cached."""
        profile_cache = self._get_profile_cache(device_id, profile_id)
        entry = profile_cache.get(position)
        return entry is not None and entry.processed_image.sha256 == sha256