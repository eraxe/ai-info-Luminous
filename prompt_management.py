#!/usr/bin/env python3
"""
Luminous AI — Prompt Management Section  (Part 2: Full Editor)
PromptManagementApp: 3-panel prompt editor with save/backup/reset,
JSON form editor, paired active-file toggle, readonly mode, unsaved-changes guard.
"""
import tkinter as tk
import json
import os
import re
import sys
import platform
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from settings import SettingsManager, settings_manager as _global_sm
except ImportError as _e:
    import tkinter.messagebox as _mb
    _r = tk.Tk(); _r.withdraw()
    _mb.showerror("Import Error", f"prompt_management.py: {_e}")
    _r.destroy()
    sys.exit(1)

C = {
    "bg":        "#0d0f14",
    "surface":   "#13161e",
    "surface2":  "#1a1e29",
    "surface3":  "#212537",
    "fg":        "#e2e8f0",
    "fg_dim":    "#7b879e",
    "fg_muted":  "#445069",
    "accent":    "#7c6af7",
    "accent2":   "#38bdf8",
    "accent3":   "#f59e0b",
    "green":     "#22d3a0",
    "red":       "#f87171",
    "border":    "#252a38",
    "scrollbar": "#2a2f42",
}

PROMPT_CATEGORIES = [
    "actions",
    "character_creation",
    "diplomacy_internal_thoughts",
    "dynamic_events_generator",
    "dynamic_events_internal_thoughts",
    "group_conversation",
    "internal_thoughts",
    "json_output",
    "kingdom_statement",
    "npc_initiative",
    "rules",
    "world_data",
]

ROOT_PROMPT_FILES = [
    "playerdescription.txt",
    "PromptModuleResponse.txt",
]

CATEGORY_ICONS = {
    "actions":                          "\u25b6",
    "character_creation":               "\u25c6",
    "diplomacy_internal_thoughts":      "\u2666",
    "dynamic_events_generator":         "\u2734",
    "dynamic_events_internal_thoughts": "\u2733",
    "group_conversation":               "\u25a6",
    "internal_thoughts":                "\u25cb",
    "json_output":                      "\u2692",
    "kingdom_statement":                "\u2654",
    "npc_initiative":                   "\u25cf",
    "rules":                            "\u2261",
    "world_data":                       "\u25bb",
    "__root__":                         "\u2026",
}


# ===========================================================================
# Collections filesystem helpers
# Storage layout: <app_base>/luminous_data/collections/<safe_name>/
#   metadata.json  — collection record
#   <prompt files> — copied prompt files
# ===========================================================================

def resolve_app_base_dir() -> Path:
    """Return the directory that contains main.py (app base)."""
    # When frozen (PyInstaller) sys.executable sits next to main.py.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # Running from source: walk up from this file until main.py is found,
    # fallback to this file's directory.
    here = Path(__file__).resolve().parent
    candidate = here / "main.py"
    if candidate.is_file():
        return here
    return here


def resolve_collections_root() -> Path:
    """Return the collections root directory (does not create it)."""
    return resolve_app_base_dir() / "luminous_data" / "collections"


def ensure_collections_root() -> Path:
    """Create the collections root directory if absent; return its path."""
    root = resolve_collections_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_collection_name(name: str) -> str:
    """
    Convert an arbitrary snapshot/collection name into a safe folder name.
    - Strips leading/trailing whitespace
    - Replaces runs of whitespace and path-unsafe characters with underscores
    - Collapses consecutive underscores
    - Strips leading/trailing underscores
    - Truncates to 64 characters
    - Falls back to 'collection' if result is empty
    """
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r'\s+', "_", name)
    name = re.sub(r'_+', "_", name)
    name = name.strip("_")
    name = name[:64]
    return name if name else "collection"


def collection_meta_path(collection_dir: Path) -> Path:
    """Return the metadata.json path for a given collection directory."""
    return collection_dir / "metadata.json"


def load_collection_meta(collection_dir: Path) -> Optional[dict]:
    """
    Load and return the metadata record for a single collection directory.
    Returns None if the directory or metadata.json is missing/invalid.
    Guarantees keys: name, safe_name, created_at, file_count, path.
    """
    meta_path = collection_meta_path(collection_dir)
    if not meta_path.is_file():
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as fh:
            record = json.load(fh)
        if not isinstance(record, dict):
            return None
    except (OSError, json.JSONDecodeError):
        return None

    # Normalise guaranteed keys
    record.setdefault("name", collection_dir.name)
    record.setdefault("safe_name", collection_dir.name)
    record.setdefault("created_at", "")
    record["file_count"] = count_collection_files(collection_dir)
    record["path"] = str(collection_dir)
    return record


def list_collections() -> list[dict]:
    """
    Scan the collections root and return a list of normalised metadata records,
    sorted newest-first by the 'created_at' field (ISO-8601 string).
    Directories without a valid metadata.json are skipped.
    """
    root = resolve_collections_root()
    if not root.is_dir():
        return []

    records: list[dict] = []
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return []

    for entry in entries:
        if not entry.is_dir():
            continue
        record = load_collection_meta(entry)
        if record is not None:
            records.append(record)

    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


def count_collection_files(collection_dir: Path) -> int:
    """
    Return the number of files inside collection_dir,
    excluding metadata.json itself.
    """
    if not collection_dir.is_dir():
        return 0
    count = 0
    try:
        for item in collection_dir.iterdir():
            if item.is_file() and item.name != "metadata.json":
                count += 1
    except OSError:
        pass
    return count


# ===========================================================================
# Snapshot creation helpers
# Creates a point-in-time copy of prompt files under:
#   luminous_data/collections/<snapshot_name>/
# Each snapshot includes metadata.json and mirrored prompt files.
# ===========================================================================

def _build_snapshot_dir(snapshot_name: str) -> Path:
    """
    Resolve a collision-safe directory path for a new snapshot.
    If <safe_name> already exists, appends _2, _3, … until a free slot is found.
    Does NOT create the directory.
    """
    root = ensure_collections_root()
    safe = sanitize_collection_name(snapshot_name)
    candidate = root / safe
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = root / f"{safe}_{n}"
        if not candidate.exists():
            return candidate
        n += 1


def _write_snapshot_meta(
    snapshot_dir: Path,
    name: str,
    campaign_id: str,
    scope_type: str,
    scope_path: str,
    file_count: int,
) -> None:
    """
    Write metadata.json into snapshot_dir.

    Fields written:
        name          – human-readable snapshot name
        safe_name     – folder name on disk
        created_at    – ISO-8601 UTC timestamp
        campaign_id   – source campaign identifier
        scope_type    – "file" | "category" | "campaign"
        scope_path    – relative path used as source (file or folder)
        file_count    – number of prompt files copied
    """
    record = {
        "name": name,
        "safe_name": snapshot_dir.name,
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "campaign_id": campaign_id,
        "scope_type": scope_type,
        "scope_path": scope_path,
        "file_count": file_count,
    }
    meta_path = snapshot_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)


def _copy_prompt_file(src: Path, prompts_root: Path, snapshot_dir: Path) -> Path:
    """
    Copy a single prompt file into snapshot_dir, mirroring its relative path
    from prompts_root.  Creates intermediate subdirectories as needed.
    Returns the destination path.
    """
    try:
        rel = src.relative_to(prompts_root)
    except ValueError:
        # Fallback: place directly in snapshot root using filename only
        rel = Path(src.name)
    dest = snapshot_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def snapshot_from_file(
    entry: "PromptFileEntry",
    prompts_root: str,
    campaign_id: str,
    snapshot_name: str = "",
) -> dict:
    """
    Create a snapshot containing only the files belonging to a single
    PromptFileEntry (base file + active variant if present).

    Parameters
    ----------
    entry          : the selected PromptFileEntry
    prompts_root   : absolute path to the campaign's prompts/ directory
    campaign_id    : campaign identifier string
    snapshot_name  : optional human-readable name; auto-generated if empty

    Returns
    -------
    dict with keys:
        success      – bool
        snapshot_dir – str path to created directory
        file_count   – int number of files copied
        name         – str human-readable name used
        error        – str (only present on failure)
    """
    if not snapshot_name:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"{entry.name}_{ts}"

    prompts_root_path = Path(prompts_root)
    snapshot_dir = _build_snapshot_dir(snapshot_name)

    try:
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        copied: list[Path] = []

        base = Path(entry.base_path)
        if base.is_file():
            _copy_prompt_file(base, prompts_root_path, snapshot_dir)
            copied.append(base)

        if entry.active_path:
            active = Path(entry.active_path)
            if active.is_file():
                _copy_prompt_file(active, prompts_root_path, snapshot_dir)
                copied.append(active)

        scope_path = str(base.relative_to(prompts_root_path)) if base.is_relative_to(prompts_root_path) else str(base)
        _write_snapshot_meta(
            snapshot_dir=snapshot_dir,
            name=snapshot_name,
            campaign_id=campaign_id,
            scope_type="file",
            scope_path=scope_path,
            file_count=len(copied),
        )

        return {
            "success": True,
            "snapshot_dir": str(snapshot_dir),
            "file_count": len(copied),
            "name": snapshot_name,
        }
    except Exception as exc:
        # Clean up partial directory on failure
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        return {"success": False, "error": str(exc), "name": snapshot_name}


def snapshot_from_category(
    category_key: str,
    entries: "list[PromptFileEntry]",
    prompts_root: str,
    campaign_id: str,
    snapshot_name: str = "",
) -> dict:
    """
    Create a snapshot of all files in a single category.

    Parameters
    ----------
    category_key   : e.g. "actions" or "__root__"
    entries        : list of PromptFileEntry objects for the category
    prompts_root   : absolute path to the campaign's prompts/ directory
    campaign_id    : campaign identifier string
    snapshot_name  : optional human-readable name; auto-generated if empty

    Returns
    -------
    dict with keys: success, snapshot_dir, file_count, name, error (on fail)
    """
    if not snapshot_name:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = category_key if category_key != "__root__" else "root"
        snapshot_name = f"{campaign_id}_{label}_{ts}"

    prompts_root_path = Path(prompts_root)
    snapshot_dir = _build_snapshot_dir(snapshot_name)

    try:
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        copied: list[Path] = []

        for entry in entries:
            base = Path(entry.base_path)
            if base.is_file():
                _copy_prompt_file(base, prompts_root_path, snapshot_dir)
                copied.append(base)
            if entry.active_path:
                active = Path(entry.active_path)
                if active.is_file():
                    _copy_prompt_file(active, prompts_root_path, snapshot_dir)
                    copied.append(active)

        # scope_path: relative category folder (or "." for root)
        if category_key == "__root__":
            scope_path = "."
        else:
            cat_dir = prompts_root_path / category_key
            scope_path = category_key if cat_dir.is_dir() else category_key

        _write_snapshot_meta(
            snapshot_dir=snapshot_dir,
            name=snapshot_name,
            campaign_id=campaign_id,
            scope_type="category",
            scope_path=scope_path,
            file_count=len(copied),
        )

        return {
            "success": True,
            "snapshot_dir": str(snapshot_dir),
            "file_count": len(copied),
            "name": snapshot_name,
        }
    except Exception as exc:
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        return {"success": False, "error": str(exc), "name": snapshot_name}


def snapshot_from_campaign(
    prompt_index: "PromptIndex",
    campaign_id: str,
    snapshot_name: str = "",
) -> dict:
    """
    Create a snapshot of the entire active campaign's prompts/ folder.

    Parameters
    ----------
    prompt_index   : a fully scanned PromptIndex for the campaign
    campaign_id    : campaign identifier string
    snapshot_name  : optional human-readable name; auto-generated if empty

    Returns
    -------
    dict with keys: success, snapshot_dir, file_count, name, error (on fail)
    """
    if not snapshot_name:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"{campaign_id}_full_{ts}"

    prompts_root = prompt_index.prompts_root
    prompts_root_path = Path(prompts_root)
    snapshot_dir = _build_snapshot_dir(snapshot_name)

    try:
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        copied: list[Path] = []

        # Root entries
        for entry in prompt_index.root_entries:
            base = Path(entry.base_path)
            if base.is_file():
                _copy_prompt_file(base, prompts_root_path, snapshot_dir)
                copied.append(base)

        # Category entries (all categories)
        for cat_key, cat_model in prompt_index.categories.items():
            for entry in cat_model.entries:
                base = Path(entry.base_path)
                if base.is_file():
                    _copy_prompt_file(base, prompts_root_path, snapshot_dir)
                    copied.append(base)
                if entry.active_path:
                    active = Path(entry.active_path)
                    if active.is_file():
                        _copy_prompt_file(active, prompts_root_path, snapshot_dir)
                        copied.append(active)

        _write_snapshot_meta(
            snapshot_dir=snapshot_dir,
            name=snapshot_name,
            campaign_id=campaign_id,
            scope_type="campaign",
            scope_path="prompts/",
            file_count=len(copied),
        )

        return {
            "success": True,
            "snapshot_dir": str(snapshot_dir),
            "file_count": len(copied),
            "name": snapshot_name,
        }
    except Exception as exc:
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        return {"success": False, "error": str(exc), "name": snapshot_name}


# ===========================================================================
# Data model
# ===========================================================================

class PromptFileEntry:
    __slots__ = ("name", "base_path", "active_path", "kind", "category")

    def __init__(self, name: str, base_path: str,
                 active_path: Optional[str],
                 kind: str,
                 category: str):
        self.name = name
        self.base_path = base_path
        self.active_path = active_path
        self.kind = kind
        self.category = category

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def has_active(self) -> bool:
        return self.active_path is not None

    @property
    def type_tag(self) -> str:
        if self.kind == "json":
            return "JSON"
        if self.kind == "paired":
            return "PAIRED"
        return "TXT"


class CategoryModel:
    __slots__ = ("key", "path", "entries", "exists")

    def __init__(self, key: str, path: str):
        self.key = key
        self.path = path
        self.entries: list[PromptFileEntry] = []
        self.exists: bool = False

    @property
    def count(self) -> int:
        return len(self.entries)


class PromptIndex:
    def __init__(self):
        self.campaign_id: str = ""
        self.prompts_root: str = ""
        self.categories: dict[str, CategoryModel] = {}
        self.root_entries: list[PromptFileEntry] = []

    def scan(self, save_data_path: str, campaign_id: str) -> bool:
        self.campaign_id = campaign_id
        self.prompts_root = os.path.join(save_data_path, campaign_id, "prompts")
        self.categories = {}
        self.root_entries = []

        if not os.path.isdir(self.prompts_root):
            return False

        for cat_key in PROMPT_CATEGORIES:
            cat_path = os.path.join(self.prompts_root, cat_key)
            model = CategoryModel(cat_key, cat_path)
            model.exists = os.path.isdir(cat_path)
            if model.exists:
                model.entries = _scan_category_folder(cat_path, cat_key)
            self.categories[cat_key] = model

        for fname in ROOT_PROMPT_FILES:
            fp = os.path.join(self.prompts_root, fname)
            if os.path.isfile(fp):
                self.root_entries.append(
                    PromptFileEntry(name=fname, base_path=fp,
                                    active_path=None, kind="txt", category="__root__")
                )
        try:
            for fname in sorted(os.listdir(self.prompts_root)):
                fp = os.path.join(self.prompts_root, fname)
                if not os.path.isfile(fp):
                    continue
                if fname in ROOT_PROMPT_FILES:
                    continue
                if fname.endswith(".txt") and not fname.endswith("_active.txt"):
                    self.root_entries.append(
                        PromptFileEntry(name=fname, base_path=fp,
                                        active_path=None, kind="txt", category="__root__")
                    )
        except OSError:
            pass

        return True

    def total_files(self) -> int:
        n = len(self.root_entries)
        for cm in self.categories.values():
            n += cm.count
        return n

    def entries_for_category(self, key: str) -> list[PromptFileEntry]:
        if key == "__root__":
            return list(self.root_entries)
        cm = self.categories.get(key)
        return list(cm.entries) if cm else []


def _scan_category_folder(folder: str, cat_key: str) -> list[PromptFileEntry]:
    entries: list[PromptFileEntry] = []
    try:
        all_files = sorted(os.listdir(folder))
    except OSError:
        return entries

    seen: set[str] = set()
    active_set: set[str] = set(all_files)

    for fn in all_files:
        if fn in seen:
            continue
        fp = os.path.join(folder, fn)
        if not os.path.isfile(fp):
            continue

        if fn.endswith("_active.txt"):
            seen.add(fn)
            continue

        if fn.endswith(".json"):
            entries.append(PromptFileEntry(name=fn, base_path=fp,
                                            active_path=None, kind="json", category=cat_key))
            seen.add(fn)
            continue

        if fn.endswith(".txt"):
            stem = fn[:-len(".txt")]
            active_fn = stem + "_active.txt"
            active_fp = os.path.join(folder, active_fn) if active_fn in active_set else None
            kind = "paired" if active_fp and os.path.isfile(active_fp) else "txt"
            entries.append(PromptFileEntry(name=fn, base_path=fp,
                                            active_path=active_fp, kind=kind, category=cat_key))
            seen.add(fn)
            if active_fn in active_set:
                seen.add(active_fn)

    return entries


# ===========================================================================
# Campaign discovery
# ===========================================================================

def discover_campaigns(save_data_path: str) -> list[str]:
    if not save_data_path or not os.path.isdir(save_data_path):
        return []
    campaigns = []
    try:
        for entry in sorted(os.listdir(save_data_path)):
            if entry.startswith("."):
                continue
            if os.path.isdir(os.path.join(save_data_path, entry)):
                campaigns.append(entry)
    except OSError:
        pass
    return campaigns


# ===========================================================================
# Shared widget helpers (no ttk)
# ===========================================================================

class FlatButton(tk.Label):
    def __init__(self, parent, text="", command=None,
                 bg=C["surface2"], fg=C["fg"],
                 hover_bg=C["surface3"], hover_fg=C["accent"],
                 font=("Segoe UI", 9), padx=12, pady=6, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font,
                         padx=padx, pady=pady, cursor="hand2", **kw)
        self._bg, self._fg = bg, fg
        self._hbg, self._hfg = hover_bg, hover_fg
        self._cmd = command
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _=None): self.config(bg=self._hbg, fg=self._hfg)
    def _on_leave(self, _=None): self.config(bg=self._bg, fg=self._fg)
    def _on_click(self, _=None):
        self._on_enter()
        if self._cmd:
            self.after(50, self._cmd)

    def set_enabled(self, enabled: bool):
        if enabled:
            self.config(cursor="hand2", fg=self._fg)
            self.bind("<Button-1>", self._on_click)
        else:
            self.config(cursor="", fg=C["fg_muted"])
            self.unbind("<Button-1>")


class AccentButton(FlatButton):
    def __init__(self, parent, text="", command=None, **kw):
        super().__init__(parent, text=text, command=command,
                         bg=C["accent"], fg="#ffffff",
                         hover_bg="#9580ff", hover_fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), **kw)


class StatusBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["surface"], height=26, **kw)
        self.pack_propagate(False)
        self._dot = tk.Label(self, text="\u25cf", bg=C["surface"], fg=C["green"],
                             font=("Segoe UI", 9))
        self._dot.pack(side=tk.LEFT, padx=(10, 4))
        self._msg = tk.Label(self, text="Ready", bg=C["surface"], fg=C["fg_dim"],
                             font=("Segoe UI", 9), anchor="w")
        self._msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._timer = None

    def set(self, msg, level="ok"):
        color = {"ok": C["green"], "warn": C["accent3"],
                 "error": C["red"], "info": C["accent2"]}.get(level, C["green"])
        self._dot.config(fg=color)
        self._msg.config(text=msg, fg=C["fg"])
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(5000, lambda: self._msg.config(text="Ready", fg=C["fg_dim"]))


# ===========================================================================
# CustomTitleBar
# ===========================================================================

class CustomTitleBar(tk.Frame):
    def __init__(self, parent, app, title=""):
        super().__init__(parent, bg=C["bg"], height=36)
        self.pack_propagate(False)
        self.app = app
        self.root = app.root
        self._is_max = False
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>", self._do_move)

        back = tk.Label(self, text="\u2b21 Hub", bg=C["bg"], fg=C["fg_muted"],
                        font=("Segoe UI", 8), padx=10, pady=6, cursor="hand2")
        back.pack(side=tk.LEFT)
        back.bind("<Enter>", lambda e: back.config(fg=C["accent"]))
        back.bind("<Leave>", lambda e: back.config(fg=C["fg_muted"]))
        back.bind("<Button-1>", lambda e: app.back_to_hub())

        tk.Frame(self, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y,
                                                     padx=(0, 8), pady=6)
        lbl = tk.Label(self, text=f" {title}", bg=C["bg"], fg=C["fg_dim"],
                       font=("Segoe UI", 9, "bold"))
        lbl.pack(side=tk.LEFT, padx=4)
        lbl.bind("<ButtonPress-1>", self._start_move)
        lbl.bind("<B1-Motion>", self._do_move)

        btns = tk.Frame(self, bg=C["bg"])
        btns.pack(side=tk.RIGHT, fill=tk.Y)
        FlatButton(btns, text="\u2014", command=self._minimize,
                   bg=C["bg"], hover_bg=C["surface3"], padx=14).pack(side=tk.LEFT, fill=tk.Y)
        self._max_btn = FlatButton(btns, text="\u2610", command=self._toggle_max,
                                   bg=C["bg"], hover_bg=C["surface3"], padx=14)
        self._max_btn.pack(side=tk.LEFT, fill=tk.Y)
        FlatButton(btns, text="\u2715",
                   command=lambda: self.root.event_generate("WM_DELETE_WINDOW"),
                   bg=C["bg"], hover_bg=C["red"], hover_fg="#fff",
                   padx=14).pack(side=tk.LEFT, fill=tk.Y)

    def _start_move(self, e):
        if not self._is_max:
            self.root.x, self.root.y = e.x, e.y

    def _do_move(self, e):
        if not self._is_max:
            x = self.root.winfo_x() + e.x - self.root.x
            y = self.root.winfo_y() + e.y - self.root.y
            self.root.geometry(f"+{x}+{y}")

    def _minimize(self):
        if platform.system() == "Windows":
            self.root.overrideredirect(False)
            self.root.iconify()
            self.root.bind("<Map>", lambda e: (
                self.root.overrideredirect(True), self.root.unbind("<Map>")))
        else:
            self.root.iconify()

    def _toggle_max(self):
        if self._is_max:
            self.root.geometry(self._norm_geo)
            self._is_max = False
            self._max_btn.config(text="\u2610")
        else:
            self._norm_geo = self.root.geometry()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self._is_max = True
            self._max_btn.config(text="\u2750")


# ===========================================================================
# VirtualList — Canvas-based virtualised file list (Panel 2)
# ===========================================================================

ROW_H = 38
ROW_PAD_X = 10

TYPE_COLORS = {
    "TXT":    C["fg_dim"],
    "PAIRED": C["accent2"],
    "JSON":   C["accent3"],
}


class VirtualFileList(tk.Frame):
    def __init__(self, parent, on_select=None, **kw):
        super().__init__(parent, bg=C["surface"], **kw)
        self._on_select = on_select
        self._entries: list[PromptFileEntry] = []
        self._filtered: list[PromptFileEntry] = []
        self._selected_idx: Optional[int] = None
        self._hover_idx: Optional[int] = None

        self._canvas = tk.Canvas(self, bg=C["surface"], highlightthickness=0, bd=0)
        self._sb = tk.Scrollbar(self, orient="vertical",
                                command=self._canvas.yview,
                                bg=C["scrollbar"], troughcolor=C["bg"],
                                width=6, bd=0, relief="flat")
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._canvas.bind("<Configure>", self._on_resize)
        self._canvas.bind("<MouseWheel>", self._on_wheel)
        self._canvas.bind("<Button-4>", lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>", lambda e: self._canvas.yview_scroll(1, "units"))
        self._canvas.bind("<Motion>", self._on_mouse_motion)
        self._canvas.bind("<Leave>", self._on_mouse_leave)
        self._canvas.bind("<Button-1>", self._on_click)

        self._canvas_width = 240

    def load(self, entries: list[PromptFileEntry], search_term: str = "") -> None:
        self._entries = entries
        self._apply_filter(search_term)

    def filter(self, search_term: str) -> None:
        self._apply_filter(search_term)

    def clear_selection(self) -> None:
        self._selected_idx = None
        self._redraw()

    def selected_entry(self) -> Optional[PromptFileEntry]:
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._filtered):
            return self._filtered[self._selected_idx]
        return None

    def _apply_filter(self, term: str) -> None:
        t = term.strip().lower()
        self._filtered = [e for e in self._entries if t in e.name.lower()] if t else list(self._entries)
        self._selected_idx = None
        self._hover_idx = None
        self._update_scroll_region()
        self._redraw()

    def _update_scroll_region(self) -> None:
        total_h = len(self._filtered) * ROW_H
        self._canvas.configure(scrollregion=(0, 0, self._canvas_width, max(total_h, 1)))

    def _on_resize(self, event) -> None:
        self._canvas_width = event.width
        self._update_scroll_region()
        self._redraw()

    def _on_wheel(self, event) -> None:
        self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _visible_range(self) -> tuple[int, int]:
        top = self._canvas.canvasy(0)
        bottom = top + self._canvas.winfo_height()
        first = max(0, int(top // ROW_H))
        last = min(len(self._filtered), int(bottom // ROW_H) + 2)
        return first, last

    def _redraw(self) -> None:
        self._canvas.delete("all")
        if not self._filtered:
            self._canvas.create_text(
                self._canvas_width // 2, 40,
                text="No files", fill=C["fg_muted"],
                font=("Segoe UI", 9), anchor="center"
            )
            return
        first, last = self._visible_range()
        for i in range(first, last):
            self._draw_row(i)

    def _draw_row(self, idx: int) -> None:
        if idx >= len(self._filtered):
            return
        entry = self._filtered[idx]
        y0 = idx * ROW_H
        y1 = y0 + ROW_H
        w = self._canvas_width

        if idx == self._selected_idx:
            bg = C["surface3"]
        elif idx == self._hover_idx:
            bg = C["surface2"]
        else:
            bg = C["surface"]

        self._canvas.create_rectangle(0, y0, w, y1, fill=bg, outline="")
        if idx == self._selected_idx:
            self._canvas.create_rectangle(0, y0, 3, y1, fill=C["accent2"], outline="")
        self._canvas.create_line(0, y1 - 1, w, y1 - 1, fill=C["border"])

        tag_text = entry.type_tag
        tag_color = TYPE_COLORS.get(tag_text, C["fg_muted"])
        self._canvas.create_text(
            ROW_PAD_X, y0 + ROW_H // 2,
            text=tag_text, fill=tag_color,
            font=("Segoe UI", 7, "bold"), anchor="w"
        )

        name_x = ROW_PAD_X + 46
        fg = C["fg"] if idx == self._selected_idx else C["fg_dim"]
        self._canvas.create_text(
            name_x, y0 + ROW_H // 2 - (5 if entry.has_active else 0),
            text=entry.display_name, fill=fg,
            font=("Segoe UI", 9), anchor="w"
        )

        if entry.has_active:
            self._canvas.create_oval(name_x, y0 + ROW_H // 2 + 5,
                                     name_x + 7, y0 + ROW_H // 2 + 12,
                                     fill=C["green"], outline="")
            self._canvas.create_text(
                name_x + 10, y0 + ROW_H // 2 + 8,
                text="active variant", fill=C["green"],
                font=("Segoe UI", 7), anchor="w"
            )

    def _row_at_y(self, canvas_y: float) -> Optional[int]:
        idx = int(canvas_y // ROW_H)
        return idx if 0 <= idx < len(self._filtered) else None

    def _on_mouse_motion(self, event) -> None:
        cy = self._canvas.canvasy(event.y)
        new_hover = self._row_at_y(cy)
        if new_hover != self._hover_idx:
            old, self._hover_idx = self._hover_idx, new_hover
            if old is not None:
                self._draw_row(old)
            if new_hover is not None:
                self._draw_row(new_hover)

    def _on_mouse_leave(self, event=None) -> None:
        old, self._hover_idx = self._hover_idx, None
        if old is not None:
            self._draw_row(old)

    def _on_click(self, event) -> None:
        cy = self._canvas.canvasy(event.y)
        idx = self._row_at_y(cy)
        if idx is None:
            return
        old, self._selected_idx = self._selected_idx, idx
        if old is not None:
            self._draw_row(old)
        self._draw_row(idx)
        if self._on_select:
            self._on_select(self._filtered[idx])


# ===========================================================================
# CategoryTree — Panel 1 lower section
# ===========================================================================

class CategoryTree(tk.Frame):
    def __init__(self, parent, on_select=None, **kw):
        super().__init__(parent, bg=C["surface"], **kw)
        self._on_select = on_select
        self._active_key: Optional[str] = None
        self._rows: dict[str, dict] = {}
        self._build()

    def _build(self) -> None:
        canvas = tk.Canvas(self, bg=C["surface"], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                          bg=C["scrollbar"], troughcolor=C["bg"], width=5, bd=0)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=C["surface"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        self._add_row(inner, "__root__", "Root Files")
        for cat_key in PROMPT_CATEGORIES:
            label = cat_key.replace("_", " ").title()
            self._add_row(inner, cat_key, label)

    def _add_row(self, parent, key: str, label: str) -> None:
        icon = CATEGORY_ICONS.get(key, "\u25b8")
        row = tk.Frame(parent, bg=C["surface"], cursor="hand2", height=30)
        row.pack(fill=tk.X)
        row.pack_propagate(False)

        indicator = tk.Frame(row, bg=C["surface"], width=3)
        indicator.pack(side=tk.LEFT, fill=tk.Y)

        icon_lbl = tk.Label(row, text=icon, bg=C["surface"], fg=C["fg_muted"],
                            font=("Segoe UI", 9))
        icon_lbl.pack(side=tk.LEFT, padx=(6, 2), pady=4)

        name_lbl = tk.Label(row, text=label, bg=C["surface"], fg=C["fg_dim"],
                            font=("Segoe UI", 9), anchor="w")
        name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        badge = tk.Label(row, text="", bg=C["surface"], fg=C["fg_muted"],
                         font=("Segoe UI", 8), padx=6)
        badge.pack(side=tk.RIGHT, padx=(0, 6))

        self._rows[key] = {
            "frame": row, "indicator": indicator,
            "icon_lbl": icon_lbl, "name_lbl": name_lbl, "badge": badge,
        }

        for w in (row, indicator, icon_lbl, name_lbl, badge):
            w.bind("<Enter>", lambda e, k=key: self._hover_on(k))
            w.bind("<Leave>", lambda e, k=key: self._hover_off(k))
            w.bind("<Button-1>", lambda e, k=key: self._click(k))

    def set_counts(self, counts: dict[str, int]) -> None:
        for key, widgets in self._rows.items():
            n = counts.get(key, 0)
            widgets["badge"].config(text=str(n) if n else "")

    def set_active(self, key: Optional[str]) -> None:
        if self._active_key and self._active_key in self._rows:
            self._deactivate(self._active_key)
        self._active_key = key
        if key and key in self._rows:
            self._activate(key)

    def _activate(self, key: str) -> None:
        w = self._rows[key]
        w["frame"].config(bg=C["surface3"])
        w["indicator"].config(bg=C["accent2"])
        w["icon_lbl"].config(bg=C["surface3"], fg=C["accent2"])
        w["name_lbl"].config(bg=C["surface3"], fg=C["fg"])
        w["badge"].config(bg=C["surface3"])

    def _deactivate(self, key: str) -> None:
        w = self._rows[key]
        for widget in (w["frame"], w["icon_lbl"], w["name_lbl"], w["badge"]):
            widget.config(bg=C["surface"])
        w["indicator"].config(bg=C["surface"])
        w["icon_lbl"].config(fg=C["fg_muted"])
        w["name_lbl"].config(fg=C["fg_dim"])

    def _hover_on(self, key: str) -> None:
        if key == self._active_key:
            return
        w = self._rows[key]
        for widget in (w["frame"], w["icon_lbl"], w["name_lbl"], w["badge"]):
            widget.config(bg=C["surface2"])

    def _hover_off(self, key: str) -> None:
        if key == self._active_key:
            return
        w = self._rows[key]
        for widget in (w["frame"], w["icon_lbl"], w["name_lbl"], w["badge"]):
            widget.config(bg=C["surface"])

    def _click(self, key: str) -> None:
        self.set_active(key)
        if self._on_select:
            self._on_select(key)


# ===========================================================================
# Panel 3 — Prompt Editor
# ===========================================================================

def _truncate_path(path: str, max_len: int) -> str:
    if len(path) <= max_len:
        return path
    return "\u2026" + path[-(max_len - 1):]


def _make_backup(file_path: str, prompts_root: str) -> None:
    """Copy file_path to prompts_root/.bak/<stem>_<timestamp>_<n>.bak avoiding collisions."""
    bak_dir = os.path.join(prompts_root, ".bak")
    os.makedirs(bak_dir, exist_ok=True)
    stem = os.path.basename(file_path)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{stem}_{ts}"
    dest = os.path.join(bak_dir, base_name + ".bak")
    n = 0
    while os.path.exists(dest):
        n += 1
        dest = os.path.join(bak_dir, f"{base_name}_{n}.bak")
    shutil.copy2(file_path, dest)


class ToggleSwitch(tk.Frame):
    """Simple two-option toggle. Calls on_change(option_key) on click."""

    def __init__(self, parent, options: list[tuple[str, str]],
                 on_change=None, **kw):
        super().__init__(parent, bg=C["surface2"], **kw)
        self._on_change = on_change
        self._btns: dict[str, tk.Label] = {}
        self._active: Optional[str] = None
        for key, label in options:
            btn = tk.Label(self, text=label, bg=C["surface2"], fg=C["fg_dim"],
                           font=("Segoe UI", 8, "bold"), padx=10, pady=4, cursor="hand2")
            btn.pack(side=tk.LEFT)
            btn.bind("<Button-1>", lambda e, k=key: self._click(k))
            self._btns[key] = btn
        if options:
            self._set(options[0][0])

    def _click(self, key: str) -> None:
        self._set(key)
        if self._on_change:
            self._on_change(key)

    def _set(self, key: str) -> None:
        self._active = key
        for k, btn in self._btns.items():
            if k == key:
                btn.config(bg=C["accent"], fg="#ffffff")
            else:
                btn.config(bg=C["surface2"], fg=C["fg_dim"])

    def set(self, key: str) -> None:
        self._set(key)

    @property
    def active(self) -> Optional[str]:
        return self._active


class JsonFormEditor(tk.Frame):
    """
    Editable key-value form for .json files in world_data/.
    Supports add/remove rows and a toggle to switch to raw JSON view.
    """

    def __init__(self, parent, readonly: bool = False, on_dirty=None, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self._readonly = readonly
        self._on_dirty = on_dirty
        self._data: dict = {}
        self._mode = "form"   # "form" or "raw"
        self._row_widgets: list[dict] = []
        self._build()

    def _build(self) -> None:
        toolbar = tk.Frame(self, bg=C["surface"])
        toolbar.pack(fill=tk.X)

        self._mode_toggle = ToggleSwitch(
            toolbar,
            options=[("form", "Form"), ("raw", "Raw JSON")],
            on_change=self._switch_mode
        )
        self._mode_toggle.pack(side=tk.LEFT, padx=8, pady=6)

        if not self._readonly:
            FlatButton(toolbar, text="+ Add Row", command=self._add_row,
                       bg=C["surface"], fg=C["accent2"],
                       hover_bg=C["surface2"], hover_fg=C["accent2"],
                       font=("Segoe UI", 8), padx=8, pady=4).pack(side=tk.RIGHT, padx=8)

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # form panel
        self._form_outer = tk.Frame(self, bg=C["bg"])
        self._form_outer.pack(fill=tk.BOTH, expand=True)

        form_canvas = tk.Canvas(self._form_outer, bg=C["bg"], highlightthickness=0, bd=0)
        form_sb = tk.Scrollbar(self._form_outer, orient="vertical", command=form_canvas.yview,
                               bg=C["scrollbar"], troughcolor=C["bg"], width=6, bd=0)
        form_canvas.configure(yscrollcommand=form_sb.set)
        form_sb.pack(side=tk.RIGHT, fill=tk.Y)
        form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._form_inner = tk.Frame(form_canvas, bg=C["bg"])
        self._form_win = form_canvas.create_window((0, 0), window=self._form_inner, anchor="nw")
        form_canvas.bind("<Configure>",
                         lambda e: form_canvas.itemconfig(self._form_win, width=e.width))
        self._form_inner.bind("<Configure>",
                              lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.bind("<MouseWheel>",
                         lambda e: form_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self._form_canvas = form_canvas

        # raw panel (hidden by default)
        self._raw_outer = tk.Frame(self, bg=C["bg"])
        self._raw_text = tk.Text(
            self._raw_outer, wrap=tk.NONE, bg=C["surface"], fg=C["fg"],
            insertbackground=C["accent"], selectbackground=C["accent"],
            selectforeground="#ffffff", font=("Consolas", 10),
            borderwidth=0, highlightthickness=0, padx=12, pady=10
        )
        raw_ysb = tk.Scrollbar(self._raw_outer, orient="vertical", command=self._raw_text.yview,
                               bg=C["scrollbar"], troughcolor=C["bg"], width=6, bd=0)
        raw_xsb = tk.Scrollbar(self._raw_outer, orient="horizontal", command=self._raw_text.xview,
                               bg=C["scrollbar"], troughcolor=C["bg"], width=6, bd=0)
        self._raw_text.configure(yscrollcommand=raw_ysb.set, xscrollcommand=raw_xsb.set)
        raw_ysb.pack(side=tk.RIGHT, fill=tk.Y)
        raw_xsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._raw_text.pack(fill=tk.BOTH, expand=True)

    def load(self, data: dict) -> None:
        self._data = data if isinstance(data, dict) else {}
        self._rebuild_form()
        if self._mode == "raw":
            self._refresh_raw()

    def get_data(self) -> dict:
        if self._mode == "raw":
            return json.loads(self._raw_text.get("1.0", "end-1c"))
        result = {}
        for row in self._row_widgets:
            key = row["key_var"].get().strip()
            val_raw = row["val_var"].get()
            if not key:
                continue
            try:
                result[key] = json.loads(val_raw)
            except (json.JSONDecodeError, ValueError):
                result[key] = val_raw
        return result

    def set_readonly(self, readonly: bool) -> None:
        self._readonly = readonly
        state = "disabled" if readonly else "normal"
        self._raw_text.config(state=state)
        for row in self._row_widgets:
            row["key_entry"].config(state=state)
            row["val_entry"].config(state=state)
            if "del_btn" in row:
                row["del_btn"].pack_forget() if readonly else row["del_btn"].pack(side=tk.RIGHT, padx=4)

    def _switch_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        if mode == "raw":
            try:
                self._data = self.get_data()
            except Exception:
                pass
            self._form_outer.pack_forget()
            self._raw_outer.pack(fill=tk.BOTH, expand=True)
            self._refresh_raw()
        else:
            try:
                raw = self._raw_text.get("1.0", "end-1c").strip()
                if raw:
                    self._data = json.loads(raw)
            except Exception:
                pass
            self._raw_outer.pack_forget()
            self._form_outer.pack(fill=tk.BOTH, expand=True)
            self._rebuild_form()
        self._mode = mode

    def _refresh_raw(self) -> None:
        state = "disabled" if self._readonly else "normal"
        self._raw_text.config(state="normal")
        self._raw_text.delete("1.0", tk.END)
        self._raw_text.insert(tk.END, json.dumps(self._data, indent=2, ensure_ascii=False))
        self._raw_text.config(state=state)

    def _rebuild_form(self) -> None:
        for w in self._form_inner.winfo_children():
            w.destroy()
        self._row_widgets = []
        for key, val in self._data.items():
            self._add_form_row(key, val)

    def _add_form_row(self, key: str = "", val=None) -> None:
        val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val

        row_frame = tk.Frame(self._form_inner, bg=C["surface2"])
        row_frame.pack(fill=tk.X, padx=8, pady=2)

        key_var = tk.StringVar(value=key)
        val_var = tk.StringVar(value=val_str)

        state = "disabled" if self._readonly else "normal"

        key_entry = tk.Entry(row_frame, textvariable=key_var, width=22,
                             bg=C["surface3"], fg=C["accent2"],
                             insertbackground=C["accent"],
                             selectbackground=C["accent"], selectforeground="#fff",
                             relief="flat", borderwidth=0,
                             highlightthickness=1, highlightbackground=C["border"],
                             font=("Consolas", 9), state=state)
        key_entry.pack(side=tk.LEFT, padx=(8, 4), pady=6)

        sep = tk.Label(row_frame, text=":", bg=C["surface2"], fg=C["fg_muted"],
                       font=("Segoe UI", 9))
        sep.pack(side=tk.LEFT)

        val_entry = tk.Entry(row_frame, textvariable=val_var,
                             bg=C["surface3"], fg=C["fg"],
                             insertbackground=C["accent"],
                             selectbackground=C["accent"], selectforeground="#fff",
                             relief="flat", borderwidth=0,
                             highlightthickness=1, highlightbackground=C["border"],
                             font=("Consolas", 9), state=state)
        val_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4), pady=6)

        row_info = {"key_var": key_var, "val_var": val_var,
                    "key_entry": key_entry, "val_entry": val_entry}

        if not self._readonly:
            del_btn = tk.Label(row_frame, text="\u2298", bg=C["surface2"], fg=C["fg_muted"],
                               font=("Segoe UI", 11), cursor="hand2", padx=6)
            del_btn.pack(side=tk.RIGHT, padx=4)
            del_btn.bind("<Enter>", lambda e: del_btn.config(fg=C["red"]))
            del_btn.bind("<Leave>", lambda e: del_btn.config(fg=C["fg_muted"]))
            del_btn.bind("<Button-1>", lambda e, rf=row_frame, ri=row_info: self._del_row(rf, ri))
            row_info["del_btn"] = del_btn

        if self._on_dirty and not self._readonly:
            key_var.trace_add("write", lambda *_: self._on_dirty())
            val_var.trace_add("write", lambda *_: self._on_dirty())

        self._row_widgets.append(row_info)

    def _add_row(self) -> None:
        self._add_form_row("", "")
        if self._on_dirty:
            self._on_dirty()

    def _del_row(self, row_frame: tk.Frame, row_info: dict) -> None:
        row_frame.destroy()
        if row_info in self._row_widgets:
            self._row_widgets.remove(row_info)
        if self._on_dirty:
            self._on_dirty()


class PromptEditor(tk.Frame):
    """
    Panel 3: full editor for prompt files.
    Handles txt, paired (with toggle), and json (form + raw).
    """

    def __init__(self, parent, get_readonly, get_prompts_root, on_status, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self._get_readonly = get_readonly
        self._get_prompts_root = get_prompts_root
        self._on_status = on_status

        self._entry: Optional[PromptFileEntry] = None
        self._active_side = "base"   # "base" or "active"
        self._disk_content_base: str = ""
        self._disk_content_active: str = ""
        self._disk_json: dict = {}
        self._dirty = False

        self._build()
        self._show_empty()

    # ---- public ----

    def load_entry(self, entry: PromptFileEntry) -> None:
        self._entry = entry
        self._active_side = "base"
        self._dirty = False
        self._refresh_editor()

    def clear(self) -> None:
        self._entry = None
        self._dirty = False
        self._show_empty()

    @property
    def has_unsaved(self) -> bool:
        return self._dirty

    # ---- build ----

    def _build(self) -> None:
        # header bar
        self._hdr = tk.Frame(self, bg=C["surface"], height=56)
        self._hdr.pack(fill=tk.X)
        self._hdr.pack_propagate(False)

        self._hdr_left = tk.Frame(self._hdr, bg=C["surface"])
        self._hdr_left.pack(side=tk.LEFT, fill=tk.Y, padx=(14, 0))

        self._fn_lbl = tk.Label(self._hdr_left, text="", bg=C["surface"], fg=C["fg"],
                                font=("Segoe UI", 11, "bold"), anchor="w")
        self._fn_lbl.pack(anchor="w", pady=(8, 0))

        self._meta_lbl = tk.Label(self._hdr_left, text="", bg=C["surface"], fg=C["fg_muted"],
                                  font=("Segoe UI", 8), anchor="w")
        self._meta_lbl.pack(anchor="w")

        self._hdr_right = tk.Frame(self._hdr, bg=C["surface"])
        self._hdr_right.pack(side=tk.RIGHT, fill=tk.Y, padx=12)

        # unsaved indicator
        self._dirty_lbl = tk.Label(self._hdr_right, text="\u25cf unsaved",
                                   bg=C["surface"], fg=C["accent3"],
                                   font=("Segoe UI", 8))

        # action buttons row
        self._btn_row = tk.Frame(self._hdr_right, bg=C["surface"])
        self._btn_row.pack(side=tk.BOTTOM, pady=(0, 6))

        self._save_btn = AccentButton(self._btn_row, text="\u2713 Save",
                                     command=self._do_save, padx=10, pady=4)
        self._save_btn.pack(side=tk.LEFT, padx=2)

        self._reset_btn = FlatButton(self._btn_row, text="\u21ba Reset",
                                     command=self._do_reset,
                                     bg=C["surface2"], fg=C["fg_dim"],
                                     hover_bg=C["surface3"], hover_fg=C["accent3"],
                                     font=("Segoe UI", 9), padx=10, pady=4)
        self._reset_btn.pack(side=tk.LEFT, padx=2)

        self._explorer_btn = FlatButton(self._btn_row, text="\u25a1 Explorer",
                                        command=self._open_explorer,
                                        bg=C["surface2"], fg=C["fg_dim"],
                                        hover_bg=C["surface3"], hover_fg=C["accent2"],
                                        font=("Segoe UI", 9), padx=10, pady=4)
        self._explorer_btn.pack(side=tk.LEFT, padx=2)

        self._copy_btn = FlatButton(self._btn_row, text="\u2398 Copy",
                                    command=self._copy_to_clipboard,
                                    bg=C["surface2"], fg=C["fg_dim"],
                                    hover_bg=C["surface3"], hover_fg=C["fg"],
                                    font=("Segoe UI", 9), padx=10, pady=4)
        self._copy_btn.pack(side=tk.LEFT, padx=2)

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # toggle row (paired files)
        self._toggle_row = tk.Frame(self, bg=C["surface2"], height=34)
        self._toggle_row.pack_propagate(False)
        tk.Label(self._toggle_row, text="Variant:", bg=C["surface2"], fg=C["fg_muted"],
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(12, 6))
        self._variant_toggle = ToggleSwitch(
            self._toggle_row,
            options=[("base", "Base"), ("active", "Active")],
            on_change=self._on_variant_switch
        )
        self._variant_toggle.pack(side=tk.LEFT, pady=4)

        # txt editor
        self._txt_frame = tk.Frame(self, bg=C["bg"])
        self._txt_text = tk.Text(
            self._txt_frame, wrap=tk.WORD, bg=C["surface"], fg=C["fg"],
            insertbackground=C["accent"], selectbackground=C["accent"],
            selectforeground="#ffffff", font=("Consolas", 10),
            borderwidth=0, highlightthickness=0, padx=16, pady=12, undo=True
        )
        txt_sb = tk.Scrollbar(self._txt_frame, orient="vertical",
                              command=self._txt_text.yview,
                              bg=C["scrollbar"], troughcolor=C["bg"], width=8, bd=0)
        self._txt_text.configure(yscrollcommand=txt_sb.set)
        txt_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._txt_text.pack(fill=tk.BOTH, expand=True)
        self._txt_text.bind("<<Modified>>", self._on_text_modified)

        # json form editor
        self._json_frame = tk.Frame(self, bg=C["bg"])
        self._json_editor = JsonFormEditor(
            self._json_frame, readonly=False, on_dirty=self._mark_dirty
        )
        self._json_editor.pack(fill=tk.BOTH, expand=True)

        # empty placeholder
        self._empty_frame = tk.Frame(self, bg=C["bg"])
        center = tk.Frame(self._empty_frame, bg=C["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(center, text="\u229e", bg=C["bg"], fg=C["surface3"],
                 font=("Segoe UI", 48)).pack()
        tk.Label(center, text="No file selected", bg=C["bg"], fg=C["fg_dim"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(8, 0))
        tk.Label(center, text="Select a category and file to edit",
                 bg=C["bg"], fg=C["fg_muted"], font=("Segoe UI", 9)).pack(pady=(4, 0))

        self._empty_frame.pack(fill=tk.BOTH, expand=True)

    # ---- internal display ----

    def _show_empty(self) -> None:
        self._toggle_row.pack_forget()
        self._txt_frame.pack_forget()
        self._json_frame.pack_forget()
        self._empty_frame.pack(fill=tk.BOTH, expand=True)
        self._fn_lbl.config(text="")
        self._meta_lbl.config(text="")
        self._dirty_lbl.pack_forget()

    def _refresh_editor(self) -> None:
        if self._entry is None:
            self._show_empty()
            return

        entry = self._entry
        readonly = self._get_readonly()

        # header
        self._fn_lbl.config(text=entry.display_name)
        self._update_meta()
        self._dirty_lbl.pack_forget()
        self._dirty = False

        # hide all content frames
        self._empty_frame.pack_forget()
        self._toggle_row.pack_forget()
        self._txt_frame.pack_forget()
        self._json_frame.pack_forget()

        # update save button
        self._save_btn.set_enabled(not readonly)

        if entry.kind == "json":
            self._load_json_editor(readonly)
            self._json_frame.pack(fill=tk.BOTH, expand=True)
        else:
            if entry.kind == "paired":
                self._toggle_row.pack(fill=tk.X)
                self._variant_toggle.set("base")
                self._active_side = "base"
            self._load_txt_editor(readonly)
            self._txt_frame.pack(fill=tk.BOTH, expand=True)

    def _update_meta(self) -> None:
        if self._entry is None:
            return
        path = (self._entry.active_path
                if self._active_side == "active" and self._entry.active_path
                else self._entry.base_path)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            mtime = "unknown"
        root = self._get_prompts_root()
        rel = os.path.relpath(path, root) if root else path
        self._meta_lbl.config(text=f"{rel}   \u2022   modified {mtime}")

    def _load_txt_editor(self, readonly: bool) -> None:
        entry = self._entry
        path = (entry.active_path
                if self._active_side == "active" and entry.active_path
                else entry.base_path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            content = f"[Error reading file: {e}]"
            readonly = True

        self._disk_content_base = content if self._active_side == "base" else self._disk_content_base
        self._disk_content_active = content if self._active_side == "active" else self._disk_content_active

        self._txt_text.config(state="normal")
        self._txt_text.delete("1.0", tk.END)
        self._txt_text.insert(tk.END, content)
        self._txt_text.edit_reset()
        self._txt_text.edit_modified(False)
        self._txt_text.config(state="disabled" if readonly else "normal")

        if readonly:
            self._txt_text.config(
                bg=C["surface"], fg=C["fg_dim"],
                insertbackground=C["surface"]
            )
        else:
            self._txt_text.config(
                bg=C["surface"], fg=C["fg"],
                insertbackground=C["accent"]
            )

    def _load_json_editor(self, readonly: bool) -> None:
        entry = self._entry
        try:
            with open(entry.base_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            data = {"_error": str(e)}
        self._disk_json = data
        self._json_editor.set_readonly(readonly)
        self._json_editor.load(data)

    def _on_variant_switch(self, side: str) -> None:
        if self._dirty:
            ans = tk.messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nSwitch variant and discard them?",
                parent=self
            )
            if not ans:
                self._variant_toggle.set(self._active_side)
                return
        self._active_side = side
        self._dirty = False
        self._dirty_lbl.pack_forget()
        self._update_meta()
        self._load_txt_editor(self._get_readonly())

    def _on_text_modified(self, event=None) -> None:
        if self._txt_text.edit_modified():
            self._mark_dirty()
            self._txt_text.edit_modified(False)

    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._dirty_lbl.pack(side=tk.RIGHT, padx=(0, 8))

    # ---- actions ----

    def _do_save(self) -> None:
        if self._entry is None:
            return
        if self._get_readonly():
            self._on_status("Read-only mode — save disabled", "warn")
            return

        prompts_root = self._get_prompts_root()
        entry = self._entry

        if entry.kind == "json":
            try:
                data = self._json_editor.get_data()
            except Exception as e:
                self._on_status(f"JSON parse error: {e}", "error")
                return
            path = entry.base_path
            if os.path.isfile(path) and prompts_root:
                _make_backup(path, prompts_root)
            try:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, path)
                self._disk_json = data
                self._dirty = False
                self._dirty_lbl.pack_forget()
                self._on_status(f"Saved: {entry.name}", "ok")
                self._update_meta()
            except OSError as e:
                self._on_status(f"Save error: {e}", "error")
        else:
            path = (entry.active_path
                    if self._active_side == "active" and entry.active_path
                    else entry.base_path)
            content = self._txt_text.get("1.0", "end-1c")
            if os.path.isfile(path) and prompts_root:
                _make_backup(path, prompts_root)
            try:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp, path)
                if self._active_side == "base":
                    self._disk_content_base = content
                else:
                    self._disk_content_active = content
                self._dirty = False
                self._dirty_lbl.pack_forget()
                self._on_status(f"Saved: {entry.name}", "ok")
                self._update_meta()
            except OSError as e:
                self._on_status(f"Save error: {e}", "error")

    def _do_reset(self) -> None:
        if self._entry is None:
            return
        entry = self._entry
        if entry.kind == "json":
            self._json_editor.load(self._disk_json)
        else:
            content = (self._disk_content_active
                       if self._active_side == "active"
                       else self._disk_content_base)
            self._txt_text.config(state="normal")
            self._txt_text.delete("1.0", tk.END)
            self._txt_text.insert(tk.END, content)
            self._txt_text.edit_reset()
            self._txt_text.edit_modified(False)
            if self._get_readonly():
                self._txt_text.config(state="disabled")
        self._dirty = False
        self._dirty_lbl.pack_forget()
        self._on_status("Reset to last saved content", "info")

    def _open_explorer(self) -> None:
        if self._entry is None:
            return
        path = (self._entry.active_path
                if self._active_side == "active" and self._entry.active_path
                else self._entry.base_path)
        folder = os.path.dirname(path)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", folder])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            self._on_status(f"Explorer error: {e}", "error")

    def _copy_to_clipboard(self) -> None:
        if self._entry is None:
            return
        try:
            if self._entry.kind == "json":
                data = self._json_editor.get_data()
                text = json.dumps(data, indent=2, ensure_ascii=False)
            else:
                text = self._txt_text.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(text)
            self._on_status("Copied to clipboard", "ok")
        except Exception as e:
            self._on_status(f"Copy error: {e}", "error")


# ===========================================================================
# PromptManagementApp
# ===========================================================================

class PromptManagementApp:
    WIN_W  = 1280
    WIN_H  = 820
    MIN_W  = 900
    MIN_H  = 600
    PANEL1_W = 220
    PANEL2_W = 260

    def __init__(self, root: tk.Toplevel, on_close=None):
        self.root = root
        self.on_close = on_close

        self.sm = SettingsManager()

        self._campaigns: list[str] = []
        self._current_campaign: Optional[str] = None
        self._prompt_index: Optional[PromptIndex] = None
        self._active_category: Optional[str] = None
        self._selected_entry: Optional[PromptFileEntry] = None

        root.title("Prompt Management")
        root.overrideredirect(True)
        root.geometry(f"{self.WIN_W}x{self.WIN_H}")
        root.minsize(self.MIN_W, self.MIN_H)
        root.configure(bg=C["border"])
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(
            f"{self.WIN_W}x{self.WIN_H}"
            f"+{(sw - self.WIN_W) // 2}+{(sh - self.WIN_H) // 2}"
        )
        root.protocol("WM_DELETE_WINDOW", self._on_destroy)

        self._frame = tk.Frame(root, bg=C["bg"],
                               highlightbackground=C["border"], highlightthickness=1)
        self._frame.pack(fill=tk.BOTH, expand=True)

        self._build_ui()
        self._init_data()

    # ---- hub integration ----

    def back_to_hub(self) -> None:
        if self._editor.has_unsaved:
            ans = tk.messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nLeave and discard them?",
                parent=self.root
            )
            if not ans:
                return
        self._on_destroy()

    def _on_destroy(self) -> None:
        self.root.destroy()
        if self.on_close:
            self.on_close()

    # ---- readonly helper ----

    def _is_readonly(self) -> bool:
        try:
            return bool(self.sm.get("readonly_mode", False))
        except Exception:
            return False

    def _get_prompts_root(self) -> str:
        if self._prompt_index:
            return self._prompt_index.prompts_root
        return ""

    # ---- data init ----

    def _init_data(self) -> None:
        save_path = self.sm.save_data_path()
        self._campaigns = discover_campaigns(save_path)

        names = self._campaigns if self._campaigns else ["(no campaigns found)"]
        self._campaign_var.set("")
        menu = self._campaign_menu["menu"]
        menu.delete(0, "end")
        for name in names:
            menu.add_command(label=name,
                             command=lambda n=name: self._on_campaign_selected(n))

        last = self.sm.last_campaign()
        if last and last in self._campaigns:
            self._campaign_var.set(last)
            self._load_campaign(last)
        elif self._campaigns:
            first = self._campaigns[0]
            self._campaign_var.set(first)
            self._load_campaign(first)
        else:
            self._campaign_var.set(names[0])
            self.status.set("No campaigns found — set save_data path in Settings", "warn")

    def _on_campaign_selected(self, campaign_id: str) -> None:
        if campaign_id not in self._campaigns:
            return
        if self._editor.has_unsaved:
            ans = tk.messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nSwitch campaign and discard them?",
                parent=self.root
            )
            if not ans:
                return
        self._campaign_var.set(campaign_id)
        self._load_campaign(campaign_id)
        self.sm.set_last_campaign(campaign_id)
        self.sm.save()

    def _load_campaign(self, campaign_id: str) -> None:
        self._current_campaign = campaign_id
        self._prompt_index = PromptIndex()
        save_path = self.sm.save_data_path()
        ok = self._prompt_index.scan(save_path, campaign_id)
        if not ok:
            self.status.set(f"prompts/ folder not found for: {campaign_id}", "warn")
        else:
            total = self._prompt_index.total_files()
            self.status.set(f"Campaign: {campaign_id}  \u2014  {total} prompt files", "ok")
        self._refresh_category_badges()
        self._active_category = None
        self._selected_entry = None
        self._cat_tree.set_active(None)
        self._file_list.load([])
        self._editor.clear()
        self._panel2_header.config(text="Select a category")
        self._panel2_count.config(text="")

    def _refresh_category_badges(self) -> None:
        if self._prompt_index is None:
            return
        counts: dict[str, int] = {}
        for cat_key, cm in self._prompt_index.categories.items():
            counts[cat_key] = cm.count
        counts["__root__"] = len(self._prompt_index.root_entries)
        self._cat_tree.set_counts(counts)

    # ---- UI construction ----

    def _build_ui(self) -> None:
        bar = CustomTitleBar(self._frame, self, "Prompt Management")
        bar.pack(fill=tk.X)

        body = tk.Frame(self._frame, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        self._build_panel1(body)
        self._build_panel2(body)
        self._build_panel3(body)

        self.status = StatusBar(self._frame)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_panel1(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=C["surface"], width=self.PANEL1_W)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)

        hdr = tk.Frame(panel, bg=C["surface"], height=48)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="\u229e Prompts", bg=C["surface"], fg=C["accent2"],
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=14, pady=12)

        tk.Frame(panel, bg=C["border"], height=1).pack(fill=tk.X)

        camp_frame = tk.Frame(panel, bg=C["surface"], pady=8)
        camp_frame.pack(fill=tk.X, padx=10)
        tk.Label(camp_frame, text="CAMPAIGN", bg=C["surface"], fg=C["fg_muted"],
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(0, 4))

        self._campaign_var = tk.StringVar()
        self._campaign_menu = tk.OptionMenu(camp_frame, self._campaign_var, "")
        self._campaign_menu.config(
            bg=C["surface2"], fg=C["fg"], activebackground=C["surface3"],
            activeforeground=C["fg"], relief="flat", borderwidth=0,
            highlightthickness=1, highlightbackground=C["border"],
            font=("Segoe UI", 9), indicatoron=True, cursor="hand2"
        )
        self._campaign_menu["menu"].config(
            bg=C["surface2"], fg=C["fg"],
            activebackground=C["accent"], activeforeground="#fff",
            borderwidth=0, font=("Segoe UI", 9)
        )
        self._campaign_menu.pack(fill=tk.X)

        FlatButton(camp_frame, text="\u21ba Refresh",
                   command=self._refresh_campaigns,
                   bg=C["surface"], fg=C["fg_muted"],
                   hover_bg=C["surface2"], hover_fg=C["accent2"],
                   font=("Segoe UI", 8), padx=4, pady=3).pack(anchor="e", pady=(4, 0))

        # readonly badge
        self._ro_badge = tk.Label(panel, text="\u26d4 READ-ONLY",
                                  bg=C["surface"], fg=C["accent3"],
                                  font=("Segoe UI", 7, "bold"), pady=3)
        if self._is_readonly():
            self._ro_badge.pack(fill=tk.X, padx=10)

        tk.Frame(panel, bg=C["border"], height=1).pack(fill=tk.X, padx=6, pady=4)

        tk.Label(panel, text="CATEGORIES", bg=C["surface"], fg=C["fg_muted"],
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=14, pady=(4, 2))

        self._cat_tree = CategoryTree(panel, on_select=self._on_category_selected)
        self._cat_tree.pack(fill=tk.BOTH, expand=True)

    def _build_panel2(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=C["surface2"], width=self.PANEL2_W)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)

        tk.Frame(panel, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(panel, bg=C["surface2"])
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        hdr = tk.Frame(inner, bg=C["surface2"], height=40)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        self._panel2_header = tk.Label(
            hdr, text="Select a category",
            bg=C["surface2"], fg=C["fg_dim"],
            font=("Segoe UI", 9, "bold"), anchor="w"
        )
        self._panel2_header.pack(side=tk.LEFT, padx=12, pady=10)
        self._panel2_count = tk.Label(
            hdr, text="",
            bg=C["surface2"], fg=C["accent2"],
            font=("Segoe UI", 8)
        )
        self._panel2_count.pack(side=tk.RIGHT, padx=10)

        tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X)

        search_row = tk.Frame(inner, bg=C["surface2"], pady=6)
        search_row.pack(fill=tk.X, padx=8)
        tk.Label(search_row, text="\u2315", bg=C["surface2"], fg=C["fg_muted"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        tk.Entry(
            search_row, textvariable=self._search_var,
            bg=C["surface3"], fg=C["fg"],
            insertbackground=C["accent"],
            selectbackground=C["accent"], selectforeground="#fff",
            relief="flat", borderwidth=0,
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent2"],
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X)

        self._file_list = VirtualFileList(inner, on_select=self._on_file_selected)
        self._file_list.pack(fill=tk.BOTH, expand=True)

    def _build_panel3(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=C["bg"])
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Frame(panel, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(panel, bg=C["bg"])
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._editor = PromptEditor(
            inner,
            get_readonly=self._is_readonly,
            get_prompts_root=self._get_prompts_root,
            on_status=lambda msg, lvl="ok": self.status.set(msg, lvl)
        )
        self._editor.pack(fill=tk.BOTH, expand=True)

    # ---- event handlers ----

    def _on_category_selected(self, cat_key: str) -> None:
        if self._editor.has_unsaved:
            ans = tk.messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nSwitch category and discard them?",
                parent=self.root
            )
            if not ans:
                self._cat_tree.set_active(self._active_category)
                return

        self._active_category = cat_key
        if self._prompt_index is None:
            return
        entries = self._prompt_index.entries_for_category(cat_key)
        self._file_list.load(entries, self._search_var.get())

        label = "Root Files" if cat_key == "__root__" else cat_key.replace("_", " ").title()
        self._panel2_header.config(text=label)
        self._panel2_count.config(text=str(len(entries)))

        self._selected_entry = None
        self._editor.clear()
        self.status.set(f"Category: {label}  \u2014  {len(entries)} files", "info")

    def _on_file_selected(self, entry: PromptFileEntry) -> None:
        if self._editor.has_unsaved:
            ans = tk.messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nLoad new file and discard them?",
                parent=self.root
            )
            if not ans:
                return

        self._selected_entry = entry
        self._editor.load_entry(entry)
        self.status.set(
            f"{entry.display_name}  \u2014  {entry.type_tag}  \u2014  {entry.base_path}",
            "info"
        )

    def _on_search_changed(self, *_) -> None:
        self._file_list.filter(self._search_var.get())

    def _refresh_campaigns(self) -> None:
        self._init_data()
        self.status.set("Campaigns refreshed", "ok")


# ===========================================================================
# Standalone entry point
# ===========================================================================

def main():
    root = tk.Tk()
    root.withdraw()
    app = PromptManagementApp(root)
    root.update_idletasks()
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
