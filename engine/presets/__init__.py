"""Local preset loader — reads preset JSON from engine/presets/data/.

Provides a preset_loader callable for EmailEngineMCPServer.
"""

import json
import os

_PRESETS_DIR = os.path.join(os.path.dirname(__file__), "data")
_cache = {}


def _load_all():
    """Load all preset JSON files into cache."""
    if _cache:
        return
    if not os.path.isdir(_PRESETS_DIR):
        return
    for fname in os.listdir(_PRESETS_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(_PRESETS_DIR, fname)
        with open(path) as f:
            preset = json.load(f)
        pid = preset.get("preset_id", fname.replace(".json", ""))
        _cache[pid] = preset


def local_preset_loader(preset_id: str, **kwargs):
    """Load a preset by ID from local files.

    Special case: preset_id="__list__" returns metadata for all presets.
    Accepts optional category kwarg for filtering.
    """
    _load_all()

    if preset_id == "__list__":
        category = kwargs.get("category")
        result = []
        for pid, preset in _cache.items():
            if category and preset.get("category") != category:
                continue
            result.append({
                "preset_id": pid,
                "name": preset.get("name", pid),
                "description": preset.get("description", ""),
                "category": preset.get("category", ""),
                "tags": preset.get("tags", []),
                "variables": preset.get("variables", {}),
            })
        return result

    preset = _cache.get(preset_id)
    if not preset:
        raise ValueError(f"Preset '{preset_id}' not found")
    return preset
