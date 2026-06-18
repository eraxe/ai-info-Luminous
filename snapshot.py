#!/usr/bin/env python3
"""
Luminous AI — Snapshot Helpers
Three serialisation functions that copy prompt/category/campaign files
into a dated snapshot folder under the campaign's .snapshots/ directory.

Snapshot layout:
    <prompts_root>/../.snapshots/<snapshot_name>/
        meta.json          — snapshot metadata
        <category>/        — mirrored from prompts tree
            <file>         — verbatim copy
"""
from __future__ import annotations

import sys
from pathlib import Path as _Path

# ── standalone import fix ──────────────────────────────────────────────────────
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(_Path(__file__).resolve().parent))

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from prompt_index import PromptFileEntry, PromptIndex


# ── internal helpers ──────────────────────────────────────────────────────────

def _snapshots_dir(prompts_root: Path) -> Path:
    """Return (and create) the .snapshots directory beside prompts_root."""
    snaps = prompts_root.parent / ".snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    return snaps


def _write_meta(dest: Path, meta: dict[str, Any]) -> None:
    """Write a meta.json file into *dest*."""
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _copy_entry(entry: PromptFileEntry, dest_root: Path) -> Path:
    """Copy a single PromptFileEntry into *dest_root*, preserving rel_path."""
    dest_file = dest_root / entry.rel_path
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entry.path, dest_file)
    return dest_file


def _result(
    success: bool,
    name: str = "",
    dest: Path | None = None,
    file_count: int = 0,
    error: str = "",
) -> dict[str, Any]:
    return {
        "success": success,
        "name": name,
        "dest": str(dest) if dest else "",
        "file_count": file_count,
        "error": error,
    }


# ── public API ────────────────────────────────────────────────────────────────

def snapshot_from_file(
    entry: PromptFileEntry,
    prompts_root: Path,
    campaign_id: str,
    snapshot_name: str,
) -> dict[str, Any]:
    """Serialise a **single prompt file** into a snapshot.

    Parameters
    ----------
    entry:
        The ``PromptFileEntry`` to snapshot.
    prompts_root:
        Absolute path to the campaign's prompts directory.
    campaign_id:
        Identifier of the owning campaign (stored in meta only).
    snapshot_name:
        Human-readable name for this snapshot.

    Returns
    -------
    dict with keys: ``success``, ``name``, ``dest``, ``file_count``, ``error``.
    """
    try:
        snaps_dir = _snapshots_dir(prompts_root)
        dest = snaps_dir / snapshot_name
        if dest.exists():
            snapshot_name = f"{snapshot_name}_{datetime.now().strftime('%H%M%S')}"
            dest = snaps_dir / snapshot_name

        copied = _copy_entry(entry, dest)
        _write_meta(
            dest,
            {
                "type": "file",
                "snapshot_name": snapshot_name,
                "campaign_id": campaign_id,
                "created_at": datetime.now().isoformat(),
                "source_file": str(entry.rel_path),
                "category": entry.category,
            },
        )
        return _result(True, snapshot_name, dest, 1)
    except Exception as exc:  # noqa: BLE001
        return _result(False, snapshot_name, error=str(exc))


def snapshot_from_category(
    category_key: str,
    entries: list[PromptFileEntry],
    prompts_root: Path,
    campaign_id: str,
    snapshot_name: str,
) -> dict[str, Any]:
    """Serialise **all prompt files in a category** into a snapshot.

    Parameters
    ----------
    category_key:
        The category identifier (subdirectory name, or ``"__root__"``).
    entries:
        List of ``PromptFileEntry`` objects belonging to the category.
    prompts_root:
        Absolute path to the campaign's prompts directory.
    campaign_id:
        Identifier of the owning campaign.
    snapshot_name:
        Human-readable name for this snapshot.

    Returns
    -------
    dict with keys: ``success``, ``name``, ``dest``, ``file_count``, ``error``.
    """
    try:
        snaps_dir = _snapshots_dir(prompts_root)
        dest = snaps_dir / snapshot_name
        if dest.exists():
            snapshot_name = f"{snapshot_name}_{datetime.now().strftime('%H%M%S')}"
            dest = snaps_dir / snapshot_name

        count = 0
        for entry in entries:
            _copy_entry(entry, dest)
            count += 1

        _write_meta(
            dest,
            {
                "type": "category",
                "snapshot_name": snapshot_name,
                "campaign_id": campaign_id,
                "created_at": datetime.now().isoformat(),
                "category": category_key,
                "file_count": count,
            },
        )
        return _result(True, snapshot_name, dest, count)
    except Exception as exc:  # noqa: BLE001
        return _result(False, snapshot_name, error=str(exc))


def snapshot_from_campaign(
    prompt_index: PromptIndex,
    campaign_id: str,
    snapshot_name: str,
) -> dict[str, Any]:
    """Serialise **every prompt file in a campaign** into a snapshot.

    Parameters
    ----------
    prompt_index:
        A fully-built ``PromptIndex`` for the campaign.
    campaign_id:
        Identifier of the campaign (used in meta and dest path).
    snapshot_name:
        Human-readable name for this snapshot.

    Returns
    -------
    dict with keys: ``success``, ``name``, ``dest``, ``file_count``, ``error``.
    """
    try:
        prompts_root = prompt_index.prompts_root
        snaps_dir = _snapshots_dir(prompts_root)
        dest = snaps_dir / snapshot_name
        if dest.exists():
            snapshot_name = f"{snapshot_name}_{datetime.now().strftime('%H%M%S')}"
            dest = snaps_dir / snapshot_name

        all_entries = prompt_index.all_entries()
        count = 0
        for entry in all_entries:
            _copy_entry(entry, dest)
            count += 1

        categories = prompt_index.categories()
        _write_meta(
            dest,
            {
                "type": "campaign",
                "snapshot_name": snapshot_name,
                "campaign_id": campaign_id,
                "created_at": datetime.now().isoformat(),
                "categories": categories,
                "file_count": count,
            },
        )
        return _result(True, snapshot_name, dest, count)
    except Exception as exc:  # noqa: BLE001
        return _result(False, snapshot_name, error=str(exc))
