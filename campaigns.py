#!/usr/bin/env python3
"""
Luminous AI — Campaign Discovery
Scan a save_data directory and return all valid campaign identifiers.

Expected layout (any combination is accepted)::

    <save_path>/
    ├── campaigns/
    │   ├── my_campaign/
    │   │   └── prompts/
    │   └── another/
    └── standalone_campaign/
        └── prompts/

A directory is recognised as a campaign if it contains a ``prompts/``
subdirectory **or** at least one supported prompt file at its top level.
"""
from __future__ import annotations

import os
from pathlib import Path

_PROMPT_EXTENSIONS: frozenset[str] = frozenset(
    {".txt", ".md", ".markdown", ".prompt", ".json", ".jsonc"}
)

# Directories that should never be treated as campaigns
_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {".git", ".idea", ".vscode", "__pycache__", ".snapshots", "node_modules"}
)


def _is_campaign_dir(path: Path) -> bool:
    """Return True if *path* looks like a campaign directory."""
    if not path.is_dir():
        return False
    # Has a prompts/ subdirectory → definitive match
    if (path / "prompts").is_dir():
        return True
    # Has at least one prompt file directly inside → loose match
    try:
        for entry in path.iterdir():
            if entry.is_file() and entry.suffix.lower() in _PROMPT_EXTENSIONS:
                return True
    except PermissionError:
        pass
    return False


def discover_campaigns(save_path: str | Path) -> list[str]:
    """Scan *save_path* and return a sorted list of campaign identifiers.

    The function checks two locations:

    1. ``<save_path>/campaigns/`` — canonical location used by the game.
    2. ``<save_path>/`` itself — for loosely organised save folders where
       campaign directories live directly at the root.

    Duplicate names (same directory appearing via both scan paths) are
    de-duplicated; the canonical ``campaigns/`` sub-path takes priority.

    Parameters
    ----------
    save_path:
        Path to the save_data root directory as configured in Settings.

    Returns
    -------
    Sorted list of campaign name strings.  Returns an empty list if
    *save_path* does not exist or contains no recognisable campaigns.
    """
    save_path = Path(save_path).resolve()
    if not save_path.is_dir():
        return []

    found: dict[str, Path] = {}  # name → canonical path (de-dup)

    # ── 1. canonical: <save_path>/campaigns/<name>/ ───────────────────────
    campaigns_dir = save_path / "campaigns"
    if campaigns_dir.is_dir():
        try:
            for child in sorted(campaigns_dir.iterdir()):
                if child.name in _EXCLUDED_DIRS:
                    continue
                if _is_campaign_dir(child):
                    found[child.name] = child
        except PermissionError:
            pass

    # ── 2. loose: <save_path>/<name>/ (skip already-found + campaigns/) ──
    try:
        for child in sorted(save_path.iterdir()):
            if child.name in _EXCLUDED_DIRS:
                continue
            if child.name == "campaigns":
                continue  # already scanned above
            if child.name in found:
                continue  # canonical path wins
            if _is_campaign_dir(child):
                found[child.name] = child
    except PermissionError:
        pass

    return sorted(found.keys())
