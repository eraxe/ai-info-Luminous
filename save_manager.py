#!/usr/bin/env python3
"""
Luminous AI — Save Manager
SaveManager: thin wrapper that persists and restores the application's
session state (active campaign, last-opened file, scroll positions, etc.)
using a JSON file alongside settings.json.

The save state is intentionally lightweight — it complements
``SettingsManager`` (which owns configuration) by tracking *session*
data that changes frequently during normal use.

State file location::

    <app_dir>/session.json
"""
from __future__ import annotations

import sys
from pathlib import Path as _Path

# ── standalone import fix ──────────────────────────────────────────────────────
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(_Path(__file__).resolve().parent))

import json
import os
from pathlib import Path
from typing import Any

from settings import SettingsManager

# ── paths ─────────────────────────────────────────────────────────────────────

_APP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
_SESSION_PATH = _APP_DIR / "session.json"

# ── default session state ─────────────────────────────────────────────────────

DEFAULT_SESSION: dict[str, Any] = {
    # last active campaign identifier
    "last_campaign": "",
    # last selected category key inside the campaign
    "last_category": "",
    # last opened file (relative path string)
    "last_file": "",
    # whether the Collections drawer was open
    "collections_open": False,
    # search box contents per panel
    "search_query": "",
    # window geometry (e.g. "1280x800+100+50")
    "window_geometry": "",
}


class SaveManager:
    """Load and persist application session state to *session.json*.

    Parameters
    ----------
    path:
        Override the default session file path (useful for tests).
    settings:
        Optional ``SettingsManager`` instance.  If provided,
        ``save_data_path()`` is delegated to it.

    Usage::

        sm = SaveManager()
        sm.set("last_campaign", "chapter_1")
        sm.save()

        # next launch
        sm = SaveManager()
        print(sm.get("last_campaign"))   # "chapter_1"
    """

    def __init__(
        self,
        path: Path | None = None,
        settings: SettingsManager | None = None,
    ) -> None:
        self._path: Path = path or _SESSION_PATH
        self._settings: SettingsManager | None = settings
        self._data: dict[str, Any] = {}
        self.load()

    # ── persistence ───────────────────────────────────────────────────────────

    def load(self) -> dict[str, Any]:
        """Load session state from disk.  Missing keys are filled with defaults.

        Returns the full state dict.
        """
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            else:
                self._data = {}
        except Exception:  # noqa: BLE001
            self._data = {}

        # back-fill any keys added in future versions
        for key, default in DEFAULT_SESSION.items():
            self._data.setdefault(key, default)

        return dict(self._data)

    def save(self) -> bool:
        """Atomically write current session state to disk.

        Returns
        -------
        ``True`` on success, ``False`` if the write failed.
        """
        try:
            tmp = str(self._path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, str(self._path))
            return True
        except Exception:  # noqa: BLE001
            return False

    # ── data access ───────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, falling back to *default*."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set *key* to *value* in the in-memory state (does not auto-save)."""
        self._data[key] = value

    def set_many(self, updates: dict[str, Any]) -> None:
        """Bulk-update multiple keys at once."""
        self._data.update(updates)

    def reset(self) -> None:
        """Reset in-memory state to defaults (does not auto-save)."""
        self._data = dict(DEFAULT_SESSION)

    def all(self) -> dict[str, Any]:
        """Return a shallow copy of the full state dict."""
        return dict(self._data)

    # ── convenience properties ────────────────────────────────────────────────

    def last_campaign(self) -> str:
        """Last active campaign identifier."""
        return str(self._data.get("last_campaign", ""))

    def set_last_campaign(self, campaign_id: str) -> None:
        self._data["last_campaign"] = campaign_id

    def last_category(self) -> str:
        """Last selected category key."""
        return str(self._data.get("last_category", ""))

    def set_last_category(self, category_key: str) -> None:
        self._data["last_category"] = category_key

    def last_file(self) -> str:
        """Relative path of the last opened prompt file."""
        return str(self._data.get("last_file", ""))

    def set_last_file(self, rel_path: str) -> None:
        self._data["last_file"] = rel_path

    def window_geometry(self) -> str:
        """Stored window geometry string, e.g. ``'1280x800+100+50'``."""
        return str(self._data.get("window_geometry", ""))

    def set_window_geometry(self, geometry: str) -> None:
        self._data["window_geometry"] = geometry

    # ── settings bridge ───────────────────────────────────────────────────────

    def save_data_path(self) -> str:
        """Return the save_data path from ``SettingsManager`` if available,
        otherwise an empty string."""
        if self._settings is not None:
            return self._settings.save_data_path()
        # Fall back to a freshly-loaded SettingsManager so SaveManager
        # can be instantiated without an explicit settings reference.
        return SettingsManager().save_data_path()
